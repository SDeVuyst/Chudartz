"""Fullscreen gate UI: idle / success / fail + keyboard-wedge capture."""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import font as tkfont

from api import check_in
from config import is_configured, load_config
from parse_qr import QRParseError, parse_qr
from ui.settings import SettingsDialog

COOLDOWN_MS = 4000

COLORS = {
    "idle": "#1a2332",
    "success": "#1b7a3d",
    "fail": "#a61e2c",
    "text": "#ffffff",
    "muted": "#c5cdd8",
}


class GateApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Chudartz Gate")
        self.config_data = load_config()
        self.scan_buffer = []
        self.cooldown = False
        self._busy = False

        self.attributes("-fullscreen", True)
        self.configure(bg=COLORS["idle"])
        self.bind("<Key>", self._on_key)
        self.bind("<F2>", lambda _e: self.open_settings())
        self.bind("<Escape>", self._on_escape)
        self.bind("<Control-comma>", lambda _e: self.open_settings())

        self.title_font = tkfont.Font(family="DejaVu Sans", size=48, weight="bold")
        self.message_font = tkfont.Font(family="DejaVu Sans", size=28)
        self.hint_font = tkfont.Font(family="DejaVu Sans", size=16)

        self.status_label = tk.Label(
            self,
            text="Scan ticket",
            font=self.title_font,
            fg=COLORS["text"],
            bg=COLORS["idle"],
        )
        self.status_label.pack(expand=True)

        self.message_label = tk.Label(
            self,
            text="Ready",
            font=self.message_font,
            fg=COLORS["muted"],
            bg=COLORS["idle"],
            wraplength=900,
            justify="center",
        )
        self.message_label.pack(pady=(0, 40))

        self.hint_label = tk.Label(
            self,
            text="F2 = settings   Esc = exit fullscreen",
            font=self.hint_font,
            fg=COLORS["muted"],
            bg=COLORS["idle"],
        )
        self.hint_label.pack(side="bottom", pady=24)

        if not is_configured(self.config_data):
            self.after(200, self.open_settings)

    def open_settings(self):
        SettingsDialog(self, self.config_data, on_save=self._on_config_saved)

    def _on_config_saved(self, data: dict):
        self.config_data = data
        self._set_state("idle", "Scan ticket", "Settings saved")

    def _on_escape(self, _event=None):
        if self.attributes("-fullscreen"):
            self.attributes("-fullscreen", False)
            self.geometry("1024x600")
        else:
            self.destroy()

    def _on_key(self, event: tk.Event):
        # Ignore shortcuts handled elsewhere
        if event.keysym in ("F2", "Escape"):
            return
        if event.state & 0x4 and event.keysym == "comma":  # Ctrl+,
            return

        # While settings dialog is open, don't capture wedge input on root
        if any(isinstance(w, SettingsDialog) for w in self.winfo_children()):
            return

        if event.keysym == "Return":
            raw = "".join(self.scan_buffer)
            self.scan_buffer.clear()
            if raw:
                self._handle_scan(raw)
            return

        if event.keysym == "BackSpace":
            if self.scan_buffer:
                self.scan_buffer.pop()
            return

        char = event.char
        if char and char.isprintable():
            self.scan_buffer.append(char)

    def _handle_scan(self, raw: str):
        if self.cooldown or self._busy:
            return

        self.cooldown = True
        self.after(COOLDOWN_MS, self._end_cooldown)

        try:
            ticket = parse_qr(raw)
        except QRParseError as exc:
            self._set_state("fail", "Access denied", str(exc))
            return

        if not is_configured(self.config_data):
            self._set_state("fail", "Not configured", "Open settings (F2) and set URL + API key")
            self.after(500, self.open_settings)
            return

        self._busy = True
        self._set_state("idle", "Checking…", "Please wait")

        thread = threading.Thread(
            target=self._check_in_worker,
            args=(ticket.participant_id, ticket.seed),
            daemon=True,
        )
        thread.start()

    def _check_in_worker(self, participant_id: int, seed: str):
        result = check_in(
            self.config_data["base_url"],
            self.config_data["api_key"],
            participant_id,
            seed,
            host_header=self.config_data.get("host_header") or "chudartz-collectibles.com",
        )
        self.after(0, lambda: self._on_check_in_done(result))

    def _on_check_in_done(self, result):
        self._busy = False
        if result.success:
            self._set_state("success", "Welcome", result.message)
            self.bell()
        else:
            self._set_state("fail", "Access denied", result.message)

    def _end_cooldown(self):
        self.cooldown = False
        if not self._busy:
            self._set_state("idle", "Scan ticket", "Ready")

    def _set_state(self, state: str, title: str, message: str):
        color = COLORS.get(state, COLORS["idle"])
        self.configure(bg=color)
        for widget in (self.status_label, self.message_label, self.hint_label):
            widget.configure(bg=color)
        self.status_label.configure(text=title, fg=COLORS["text"])
        msg_fg = COLORS["text"] if state != "idle" else COLORS["muted"]
        self.message_label.configure(text=message, fg=msg_fg)
        hint_fg = COLORS["muted"] if state == "idle" else COLORS["text"]
        self.hint_label.configure(fg=hint_fg)
