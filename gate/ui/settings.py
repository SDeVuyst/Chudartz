"""Settings dialog for gate configuration."""

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

        frame = ttk.Frame(self, padding=14)
        frame.grid(row=0, column=0, sticky="nsew")

        row = 0

        ttk.Label(frame, text="API base URL").grid(row=row, column=0, sticky="w")
        row += 1
        self.url_var = tk.StringVar(value=config.get("base_url") or DEFAULT_BASE_URL)
        ttk.Entry(frame, textvariable=self.url_var, width=44).grid(
            row=row, column=0, sticky="ew", pady=(2, 8)
        )
        row += 1

        ttk.Label(frame, text="Host header").grid(row=row, column=0, sticky="w")
        row += 1
        self.host_var = tk.StringVar(
            value=config.get("host_header") or DEFAULT_HOST_HEADER
        )
        ttk.Entry(frame, textvariable=self.host_var, width=44).grid(
            row=row, column=0, sticky="ew", pady=(2, 8)
        )
        row += 1

        ttk.Label(frame, text="Device API key").grid(row=row, column=0, sticky="w")
        row += 1
        self.key_var = tk.StringVar(value=config.get("api_key") or "")
        ttk.Entry(frame, textvariable=self.key_var, width=44, show="•").grid(
            row=row, column=0, sticky="ew", pady=(2, 8)
        )
        row += 1

        ids = ttk.Frame(frame)
        ids.grid(row=row, column=0, sticky="ew", pady=(4, 8))
        ids.columnconfigure(0, weight=1)
        ids.columnconfigure(1, weight=1)

        ttk.Label(ids, text="Event ID (optional)").grid(row=0, column=0, sticky="w")
        ttk.Label(ids, text="Ticket ID (optional)").grid(row=0, column=1, sticky="w", padx=(8, 0))
        self.event_var = tk.StringVar(value=str(config.get("event_id") or ""))
        self.ticket_var = tk.StringVar(value=str(config.get("ticket_id") or ""))
        ttk.Entry(ids, textvariable=self.event_var, width=16).grid(
            row=1, column=0, sticky="ew", pady=(2, 0)
        )
        ttk.Entry(ids, textvariable=self.ticket_var, width=16).grid(
            row=1, column=1, sticky="ew", padx=(8, 0), pady=(2, 0)
        )
        row += 1

        ttk.Label(
            frame,
            text="Leave blank to accept any. Set event and/or ticket ID to lock this gate.",
            foreground="#666",
            wraplength=360,
        ).grid(row=row, column=0, sticky="w", pady=(0, 10))
        row += 1

        self.debug_var = tk.BooleanVar(value=bool(config.get("debug")))
        ttk.Checkbutton(
            frame,
            text="Debug mode (show scan buffer + request/response)",
            variable=self.debug_var,
        ).grid(row=row, column=0, sticky="w", pady=(0, 12))
        row += 1

        buttons = ttk.Frame(frame)
        buttons.grid(row=row, column=0, sticky="e")
        ttk.Button(buttons, text="Cancel", command=self.destroy).pack(
            side="right", padx=(8, 0)
        )
        ttk.Button(buttons, text="Save", command=self._save).pack(side="right")

        self.bind("<Escape>", lambda _e: self.destroy())
        self.protocol("WM_DELETE_WINDOW", self.destroy)
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
        event_id = self.event_var.get().strip()
        ticket_id = self.ticket_var.get().strip()

        if not base_url:
            messagebox.showerror("Settings", "API base URL is required.", parent=self)
            return
        if not api_key:
            messagebox.showerror("Settings", "Device API key is required.", parent=self)
            return
        for label, value in (("Event ID", event_id), ("Ticket ID", ticket_id)):
            if value == "":
                continue
            try:
                int(value)
            except ValueError:
                messagebox.showerror(
                    "Settings", f"{label} must be a number (or blank).", parent=self
                )
                return

        data = {
            "base_url": base_url,
            "host_header": host_header,
            "api_key": api_key,
            "event_id": event_id,
            "ticket_id": ticket_id,
            "debug": bool(self.debug_var.get()),
        }
        save_config(data)
        if self.on_save:
            self.on_save(data)
        self.destroy()
