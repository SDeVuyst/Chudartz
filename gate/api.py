"""HTTP client for the Django gate check-in endpoint."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass


@dataclass(frozen=True)
class CheckInResult:
    success: bool
    message: str
    status_code: int


def check_in(
    base_url: str,
    api_key: str,
    participant_id: int,
    seed: str,
    host_header: str = "chudartz-collectibles.com",
    timeout: float = 10.0,
) -> CheckInResult:
    url = base_url.rstrip("/") + "/en/pokemon/gate/check-in/"
    body = json.dumps(
        {"participant_id": participant_id, "seed": seed}
    ).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "X-Gate-Api-Key": api_key,
        "Accept": "application/json",
    }
    if host_header:
        headers["Host"] = host_header
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers=headers,
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            status = response.getcode()
            data = _parse_json(raw)
            return CheckInResult(
                success=bool(data.get("success")),
                message=str(data.get("message") or "OK"),
                status_code=status,
            )
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        data = _parse_json(raw)
        return CheckInResult(
            success=False,
            message=str(data.get("message") or f"HTTP {exc.code}"),
            status_code=exc.code,
        )
    except urllib.error.URLError as exc:
        return CheckInResult(
            success=False,
            message=f"Network error: {exc.reason}",
            status_code=0,
        )
    except TimeoutError:
        return CheckInResult(
            success=False,
            message="Request timed out",
            status_code=0,
        )


def _parse_json(raw: str) -> dict:
    try:
        data = json.loads(raw) if raw else {}
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}
