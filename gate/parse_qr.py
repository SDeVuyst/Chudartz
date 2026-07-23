"""Parse ticket QR payloads produced by Participant.generate_qr_code()."""

from __future__ import annotations

import re
from dataclasses import dataclass


class QRParseError(ValueError):
    pass


@dataclass(frozen=True)
class TicketQR:
    participant_id: int
    seed: str


_PARTICIPANT_RE = re.compile(r"participant_id:(\d+)")


def parse_qr(raw: str) -> TicketQR:
    text = (raw or "").strip()
    if not text:
        raise QRParseError("QR code not recognised!")

    match = _PARTICIPANT_RE.search(text)
    if not match:
        raise QRParseError("QR code not recognised!")

    keyword = "seed:"
    start = text.find(keyword)
    if start == -1:
        raise QRParseError("QR code not recognised!")

    seed = text[start + len(keyword) :].strip()
    if not seed:
        raise QRParseError("QR code not recognised!")

    return TicketQR(participant_id=int(match.group(1)), seed=seed)
