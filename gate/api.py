"""HTTP client for the Django gate check-in endpoint."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field


@dataclass(frozen=True)
class CheckInResult:
    success: bool
    message: str
    status_code: int
    request_url: str = ""
    request_body: dict = field(default_factory=dict)
    response_body: dict = field(default_factory=dict)


def check_in(
    base_url: str,
    api_key: str,
    participant_id: int,
    seed: str,
    host_header: str = "chudartz-collectibles.com",
    event_id=None,
    ticket_id=None,
    timeout: float = 10.0,
) -> CheckInResult:
    url = base_url.rstrip("/") + "/en/pokemon/gate/check-in/"
    payload = {
        "participant_id": participant_id,
        "seed": seed,
    }
    if event_id is not None:
        payload["event_id"] = int(event_id)
    if ticket_id is not None:
        payload["ticket_id"] = int(ticket_id)

    body = json.dumps(payload).encode("utf-8")
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
                request_url=url,
                request_body=payload,
                response_body=data,
            )
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        data = _parse_json(raw)
        return CheckInResult(
            success=False,
            message=str(data.get("message") or f"HTTP {exc.code}"),
            status_code=exc.code,
            request_url=url,
            request_body=payload,
            response_body=data,
        )
    except urllib.error.URLError as exc:
        reason = exc.reason
        message = f"Network error: {reason}"
        reason_text = str(reason)
        if "WRONG_VERSION_NUMBER" in reason_text or "SSL" in reason_text:
            if base_url.lower().startswith("https://"):
                message += (
                    " — server is not speaking TLS. "
                    "For local Docker/nginx use http:// (not https://), e.g. http://192.168.x.x:81"
                )
        return CheckInResult(
            success=False,
            message=message,
            status_code=0,
            request_url=url,
            request_body=payload,
            response_body={},
        )
    except TimeoutError:
        return CheckInResult(
            success=False,
            message="Request timed out",
            status_code=0,
            request_url=url,
            request_body=payload,
            response_body={},
        )


def _parse_json(raw: str) -> dict:
    try:
        data = json.loads(raw) if raw else {}
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}
