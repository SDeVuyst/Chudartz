"""Local config for the gate scanner (API URL + device key)."""

from __future__ import annotations

import json
import os
from pathlib import Path

DEFAULT_BASE_URL = "https://chudartz-collectibles.com"
DEFAULT_HOST_HEADER = "chudartz-collectibles.com"
DEFAULT_CONFIG = {
    "base_url": DEFAULT_BASE_URL,
    "api_key": "",
    # Required when base_url is an IP/localhost so Django routes to pokemon.urls
    "host_header": DEFAULT_HOST_HEADER,
    # Optional filters — empty means accept any event/ticket type
    "event_id": "",
    "ticket_id": "",
    "debug": False,
}


def config_path() -> Path:
    override = os.environ.get("CHUDARTZ_GATE_CONFIG")
    if override:
        return Path(override)
    return Path.home() / ".config" / "chudartz-gate" / "config.json"


def _normalize_optional_id(value) -> str:
    if value is None or value == "":
        return ""
    return str(int(value))


def _normalize_debug(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return bool(value)


def load_config() -> dict:
    path = config_path()
    if not path.is_file():
        return dict(DEFAULT_CONFIG)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return dict(DEFAULT_CONFIG)
    merged = dict(DEFAULT_CONFIG)
    for key in DEFAULT_CONFIG:
        if key not in data:
            continue
        if key == "debug":
            merged[key] = _normalize_debug(data[key])
        elif key in ("event_id", "ticket_id"):
            try:
                merged[key] = _normalize_optional_id(data[key]) if data[key] not in (None, "") else ""
            except (TypeError, ValueError):
                merged[key] = ""
        else:
            merged[key] = data[key]
    return merged


def save_config(data: dict) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    event_id = data.get("event_id", "")
    ticket_id = data.get("ticket_id", "")
    try:
        event_id = _normalize_optional_id(event_id) if event_id not in (None, "") else ""
    except (TypeError, ValueError):
        event_id = ""
    try:
        ticket_id = _normalize_optional_id(ticket_id) if ticket_id not in (None, "") else ""
    except (TypeError, ValueError):
        ticket_id = ""

    payload = {
        "base_url": (data.get("base_url") or DEFAULT_BASE_URL).rstrip("/"),
        "api_key": data.get("api_key") or "",
        "host_header": (data.get("host_header") or DEFAULT_HOST_HEADER).strip(),
        "event_id": event_id,
        "ticket_id": ticket_id,
        "debug": _normalize_debug(data.get("debug", False)),
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def is_configured(data: dict | None = None) -> bool:
    cfg = data if data is not None else load_config()
    return bool(cfg.get("base_url") and cfg.get("api_key"))


def optional_id(cfg: dict, key: str):
    value = cfg.get(key)
    if value in (None, ""):
        return None
    return int(value)
