"""Fullscreen gate UI — ChudartZ Collectibles branding, Nederlands."""

from __future__ import annotations

import json
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import font as tkfont

from api import check_in, send_heartbeat
from config import is_configured, load_config, optional_id, save_config
from parse_qr import QRParseError, parse_qr
from sound import play_error, play_success
from ui import i18n
from ui.settings import SettingsDialog

COOLDOWN_MS = 2000
HEADER_IDLE_MS = 2500
HEARTBEAT_MS = 30000
SCAN_EXPECTED_LEN = 20
SCAN_PROGRESS_CAP = 0.95
CHECKING_PULSE_MS = 80
PROGRESS_MIN_WIDTH = 240
PROGRESS_MAX_WIDTH = 480
PROGRESS_HEIGHT = 8
ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
LOGO_PATH = ASSETS_DIR / "logo.png"

# Brand palette from pokemon site / logo (#c3111a accent)
COLORS = {
    "bg": "#eceeef",
    "header": "#111111",
    "card": "#ffffff",
    "idle": "#ffffff",
    "success": "#1b8a42",
    "fail": "#c3111a",
    "checking": "#32353a",
    "text": "#212529",
    "text_on_dark": "#ffffff",
    "muted": "#6c757d",
    "muted_on_dark": "#9aa0a6",
    "accent": "#c3111a",
    "accent_hover": "#a00e16",
    "border": "#d5d8dc",
    "btn_bg": "#1a1a1a",
    "btn_border": "#c3111a",
    "debug_bg": "#0d0d0d",
    "debug_fg": "#d0d5db",
}


class GateApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(i18n.WINDOW_TITLE)
        self.config_data = load_config()
        self.scan_buffer: list[str] = []
        self.cooldown = False
        self._busy = False
        self._cooldown_after_id = None
        self._state = "idle"
        self._last_raw = ""
        self._request_gen = 0
        self._logo_image = None
        self._header_visible = True
        self._header_hide_after_id = None
        self._last_heartbeat = "—"
        self._progress_mode = "hidden"
        self._checking_pulse_after_id = None
        self._checking_pulse_step = 0
        self._progress_visible = False
        self._progress_track_width = PROGRESS_MAX_WIDTH

        self.attributes("-fullscreen", True)
        self.configure(bg=COLORS["bg"])
        self.bind("<Key>", self._on_key)
        self.bind("<F2>", lambda _e: self.open_settings())
        self.bind("<F5>", lambda _e: self.reset_scanner())
        self.bind("<Escape>", self._on_escape)
        self.bind("<Control-comma>", lambda _e: self.open_settings())
        self.bind("<Configure>", self._on_resize)
        self.bind_all("<Motion>", self._on_mouse_motion)

        sw = max(self.winfo_screenwidth(), 480)
        sh = max(self.winfo_screenheight(), 320)
        self._scale_fonts(sw, sh)

        self._build_header()
        self._build_card(sw)
        self._build_debug()

        self._update_filter_label()
        self._apply_debug_visibility()
        self._set_debug_lines([i18n.DEBUG_WAITING])
        self._schedule_header_hide()
        self._schedule_heartbeat()

        if not is_configured(self.config_data):
            self.after(200, self.open_settings)

    def _scale_fonts(self, sw: int, sh: int):
        unit = max(min(sw, sh) / 480, 0.75)
        family = "DejaVu Sans"
        mono = "DejaVu Sans Mono"
        self.title_font = tkfont.Font(family=family, size=max(int(34 * unit), 22), weight="bold")
        self.message_font = tkfont.Font(family=family, size=max(int(15 * unit), 12))
        self.btn_font = tkfont.Font(family=family, size=max(int(11 * unit), 10), weight="bold")
        self.small_font = tkfont.Font(family=family, size=max(int(10 * unit), 9))
        self.debug_font = tkfont.Font(family=mono, size=max(int(9 * unit), 8))

    def _build_header(self):
        self.header = tk.Frame(
            self,
            bg=COLORS["header"],
            highlightbackground=COLORS["border"],
            highlightthickness=1,
        )
        self.header.pack(fill="x", side="top")

        logo_wrap = tk.Frame(self.header, bg=COLORS["header"])
        logo_wrap.pack(side="left", padx=12, pady=8)

        self.logo_label = tk.Label(logo_wrap, bg=COLORS["header"])
        self._load_logo()
        self.logo_label.pack(side="left")

        self.filter_label = tk.Label(
            self.header,
            text="",
            font=self.small_font,
            fg=COLORS["muted_on_dark"],
            bg=COLORS["header"],
        )
        self.filter_label.pack(side="left", padx=(8, 8))

        btn_wrap = tk.Frame(self.header, bg=COLORS["header"])
        btn_wrap.pack(side="right", padx=10, pady=8)

        self.settings_btn = self._make_outline_button(
            btn_wrap, i18n.BTN_SETTINGS, self.open_settings
        )
        self.settings_btn.pack(side="right", padx=(6, 0))

        self.reset_btn = self._make_accent_button(
            btn_wrap, i18n.BTN_RESET, self.reset_scanner
        )
        self.reset_btn.pack(side="right")

    def _make_accent_button(self, parent, text, command) -> tk.Button:
        return tk.Button(
            parent,
            text=text,
            font=self.btn_font,
            command=command,
            bg=COLORS["accent"],
            fg=COLORS["text_on_dark"],
            activebackground=COLORS["accent_hover"],
            activeforeground=COLORS["text_on_dark"],
            relief="flat",
            bd=0,
            padx=14,
            pady=7,
            cursor="hand2",
            highlightthickness=0,
        )

    def _make_outline_button(self, parent, text, command) -> tk.Button:
        return tk.Button(
            parent,
            text=text,
            font=self.btn_font,
            command=command,
            bg=COLORS["btn_bg"],
            fg=COLORS["text_on_dark"],
            activebackground="#2a2a2a",
            activeforeground=COLORS["text_on_dark"],
            relief="flat",
            bd=0,
            highlightbackground=COLORS["btn_border"],
            highlightcolor=COLORS["btn_border"],
            highlightthickness=1,
            padx=12,
            pady=6,
            cursor="hand2",
        )

    def _load_logo(self):
        path = LOGO_PATH
        if not path.is_file():
            # Fallback if assets not shipped yet
            alt = Path(__file__).resolve().parents[2] / "pokemon" / "static" / "pokemon" / "img" / "logo-black.png"
            path = alt if alt.is_file() else None
        if path is None:
            self.logo_label.configure(
                text="ChudartZ Collectibles",
                font=self.btn_font,
                fg=COLORS["accent"],
            )
            return
        try:
            img = tk.PhotoImage(file=str(path))
            # Keep logo readable on small screens without dominating the header
            max_h = 48
            while img.height() > max_h * 2 and img.width() > 80:
                img = img.subsample(2, 2)
            if img.height() > max_h:
                # Fine subsample if still tall
                factor = max(1, img.height() // max_h)
                if factor > 1:
                    img = img.subsample(factor, factor)
            self._logo_image = img
            self.logo_label.configure(image=self._logo_image)
        except tk.TclError:
            self.logo_label.configure(
                text="ChudartZ Collectibles",
                font=self.btn_font,
                fg=COLORS["accent"],
            )

    def _build_card(self, sw: int):
        # Full-bleed status area under the header (no gray/white frame margin)
        self.card = tk.Frame(self, bg=COLORS["idle"], highlightthickness=0)
        self.card.pack(fill="both", expand=True)

        self.accent_bar = tk.Frame(self.card, bg=COLORS["accent"], height=4)
        self.accent_bar.pack(fill="x", side="top")

        # Keep title + feedback text as one centered block
        self.content = tk.Frame(self.card, bg=COLORS["idle"])
        self.content.place(relx=0.5, rely=0.45, anchor="center")

        self.status_label = tk.Label(
            self.content,
            text=i18n.TITLE_IDLE,
            font=self.title_font,
            fg=COLORS["text"],
            bg=COLORS["idle"],
        )
        self.status_label.pack(pady=(0, 10))

        self.message_label = tk.Label(
            self.content,
            text=i18n.MSG_READY,
            font=self.message_font,
            fg=COLORS["muted"],
            bg=COLORS["idle"],
            wraplength=max(sw - 48, 260),
            justify="center",
        )
        self.message_label.pack()

        self._build_scan_progress(sw)

    def _progress_track_width_for(self, sw: int) -> int:
        return max(PROGRESS_MIN_WIDTH, min(int(sw * 0.5), PROGRESS_MAX_WIDTH))

    def _build_scan_progress(self, sw: int):
        self._progress_track_width = self._progress_track_width_for(sw)
        bg = COLORS["idle"]

        self.progress_wrap = tk.Frame(self.content, bg=bg)
        self.progress_track = tk.Frame(
            self.progress_wrap,
            bg=COLORS["border"],
            width=self._progress_track_width,
            height=PROGRESS_HEIGHT,
        )
        self.progress_track.pack()
        self.progress_track.pack_propagate(False)

        self.progress_fill = tk.Frame(
            self.progress_track,
            bg=COLORS["accent"],
            height=PROGRESS_HEIGHT,
        )
        self.progress_fill.place(relx=0, rely=0, relheight=1, relwidth=0, anchor="nw")

    def _build_debug(self):
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
            fg=COLORS["debug_fg"],
            insertbackground=COLORS["text_on_dark"],
            relief="flat",
            bd=0,
            wrap="word",
            state="disabled",
            padx=8,
            pady=4,
        )
        self.debug_text.pack(fill="both", expand=True, padx=4, pady=(0, 6))

    def _on_resize(self, event):
        if event.widget is self:
            self.message_label.configure(wraplength=max(event.width - 48, 240))
            width = self._progress_track_width_for(event.width)
            if width != self._progress_track_width:
                self._progress_track_width = width
                self.progress_track.configure(width=width)

    def _sync_progress_colors(self, state: str, card_bg: str):
        if self._progress_mode == "hidden" and not self._progress_visible:
            return

        if state == "checking":
            wrap_bg = card_bg
            track_bg = "#4a4f56"
            fill_bg = COLORS["text_on_dark"]
        else:
            wrap_bg = card_bg
            track_bg = COLORS["border"]
            fill_bg = COLORS["accent"]

        self.progress_wrap.configure(bg=wrap_bg)
        self.progress_track.configure(bg=track_bg)
        self.progress_fill.configure(bg=fill_bg)

    def _show_progress_bar(self):
        if not self._progress_visible:
            self.progress_wrap.pack(after=self.message_label, pady=(16, 0))
            self._progress_visible = True

    def _hide_progress_bar(self):
        if self._progress_visible:
            self.progress_wrap.pack_forget()
            self._progress_visible = False

    def _set_progress_fill(self, ratio: float):
        ratio = max(0.0, min(ratio, 1.0))
        self.progress_fill.place(relx=0, rely=0, relheight=1, relwidth=ratio, anchor="nw")

    def _update_scan_progress(self):
        if self.cooldown or self._busy:
            return

        if self._state != "idle":
            return

        if not self.scan_buffer:
            if self._progress_mode == "input":
                self._progress_mode = "hidden"
                self._hide_progress_bar()
                self.message_label.configure(text=i18n.MSG_READY)
            return

        self._progress_mode = "input"
        self._show_progress_bar()
        self._sync_progress_colors("idle", COLORS["idle"])
        self.message_label.configure(text=i18n.MSG_SCANNING)
        ratio = min(len(self.scan_buffer) / SCAN_EXPECTED_LEN, SCAN_PROGRESS_CAP)
        self._set_progress_fill(ratio)

    def _complete_input_progress(self):
        self._show_progress_bar()
        self._set_progress_fill(1.0)

    def _stop_checking_progress(self):
        if self._checking_pulse_after_id is not None:
            try:
                self.after_cancel(self._checking_pulse_after_id)
            except tk.TclError:
                pass
            self._checking_pulse_after_id = None
        self._checking_pulse_step = 0
        self._progress_mode = "hidden"
        self._hide_progress_bar()

    def _start_checking_progress(self):
        self._stop_checking_progress()
        self._progress_mode = "checking"
        self._show_progress_bar()
        self._sync_progress_colors("checking", COLORS["checking"])
        self._set_progress_fill(1.0)
        self._pulse_checking_progress()

    def _pulse_checking_progress(self):
        if self._progress_mode != "checking" or self._state != "checking":
            self._checking_pulse_after_id = None
            return

        # Oscillate between 70% and 100% width.
        phase = self._checking_pulse_step % 20
        if phase <= 10:
            ratio = 0.7 + (phase / 10) * 0.3
        else:
            ratio = 1.0 - ((phase - 10) / 10) * 0.3
        self._set_progress_fill(ratio)
        self._checking_pulse_step += 1
        self._checking_pulse_after_id = self.after(
            CHECKING_PULSE_MS, self._pulse_checking_progress
        )

    def open_settings(self):
        self._show_header()
        SettingsDialog(self, self.config_data, on_save=self._on_config_saved)
        self._schedule_header_hide()

    def _on_mouse_motion(self, _event=None):
        self._show_header()
        self._schedule_header_hide()

    def _schedule_header_hide(self):
        if self._header_hide_after_id is not None:
            try:
                self.after_cancel(self._header_hide_after_id)
            except tk.TclError:
                pass
        self._header_hide_after_id = self.after(HEADER_IDLE_MS, self._hide_header)

    def _hide_header(self):
        self._header_hide_after_id = None
        if any(isinstance(w, SettingsDialog) for w in self.winfo_children()):
            # Keep chrome visible while configuring
            self._schedule_header_hide()
            return
        if self._header_visible:
            self.header.pack_forget()
            self._header_visible = False

    def _show_header(self):
        if not self._header_visible:
            self.header.pack(fill="x", side="top", before=self.card)
            self._header_visible = True

    def _on_config_saved(self, data: dict):
        self.config_data = data
        self._update_filter_label()
        self._apply_debug_visibility()
        self.reset_scanner(message=i18n.MSG_SETTINGS_SAVED)
        # Report the new settings right away instead of waiting for the next interval.
        self._send_heartbeat(self._state)

    def _update_filter_label(self):
        self.filter_label.configure(
            text=i18n.filter_caption(
                self.config_data.get("event_id") or "",
                self.config_data.get("ticket_id") or "",
            )
        )

    def _apply_debug_visibility(self):
        if self.config_data.get("debug"):
            self.debug_frame.pack(fill="x", side="bottom", padx=12, pady=(0, 8))
        else:
            self.debug_frame.pack_forget()

    def reset_scanner(self, message: str | None = None):
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
        self._stop_checking_progress()
        self._set_state("idle", i18n.TITLE_IDLE, message or i18n.MSG_RESET)
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
            if raw:
                self._complete_input_progress()
            self.scan_buffer.clear()
            self._refresh_debug_live()
            if raw:
                self._handle_scan(raw)
            else:
                self._update_scan_progress()
            return

        if event.keysym == "BackSpace":
            if self.scan_buffer:
                self.scan_buffer.pop()
                self._refresh_debug_live()
                self._update_scan_progress()
            return

        char = event.char
        if char and char.isprintable():
            self.scan_buffer.append(char)
            self._refresh_debug_live()
            self._update_scan_progress()

    def _handle_scan(self, raw: str):
        if self.cooldown or self._busy:
            self._set_debug_lines(
                [
                    f"Genegeerd (bezig): {raw!r}",
                    f"cooldown={self.cooldown} busy={self._busy}",
                ]
            )
            self._stop_checking_progress()
            return

        self.cooldown = True
        self._cooldown_after_id = self.after(COOLDOWN_MS, self._end_cooldown)
        self._last_raw = raw

        try:
            ticket = parse_qr(raw)
        except QRParseError:
            self._set_state(
                "fail",
                i18n.TITLE_DENIED,
                i18n.translate_server_message("QR code not recognised!"),
            )
            self._set_debug_lines([f"RAW: {raw}", "Parsefout: QR niet herkend"])
            play_error()
            return

        if not is_configured(self.config_data):
            self._set_state("fail", i18n.TITLE_NOT_CONFIGURED, i18n.MSG_NOT_CONFIGURED)
            self.after(500, self.open_settings)
            return

        self._busy = True
        self._set_state("checking", i18n.TITLE_CHECKING, i18n.MSG_CHECKING)
        self._set_debug_lines(
            [
                f"RAW: {raw}",
                f"Geparsed: participant_id={ticket.participant_id} seed={ticket.seed}",
                "Verzoek verzenden…",
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
            self._set_state("success", i18n.TITLE_SUCCESS, result.message)
            play_success()
        else:
            self._set_state(
                "fail",
                i18n.TITLE_DENIED,
                i18n.translate_server_message(result.message),
            )
            play_error()

    def _end_cooldown(self):
        self._cooldown_after_id = None
        self.cooldown = False
        if not self._busy and self._state in ("success", "fail"):
            self._set_state("idle", i18n.TITLE_IDLE, i18n.MSG_READY)

    def _schedule_heartbeat(self):
        self._send_heartbeat(self._state)
        self.after(HEARTBEAT_MS, self._schedule_heartbeat)

    def _send_heartbeat(self, status: str):
        if not is_configured(self.config_data):
            self._log_heartbeat(status, None)
            return
        config = dict(self.config_data)
        thread = threading.Thread(
            target=self._heartbeat_worker,
            args=(status, config),
            daemon=True,
        )
        thread.start()

    def _heartbeat_worker(self, status: str, config: dict):
        result = send_heartbeat(
            config["base_url"],
            config["api_key"],
            status,
            config,
            host_header=config.get("host_header") or "chudartz-collectibles.com",
        )
        if result.success and result.config_update:
            merged = dict(self.config_data)
            changed = False
            for key in ("event_id", "ticket_id", "debug"):
                if key in result.config_update:
                    merged[key] = result.config_update[key]
                    changed = True
            if changed:
                save_config(merged)
                self.config_data = load_config()
                config = dict(self.config_data)

                def _apply_remote_ui():
                    self._update_filter_label()
                    self._apply_debug_visibility()

                self.after(0, _apply_remote_ui)
        self.after(0, lambda: self._log_heartbeat(status, result))

    def _log_heartbeat(self, status: str, result):
        """Record the heartbeat outcome on screen and on stdout for the log file."""
        stamp = time.strftime("%H:%M:%S")
        if result is None:
            outcome = i18n.HEARTBEAT_UNCONFIGURED
            detail = ""
        elif result.success:
            outcome = i18n.HEARTBEAT_OK
            detail = f" -> {result.url}"
        else:
            outcome = i18n.HEARTBEAT_FAILED
            detail = f" -> {result.url}"
            if result.error:
                detail += f" ({result.error})"
        self._last_heartbeat = f"{stamp} {status} {outcome}"
        self.debug_header.configure(
            text=f"DEBUG — {i18n.HEARTBEAT_LABEL}: {self._last_heartbeat}"
        )
        print(f"[{stamp}] heartbeat status={status} result={outcome}{detail}", flush=True)

    def _set_state(self, state: str, title: str, message: str):
        if state != self._state:
            self._send_heartbeat(state)
        self._state = state
        if state == "success":
            color = COLORS["success"]
            fg = COLORS["text_on_dark"]
            msg_fg = COLORS["text_on_dark"]
            bar = COLORS["success"]
        elif state == "fail":
            color = COLORS["fail"]
            fg = COLORS["text_on_dark"]
            msg_fg = COLORS["text_on_dark"]
            bar = COLORS["fail"]
        elif state == "checking":
            color = COLORS["checking"]
            fg = COLORS["text_on_dark"]
            msg_fg = "#cfd4da"
            bar = COLORS["accent"]
        else:
            color = COLORS["idle"]
            fg = COLORS["text"]
            msg_fg = COLORS["muted"]
            bar = COLORS["accent"]

        self.configure(bg=color)
        self.card.configure(bg=color)
        self.content.configure(bg=color)
        self.accent_bar.configure(bg=bar)
        self.status_label.configure(text=title, fg=fg, bg=color)
        self.message_label.configure(text=message, fg=msg_fg, bg=color)

        if state == "checking":
            self._start_checking_progress()
        elif state in ("success", "fail", "idle"):
            self._stop_checking_progress()
        elif self._progress_mode == "input":
            self._sync_progress_colors(state, color)

    def _refresh_debug_live(self):
        if not self.config_data.get("debug"):
            return
        buf = "".join(self.scan_buffer)
        lines = [
            f"BUFFER ({len(self.scan_buffer)}): {buf!r}",
            f"state={self._state} cooldown={self.cooldown} busy={self._busy}",
        ]
        if self._last_raw:
            lines.append(f"LAATSTE RAW: {self._last_raw}")
        self._set_debug_lines(lines)

    def _set_debug_lines(self, lines: list[str]):
        self.debug_text.configure(state="normal")
        self.debug_text.delete("1.0", "end")
        self.debug_text.insert("1.0", "\n".join(lines))
        self.debug_text.configure(state="disabled")
        self.debug_text.see("end")
