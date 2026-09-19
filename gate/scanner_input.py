"""Read USB keyboard-wedge QR scanners via Linux evdev (no window focus needed).

Keystrokes are assembled on the reader thread and delivered to the UI through a
thread-safe queue. Calling Tk `after()` from a background thread drops characters
under burst input from fast HID wedges.
"""

from __future__ import annotations

import queue
import select
import threading
import time
from pathlib import Path

try:
    import fcntl
    import os
except ImportError:  # pragma: no cover
    fcntl = None  # type: ignore[assignment]
    os = None  # type: ignore[assignment]

try:
    from evdev import InputDevice, categorize, ecodes, list_devices
except ImportError:  # pragma: no cover - optional on non-Linux / missing package
    InputDevice = None  # type: ignore[misc, assignment]
    categorize = None  # type: ignore[misc, assignment]
    ecodes = None  # type: ignore[misc, assignment]
    list_devices = None  # type: ignore[misc, assignment]


# US QWERTY + keypad digits: keycode -> (unshifted, shifted).
_KEYMAP = {
    "KEY_1": ("1", "!"),
    "KEY_2": ("2", "@"),
    "KEY_3": ("3", "#"),
    "KEY_4": ("4", "$"),
    "KEY_5": ("5", "%"),
    "KEY_6": ("6", "^"),
    "KEY_7": ("7", "&"),
    "KEY_8": ("8", "*"),
    "KEY_9": ("9", "("),
    "KEY_0": ("0", ")"),
    "KEY_MINUS": ("-", "_"),
    "KEY_EQUAL": ("=", "+"),
    "KEY_Q": ("q", "Q"),
    "KEY_W": ("w", "W"),
    "KEY_E": ("e", "E"),
    "KEY_R": ("r", "R"),
    "KEY_T": ("t", "T"),
    "KEY_Y": ("y", "Y"),
    "KEY_U": ("u", "U"),
    "KEY_I": ("i", "I"),
    "KEY_O": ("o", "O"),
    "KEY_P": ("p", "P"),
    "KEY_LEFTBRACE": ("[", "{"),
    "KEY_RIGHTBRACE": ("]", "}"),
    "KEY_A": ("a", "A"),
    "KEY_S": ("s", "S"),
    "KEY_D": ("d", "D"),
    "KEY_F": ("f", "F"),
    "KEY_G": ("g", "G"),
    "KEY_H": ("h", "H"),
    "KEY_J": ("j", "J"),
    "KEY_K": ("k", "K"),
    "KEY_L": ("l", "L"),
    "KEY_SEMICOLON": (";", ":"),
    "KEY_APOSTROPHE": ("'", '"'),
    "KEY_GRAVE": ("`", "~"),
    "KEY_BACKSLASH": ("\\", "|"),
    "KEY_Z": ("z", "Z"),
    "KEY_X": ("x", "X"),
    "KEY_C": ("c", "C"),
    "KEY_V": ("v", "V"),
    "KEY_B": ("b", "B"),
    "KEY_N": ("n", "N"),
    "KEY_M": ("m", "M"),
    "KEY_COMMA": (",", "<"),
    "KEY_DOT": (".", ">"),
    "KEY_SLASH": ("/", "?"),
    "KEY_SPACE": (" ", " "),
    # Numeric keypad (common on some wedges when NumLock is on)
    "KEY_KP1": ("1", "1"),
    "KEY_KP2": ("2", "2"),
    "KEY_KP3": ("3", "3"),
    "KEY_KP4": ("4", "4"),
    "KEY_KP5": ("5", "5"),
    "KEY_KP6": ("6", "6"),
    "KEY_KP7": ("7", "7"),
    "KEY_KP8": ("8", "8"),
    "KEY_KP9": ("9", "9"),
    "KEY_KP0": ("0", "0"),
    "KEY_KPDOT": (".", "."),
    "KEY_KPMINUS": ("-", "-"),
    "KEY_KPPLUS": ("+", "+"),
    "KEY_KPASTERISK": ("*", "*"),
    "KEY_KPSLASH": ("/", "/"),
}

