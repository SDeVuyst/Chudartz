#!/usr/bin/env python3
"""Chudartz Raspberry Pi ticket gate scanner."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api import check_in
from config import (
    DEFAULT_BASE_URL,
    DEFAULT_HOST_HEADER,
    config_path,
    is_configured,
    load_config,
    save_config,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Chudartz gate scanner (USB QR wedge + fullscreen feedback).",
    )
    parser.add_argument(
        "--configure",
        action="store_true",
        help="Write config from flags / prompts and exit (SSH-friendly).",
    )
    parser.add_argument(
        "--show-config",
        action="store_true",
        help="Print current config path and values (API key redacted) and exit.",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="POST a dry check-in probe to verify URL + API key, then exit.",
    )
    parser.add_argument("--base-url", help="API base URL (no trailing slash required).")
    parser.add_argument("--api-key", help="Gate device API key from Django admin.")
    parser.add_argument(
        "--host-header",
        help=f"HTTP Host header (default: {DEFAULT_HOST_HEADER}).",
    )
    return parser


def _redact_key(key: str) -> str:
    if not key:
        return "(empty)"
    if len(key) <= 8:
        return "********"
    return f"{key[:4]}...{key[-4:]} ({len(key)} chars)"


def cmd_show_config() -> int:
    cfg = load_config()
    print(f"Config file: {config_path()}")
    print(f"base_url:    {cfg.get('base_url')}")
    print(f"host_header: {cfg.get('host_header')}")
    print(f"api_key:     {_redact_key(cfg.get('api_key') or '')}")
    print(f"configured:  {is_configured(cfg)}")
    return 0


def cmd_configure(args: argparse.Namespace) -> int:
    cfg = load_config()
    base_url = args.base_url
    api_key = args.api_key
    host_header = args.host_header

    if base_url is None and sys.stdin.isatty():
        current = cfg.get("base_url") or DEFAULT_BASE_URL
        entered = input(f"API base URL [{current}]: ").strip()
        base_url = entered or current
    if host_header is None and sys.stdin.isatty():
        current = cfg.get("host_header") or DEFAULT_HOST_HEADER
        entered = input(f"Host header [{current}]: ").strip()
        host_header = entered or current
    if api_key is None and sys.stdin.isatty():
        entered = input("Device API key: ").strip()
        api_key = entered or cfg.get("api_key") or ""

    if base_url is None:
        base_url = cfg.get("base_url") or DEFAULT_BASE_URL
    if host_header is None:
        host_header = cfg.get("host_header") or DEFAULT_HOST_HEADER
    if api_key is None:
        api_key = cfg.get("api_key") or ""

    if not base_url:
        print("Error: --base-url is required (or use interactive --configure).", file=sys.stderr)
        return 1
    if not api_key:
        print("Error: --api-key is required (or use interactive --configure).", file=sys.stderr)
        return 1

    save_config(
        {
            "base_url": base_url,
            "api_key": api_key,
            "host_header": host_header,
        }
    )
    print(f"Saved config to {config_path()}")
    return 0


def cmd_test() -> int:
    cfg = load_config()
    if not is_configured(cfg):
        print("Error: not configured. Run with --configure first.", file=sys.stderr)
        return 1

    # Invalid ids exercise auth + reachability without marking attendance.
    result = check_in(
        cfg["base_url"],
        cfg["api_key"],
        participant_id=0,
        seed="test",
        host_header=cfg.get("host_header") or DEFAULT_HOST_HEADER,
    )
    print(f"HTTP status: {result.status_code}")
    print(f"success:     {result.success}")
    print(f"message:     {result.message}")

    if result.status_code == 401:
        print("API key rejected (Unauthorized).", file=sys.stderr)
        return 1
    if result.status_code == 0:
        print("Could not reach the server.", file=sys.stderr)
        return 1
    # 400/404 from bogus participant means URL + key worked.
    print("Connection and API key look OK.")
    return 0


def cmd_run() -> int:
    from ui.app import GateApp

    app = GateApp()
    app.mainloop()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.show_config:
        return cmd_show_config()

    if args.configure or args.base_url or args.api_key or args.host_header:
        # Allow one-shot: python3 main.py --base-url … --api-key … --configure
        if args.configure or (args.base_url and args.api_key):
            code = cmd_configure(args)
            if code != 0:
                return code
            if args.configure and not args.test:
                return 0
        elif args.base_url or args.api_key or args.host_header:
            print(
                "Error: pass --configure together with --base-url / --api-key "
                "(and optional --host-header).",
                file=sys.stderr,
            )
            return 1

    if args.test:
        return cmd_test()

    return cmd_run()


if __name__ == "__main__":
    raise SystemExit(main())
