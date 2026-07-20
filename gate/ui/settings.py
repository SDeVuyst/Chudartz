"""Settings dialog for API base URL and device API key."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from config import DEFAULT_BASE_URL, DEFAULT_HOST_HEADER, save_config


class SettingsDialog(tk.Toplevel):
    def __init__(self, master, config: dict, on_save=None):
        super().__init__(master)
        self.title("Gate settings")
        self.on_save = on_save
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        frame = ttk.Frame(self, padding=16)
        frame.grid(row=0, column=0, sticky="nsew")

        ttk.Label(frame, text="API base URL").grid(row=0, column=0, sticky="w")
        self.url_var = tk.StringVar(value=config.get("base_url") or DEFAULT_BASE_URL)
        url_entry = ttk.Entry(frame, textvariable=self.url_var, width=48)
        url_entry.grid(row=1, column=0, sticky="ew", pady=(4, 12))

        ttk.Label(
            frame,
            text="Example: https://chudartz-collectibles.com  or  http://192.168.x.x:81",
            foreground="#666",
        ).grid(row=2, column=0, sticky="w", pady=(0, 12))

        ttk.Label(frame, text="Host header").grid(row=3, column=0, sticky="w")
        self.host_var = tk.StringVar(
            value=config.get("host_header") or DEFAULT_HOST_HEADER
        )
        host_entry = ttk.Entry(frame, textvariable=self.host_var, width=48)
        host_entry.grid(row=4, column=0, sticky="ew", pady=(4, 4))

        ttk.Label(
            frame,
            text="Keep chudartz-collectibles.com when using a LAN IP / localhost URL.",
            foreground="#666",
        ).grid(row=5, column=0, sticky="w", pady=(0, 12))

        ttk.Label(frame, text="Device API key").grid(row=6, column=0, sticky="w")
        self.key_var = tk.StringVar(value=config.get("api_key") or "")
        key_entry = ttk.Entry(frame, textvariable=self.key_var, width=48, show="•")
        key_entry.grid(row=7, column=0, sticky="ew", pady=(4, 16))

        buttons = ttk.Frame(frame)
        buttons.grid(row=8, column=0, sticky="e")
        ttk.Button(buttons, text="Cancel", command=self.destroy).pack(side="right", padx=(8, 0))
        ttk.Button(buttons, text="Save", command=self._save).pack(side="right")

        self.bind("<Escape>", lambda _e: self.destroy())
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        url_entry.focus_set()

        self.update_idletasks()
        self._center()

    def _center(self):
        self.update_idletasks()
        w = self.winfo_width()
        h = self.winfo_height()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"+{(sw - w) // 2}+{(sh - h) // 2}")

    def _save(self):
        base_url = self.url_var.get().strip().rstrip("/")
        host_header = self.host_var.get().strip() or DEFAULT_HOST_HEADER
        api_key = self.key_var.get().strip()
        if not base_url:
            messagebox.showerror("Settings", "API base URL is required.", parent=self)
            return
        if not api_key:
            messagebox.showerror("Settings", "Device API key is required.", parent=self)
            return
        data = {
            "base_url": base_url,
            "host_header": host_header,
            "api_key": api_key,
        }
        save_config(data)
        if self.on_save:
            self.on_save(data)
        self.destroy()
