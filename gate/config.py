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
}


def config_path() -> Path:
    override = os.environ.get("CHUDARTZ_GATE_CONFIG")
    if override:
        return Path(override)
    return Path.home() / ".config" / "chudartz-gate" / "config.json"


def load_config() -> dict:
    path = config_path()
    if not path.is_file():
        return dict(DEFAULT_CONFIG)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return dict(DEFAULT_CONFIG)
    merged = dict(DEFAULT_CONFIG)
    merged.update({k: v for k, v in data.items() if k in DEFAULT_CONFIG})
    return merged


def save_config(data: dict) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "base_url": (data.get("base_url") or DEFAULT_BASE_URL).rstrip("/"),
        "api_key": data.get("api_key") or "",
        "host_header": (data.get("host_header") or DEFAULT_HOST_HEADER).strip(),
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def is_configured(data: dict | None = None) -> bool:
    cfg = data if data is not None else load_config()
    return bool(cfg.get("base_url") and cfg.get("api_key"))
