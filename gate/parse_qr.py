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
_SEED_LEN = 10


def _parse_legacy(text: str) -> TicketQR:
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


def _parse_compact(text: str) -> TicketQR:
    if len(text) < _SEED_LEN + 1:
        raise QRParseError("QR code not recognised!")

    seed = text[-_SEED_LEN:]
    id_part = text[:-_SEED_LEN]
    if not id_part.isdigit() or not seed.isalnum():
        raise QRParseError("QR code not recognised!")

    return TicketQR(participant_id=int(id_part), seed=seed)


def parse_qr(raw: str) -> TicketQR:
    text = (raw or "").strip()
    if not text:
        raise QRParseError("QR code not recognised!")

    if "participant_id:" in text:
        return _parse_legacy(text)

    return _parse_compact(text)
