"""Fullscreen gate UI — ChudartZ Collectibles branding, Nederlands."""

from __future__ import annotations

import json
import threading
import tkinter as tk
from pathlib import Path
from tkinter import font as tkfont

from api import check_in
from config import is_configured, load_config, optional_id
from parse_qr import QRParseError, parse_qr
from ui import i18n
from ui.settings import SettingsDialog

COOLDOWN_MS = 4000
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

        self._build_header()
        self._build_card(sw)
        self._build_debug()

        self._update_filter_label()
        self._apply_debug_visibility()
        self._set_debug_lines([i18n.DEBUG_WAITING])

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
        outer = tk.Frame(self, bg=COLORS["bg"])
        outer.pack(fill="both", expand=True, padx=12, pady=12)

        self.card = tk.Frame(
            outer,
            bg=COLORS["idle"],
            highlightbackground=COLORS["border"],
            highlightthickness=1,
        )
        self.card.pack(fill="both", expand=True)

        self.accent_bar = tk.Frame(self.card, bg=COLORS["accent"], height=4)
        self.accent_bar.pack(fill="x", side="top")

        self.status_label = tk.Label(
            self.card,
            text=i18n.TITLE_IDLE,
            font=self.title_font,
            fg=COLORS["text"],
            bg=COLORS["idle"],
        )
        self.status_label.pack(expand=True, pady=(24, 6))

        self.message_label = tk.Label(
            self.card,
            text=i18n.MSG_READY,
            font=self.message_font,
            fg=COLORS["muted"],
            bg=COLORS["idle"],
            wraplength=max(sw - 64, 260),
            justify="center",
        )
        self.message_label.pack(pady=(0, 28), padx=16)

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
            self.message_label.configure(wraplength=max(event.width - 64, 240))

    def open_settings(self):
        SettingsDialog(self, self.config_data, on_save=self._on_config_saved)

    def _on_config_saved(self, data: dict):
        self.config_data = data
        self._update_filter_label()
        self._apply_debug_visibility()
        self.reset_scanner(message=i18n.MSG_SETTINGS_SAVED)

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
                    f"Genegeerd (bezig): {raw!r}",
                    f"cooldown={self.cooldown} busy={self._busy}",
                ]
            )
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
            self.bell()
        else:
            self._set_state(
                "fail",
                i18n.TITLE_DENIED,
                i18n.translate_server_message(result.message),
            )

    def _end_cooldown(self):
        self._cooldown_after_id = None
        self.cooldown = False
        if not self._busy and self._state in ("success", "fail"):
            self._set_state("idle", i18n.TITLE_IDLE, i18n.MSG_READY)

    def _set_state(self, state: str, title: str, message: str):
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

        self.card.configure(bg=color)
        self.accent_bar.configure(bg=bar)
        self.status_label.configure(text=title, fg=fg, bg=color)
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
            lines.append(f"LAATSTE RAW: {self._last_raw}")
        self._set_debug_lines(lines)

    def _set_debug_lines(self, lines: list[str]):
        self.debug_text.configure(state="normal")
        self.debug_text.delete("1.0", "end")
        self.debug_text.insert("1.0", "\n".join(lines))
        self.debug_text.configure(state="disabled")
        self.debug_text.see("end")