# Drop a partial buffer if the wedge stalls mid-scan (ms).
_PARTIAL_IDLE_MS = 400


def _looks_like_scanner(dev: "InputDevice") -> bool:
    """Prefer USB HID keyboards; skip HDMI CEC / virtual devices."""
    path = (dev.path or "").lower()
    name = (dev.name or "").lower()
    phys = (dev.phys or "").lower()
    if "hdmi" in name or "vc4" in name:
        return False
    if not phys.startswith("usb-") and "usb-" not in path and "/by-id/usb-" not in path:
        by_id = Path("/dev/input/by-id")
        if by_id.is_dir():
            for link in by_id.glob("usb-*-event-kbd"):
                try:
                    if link.resolve() == Path(dev.path).resolve():
                        return True
                except OSError:
                    continue
        return False
    caps = dev.capabilities()
    keys = caps.get(ecodes.EV_KEY, [])
    return bool(keys) and (
        ecodes.KEY_ENTER in keys or ecodes.KEY_A in keys or ecodes.KEY_1 in keys
    )


def find_scanner_devices() -> list["InputDevice"]:
    """Return at most one USB keyboard-wedge device.

    Prefer ``/dev/input/by-id/usb-*-event-kbd`` so we do not grab the same
    physical scanner twice via multiple event nodes (which drops characters).
    """
    if list_devices is None:
        return []

    candidates: list[str] = []
    by_id = Path("/dev/input/by-id")
    if by_id.is_dir():
        for link in sorted(by_id.glob("usb-*-event-kbd")):
            try:
                candidates.append(str(link.resolve()))
            except OSError:
                continue

    if not candidates:
        for path in list_devices():
            try:
                dev = InputDevice(path)
            except (OSError, PermissionError):
                continue
            ok = _looks_like_scanner(dev)
            resolved = dev.path
            try:
                dev.close()
            except OSError:
                pass
            if ok:
                candidates.append(resolved)

    # Deduplicate and open only the first match.
    seen: set[str] = set()
    unique: list[str] = []
    for path in candidates:
        if path in seen:
            continue
        seen.add(path)
        unique.append(path)

    found: list[InputDevice] = []
    for path in unique[:1]:
        try:
            found.append(InputDevice(path))
        except (OSError, PermissionError):
            continue
    return found


