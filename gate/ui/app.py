"""Fullscreen gate UI tuned for small Pi displays."""

from __future__ import annotations

import json
import threading
import tkinter as tk
from tkinter import font as tkfont

from api import check_in
from config import is_configured, load_config, optional_id
from parse_qr import QRParseError, parse_qr
from ui.settings import SettingsDialog

COOLDOWN_MS = 4000

COLORS = {
    "bg": "#0f1419",
    "panel": "#1a222c",
    "idle": "#1a222c",
    "success": "#149a4a",
    "fail": "#c62828",
    "checking": "#1e3a5f",
    "text": "#f4f6f8",
    "muted": "#8b97a5",
    "accent": "#e8a838",
    "border": "#2a3542",
    "btn": "#2a3542",
    "btn_active": "#3a4756",
    "debug_bg": "#0b0f13",
}


class GateApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Chudartz Gate")
        self.config_data = load_config()
        self.scan_buffer: list[str] = []
        self.cooldown = False
        self._busy = False
        self._cooldown_after_id = None
        self._state = "idle"
        self._last_raw = ""
        self._request_gen = 0

        self.attributes("-fullscreen", True)
        self.configure(bg=COLORS["bg"])
        self.bind("<Key>", self._on_key)
        self.bind("<F2>", lambda _e: self.open_settings())
        self.bind("<F5>", lambda _e: self.reset_scanner())
        self.bind("<Escape>", self._on_escape)
        self.bind("<Control-comma>", lambda _e: self.open_settings())
        self.bind("<Configure>", self._on_resize)

        sw = max(self.winfo_screenwidth(), 480)
        sh = max(self.winfo_screenheight(), 320)
        self._scale_fonts(sw, sh)

        # Top bar
        self.top = tk.Frame(self, bg=COLORS["bg"], height=56)
        self.top.pack(fill="x", side="top")
        self.top.pack_propagate(False)

        self.brand = tk.Label(
            self.top,
            text="CHUDARTZ",
            font=self.brand_font,
            fg=COLORS["accent"],
            bg=COLORS["bg"],
            padx=12,
        )
        self.brand.pack(side="left", pady=8)

        self.filter_label = tk.Label(
            self.top,
            text="",
            font=self.small_font,
            fg=COLORS["muted"],
            bg=COLORS["bg"],
        )
        self.filter_label.pack(side="left", padx=(0, 8))

        self.reset_btn = tk.Button(
            self.top,
            text="RESET",
            font=self.btn_font,
            command=self.reset_scanner,
            bg=COLORS["btn"],
            fg=COLORS["text"],
            activebackground=COLORS["btn_active"],
            activeforeground=COLORS["text"],
            relief="flat",
            bd=0,
            padx=16,
            pady=6,
            cursor="hand2",
        )
        self.reset_btn.pack(side="right", padx=10, pady=8)

        self.settings_btn = tk.Button(
            self.top,
            text="⚙",
            font=self.btn_font,
            command=self.open_settings,
            bg=COLORS["btn"],
            fg=COLORS["text"],
            activebackground=COLORS["btn_active"],
            activeforeground=COLORS["text"],
            relief="flat",
            bd=0,
            padx=12,
            pady=6,
            cursor="hand2",
        )
        self.settings_btn.pack(side="right", pady=8)

        # Main status card
        self.card = tk.Frame(self, bg=COLORS["idle"], highlightthickness=0)
        self.card.pack(fill="both", expand=True, padx=10, pady=(0, 8))

        self.status_label = tk.Label(
            self.card,
            text="Scan ticket",
            font=self.title_font,
            fg=COLORS["text"],
            bg=COLORS["idle"],
        )
        self.status_label.pack(expand=True, pady=(16, 4))

        self.message_label = tk.Label(
            self.card,
            text="Ready",
            font=self.message_font,
            fg=COLORS["muted"],
            bg=COLORS["idle"],
            wraplength=max(sw - 48, 280),
            justify="center",
        )
        self.message_label.pack(pady=(0, 20))

        # Debug panel
        self.debug_frame = tk.Frame(self, bg=COLORS["debug_bg"])
        self.debug_header = tk.Label(
            self.debug_frame,
            text="DEBUG",
            font=self.small_font,
            fg=COLORS["accent"],
            bg=COLORS["debug_bg"],
            anchor="w",
            padx=8,
        )
        self.debug_header.pack(fill="x", pady=(4, 0))

        self.debug_text = tk.Text(
            self.debug_frame,
            height=7,
            font=self.debug_font,
            bg=COLORS["debug_bg"],
            fg="#b8c4d0",
            insertbackground=COLORS["text"],
            relief="flat",
            bd=0,
            wrap="word",
            state="disabled",
            padx=8,
            pady=4,
        )
        self.debug_text.pack(fill="both", expand=True, padx=4, pady=(0, 6))

        self.hint_label = tk.Label(
            self,
            text="F5 reset · F2 settings · Esc exit fullscreen",
            font=self.small_font,
            fg=COLORS["muted"],
            bg=COLORS["bg"],
        )
        self.hint_label.pack(side="bottom", pady=(0, 6))

        self._update_filter_label()
        self._apply_debug_visibility()
        self._set_debug_lines(["Waiting for scanner input…"])

        if not is_configured(self.config_data):
            self.after(200, self.open_settings)

    def _scale_fonts(self, sw: int, sh: int):
        # Tuned for ~7" / 800x480-class panels; scales up on larger screens.
        unit = max(min(sw, sh) / 480, 0.75)
        family = "DejaVu Sans"
        mono = "DejaVu Sans Mono"
        self.brand_font = tkfont.Font(family=family, size=max(int(14 * unit), 11), weight="bold")
        self.title_font = tkfont.Font(family=family, size=max(int(36 * unit), 22), weight="bold")
        self.message_font = tkfont.Font(family=family, size=max(int(16 * unit), 12))
        self.btn_font = tkfont.Font(family=family, size=max(int(12 * unit), 10), weight="bold")
        self.small_font = tkfont.Font(family=family, size=max(int(10 * unit), 9))
        self.debug_font = tkfont.Font(family=mono, size=max(int(9 * unit), 8))

    def _on_resize(self, event):
        if event.widget is self:
            self.message_label.configure(wraplength=max(event.width - 48, 240))

    def open_settings(self):
        SettingsDialog(self, self.config_data, on_save=self._on_config_saved)

    def _on_config_saved(self, data: dict):
        self.config_data = data
        self._update_filter_label()
        self._apply_debug_visibility()
        self.reset_scanner(message="Settings saved")

    def _update_filter_label(self):
        parts = []
        if self.config_data.get("event_id"):
            parts.append(f"event {self.config_data['event_id']}")
        if self.config_data.get("ticket_id"):
            parts.append(f"ticket {self.config_data['ticket_id']}")
        self.filter_label.configure(text=" · ".join(parts) if parts else "any ticket")

    def _apply_debug_visibility(self):
        if self.config_data.get("debug"):
            self.debug_frame.pack(fill="x", side="bottom", before=self.hint_label, padx=10, pady=(0, 4))
        else:
            self.debug_frame.pack_forget()

    def reset_scanner(self, message: str = "Ready"):
        """Clear scan buffer / cooldown and return to idle (does not touch config)."""
        if self._cooldown_after_id is not None:
            try:
                self.after_cancel(self._cooldown_after_id)
            except tk.TclError:
                pass
            self._cooldown_after_id = None

        self.scan_buffer.clear()
        self.cooldown = False
        self._busy = False
        self._last_raw = ""
        self._request_gen += 1
        self._set_state("idle", "Scan ticket", message)
        self._refresh_debug_live()

    def _on_escape(self, _event=None):
        if self.attributes("-fullscreen"):
            self.attributes("-fullscreen", False)
            self.geometry("800x480")
        else:
            self.destroy()

    def _on_key(self, event: tk.Event):
        if event.keysym in ("F2", "F5", "Escape"):
            return
        if event.state & 0x4 and event.keysym == "comma":
            return
        if any(isinstance(w, SettingsDialog) for w in self.winfo_children()):
            return

        if event.keysym == "Return":
            raw = "".join(self.scan_buffer)
            self.scan_buffer.clear()
            self._refresh_debug_live()
            if raw:
                self._handle_scan(raw)
            return

        if event.keysym == "BackSpace":
            if self.scan_buffer:
                self.scan_buffer.pop()
                self._refresh_debug_live()
            return

        char = event.char
        if char and char.isprintable():
            self.scan_buffer.append(char)
            self._refresh_debug_live()

    def _handle_scan(self, raw: str):
        if self.cooldown or self._busy:
            self._set_debug_lines(
                [
                    f"Ignored (busy/cooldown): {raw!r}",
                    f"cooldown={self.cooldown} busy={self._busy}",
                ]
            )
            return

        self.cooldown = True
        self._cooldown_after_id = self.after(COOLDOWN_MS, self._end_cooldown)
        self._last_raw = raw

        try:
            ticket = parse_qr(raw)
        except QRParseError as exc:
            self._set_state("fail", "Denied", str(exc))
            self._set_debug_lines([f"RAW: {raw}", f"Parse error: {exc}"])
            return

        if not is_configured(self.config_data):
            self._set_state("fail", "Not configured", "Open settings and set URL + API key")
            self.after(500, self.open_settings)
            return

        self._busy = True
        self._set_state("checking", "Checking…", "Please wait")
        self._set_debug_lines(
            [
                f"RAW: {raw}",
                f"Parsed: participant_id={ticket.participant_id} seed={ticket.seed}",
                "Sending request…",
            ]
        )

        request_gen = self._request_gen
        thread = threading.Thread(
            target=self._check_in_worker,
            args=(ticket.participant_id, ticket.seed, request_gen),
            daemon=True,
        )
        thread.start()

    def _check_in_worker(self, participant_id: int, seed: str, request_gen: int):
        result = check_in(
            self.config_data["base_url"],
            self.config_data["api_key"],
            participant_id,
            seed,
            host_header=self.config_data.get("host_header") or "chudartz-collectibles.com",
            event_id=optional_id(self.config_data, "event_id"),
            ticket_id=optional_id(self.config_data, "ticket_id"),
        )
        self.after(0, lambda: self._on_check_in_done(result, request_gen))

    def _on_check_in_done(self, result, request_gen: int):
        if request_gen != self._request_gen:
            return
        self._busy = False
        self._set_debug_lines(
            [
                f"RAW: {self._last_raw}",
                f"URL: {result.request_url}",
                f"REQUEST: {json.dumps(result.request_body, ensure_ascii=True)}",
                f"HTTP {result.status_code}",
                f"RESPONSE: {json.dumps(result.response_body, ensure_ascii=True) or result.message}",
            ]
        )
        if result.success:
            self._set_state("success", "Welcome", result.message)
            self.bell()
        else:
            self._set_state("fail", "Denied", result.message)

    def _end_cooldown(self):
        self._cooldown_after_id = None
        self.cooldown = False
        if not self._busy and self._state in ("success", "fail", "idle"):
            if self._state in ("success", "fail"):
                self._set_state("idle", "Scan ticket", "Ready")

    def _set_state(self, state: str, title: str, message: str):
        self._state = state
        color = COLORS.get(state, COLORS["idle"])
        self.card.configure(bg=color)
        self.status_label.configure(text=title, fg=COLORS["text"], bg=color)
        msg_fg = COLORS["text"] if state != "idle" else COLORS["muted"]
        self.message_label.configure(text=message, fg=msg_fg, bg=color)

    def _refresh_debug_live(self):
        if not self.config_data.get("debug"):
            return
        buf = "".join(self.scan_buffer)
        lines = [
            f"BUFFER ({len(self.scan_buffer)}): {buf!r}",
            f"state={self._state} cooldown={self.cooldown} busy={self._busy}",
        ]
        if self._last_raw:
            lines.append(f"LAST RAW: {self._last_raw}")
        self._set_debug_lines(lines)

    def _set_debug_lines(self, lines: list[str]):
        if not self.config_data.get("debug") and self._state == "idle":
            # Still update buffer so enabling debug later is fine; skip heavy redraw when hidden
            pass
        self.debug_text.configure(state="normal")
        self.debug_text.delete("1.0", "end")
        self.debug_text.insert("1.0", "\n".join(lines))
        self.debug_text.configure(state="disabled")
        self.debug_text.see("end")