class ScannerReader:
    """Background USB-wedge reader.

    Events placed on ``self.events`` (thread-safe):
      ("status", message)
      ("active", True|False)  — device grabbed / released
      ("partial", current_buffer)
      ("scan", full_payload)  — Enter received; buffer already cleared
    """

    def __init__(self):
        self.events: queue.Queue[tuple] = queue.Queue()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._shift = False
        self._caps = False
        self._buffer: list[str] = []
        self._last_key_at = 0.0
        self._devices: list[InputDevice] = []

    @property
    def available(self) -> bool:
        return InputDevice is not None

    def start(self) -> bool:
        if not self.available:
            self._emit("status", "evdev niet beschikbaar — val terug op toetsenbord-focus")
            return False
        if self._thread and self._thread.is_alive():
            return True
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="scanner-evdev", daemon=True)
        self._thread.start()
        return True

    def stop(self) -> None:
        self._stop.set()
        for dev in self._devices:
            try:
                dev.close()
            except OSError:
                pass
        self._devices = []
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._thread = None

    def _emit(self, kind: str, payload) -> None:
        self.events.put((kind, payload))
        if kind == "status":
            print(f"[scanner] {payload}", flush=True)

    def _clear_buffer(self, emit_partial: bool = True) -> None:
        self._buffer.clear()
        self._last_key_at = 0.0
        if emit_partial:
            self._emit("partial", "")

    def _open_devices(self) -> list[InputDevice]:
        devices = find_scanner_devices()
        grabbed: list[InputDevice] = []
        for dev in devices:
            try:
                # Grab so keystrokes do not also hit the focused window (duplicates).
                dev.grab()
                if fcntl is not None and os is not None:
                    flags = fcntl.fcntl(dev.fd, fcntl.F_GETFL)
                    fcntl.fcntl(dev.fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
                grabbed.append(dev)
                self._emit("status", f"Scanner gekoppeld: {dev.name} ({dev.path})")
                self._emit("active", True)
            except OSError as exc:
                self._emit("status", f"Kon scanner niet claimen ({dev.path}): {exc}")
                try:
                    dev.close()
                except OSError:
                    pass
        return grabbed

    def _run(self) -> None:
        while not self._stop.is_set():
            self._devices = self._open_devices()
            if not self._devices:
                self._emit("active", False)
                self._emit("status", "Geen USB-scanner gevonden — opnieuw proberen over 3s")
                self._stop.wait(3.0)
                continue

            try:
                self._poll_loop()
            finally:
                self._clear_buffer()
                self._emit("active", False)
                for dev in self._devices:
                    try:
                        dev.ungrab()
                    except OSError:
                        pass
                    try:
                        dev.close()
                    except OSError:
                        pass
                self._devices = []

            if not self._stop.is_set():
                time.sleep(1.0)

    def _poll_loop(self) -> None:
        devices = {dev.fd: dev for dev in self._devices}
        while not self._stop.is_set() and devices:
            if self._buffer and self._last_key_at:
                idle_ms = (time.monotonic() - self._last_key_at) * 1000
                if idle_ms >= _PARTIAL_IDLE_MS:
                    dropped = "".join(self._buffer)
                    self._emit(
                        "status",
                        f"Onvolledige scan verworpen ({len(dropped)} tekens): {dropped!r}",
                    )
                    self._clear_buffer()

            try:
                r, _w, _x = select.select(list(devices.keys()), [], [], 0.05)
            except (OSError, ValueError):
                break
            for fd in r:
                dev = devices.get(fd)
                if dev is None:
                    continue
                try:
                    # Fully drain the kernel queue for this readable burst.
                    while True:
                        try:
                            events = list(dev.read())
                        except BlockingIOError:
                            break
                        if not events:
                            break
                        for event in events:
                            self._handle_event(event)
                except OSError:
                    try:
                        dev.close()
                    except OSError:
                        pass
                    devices.pop(fd, None)
                    break

    def _handle_event(self, event) -> None:
        # Kernel overflow — discard partial payload.
        if event.type == ecodes.EV_SYN and event.code == ecodes.SYN_DROPPED:
            self._emit("status", "Invoerbuffer overgelopen — scan genegeerd")
            self._clear_buffer()
            self._shift = False
            return

        if event.type != ecodes.EV_KEY:
            return

        key = categorize(event)
        keycode = key.keycode
        if isinstance(keycode, (list, tuple)):
            keycode = keycode[0]

        if keycode in ("KEY_LEFTSHIFT", "KEY_RIGHTSHIFT"):
            self._shift = key.keystate != key.key_up
            return

        if keycode == "KEY_CAPSLOCK" and key.keystate == key.key_down:
            self._caps = not self._caps
            return

        # Only key-down (not hold-repeat / key-up).
        if key.keystate != key.key_down:
            return

        now = time.monotonic()
        self._last_key_at = now

        if keycode in ("KEY_ENTER", "KEY_KPENTER"):
            raw = "".join(self._buffer)
            self._buffer.clear()
            self._last_key_at = 0.0
            self._emit("partial", "")
            if raw:
                self._emit("scan", raw)
            return

        if keycode == "KEY_BACKSPACE":
            if self._buffer:
                self._buffer.pop()
                self._emit("partial", "".join(self._buffer))
            return

        pair = _KEYMAP.get(keycode)
        if not pair:
            return
        ch = pair[1] if self._shift else pair[0]
        if ch.isalpha() and self._caps:
            ch = ch.swapcase()
        self._buffer.append(ch)
        self._emit("partial", "".join(self._buffer))
