from django.urls import reverse

from gate.parse_qr import QRParseError, parse_qr
from pokemon.models import Participant, PaymentStatus


class AttendanceError(Exception):
    def __init__(
        self,
        message: str,
        status: int = 400,
        *,
        admin_url: str | None = None,
        participant_id=None,
    ):
        self.message = message
        self.status = status
        self.admin_url = admin_url
        self.participant_id = participant_id
        super().__init__(message)


def _optional_int(value):
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        raise AttendanceError("Ongeldig evenement- of ticketnummer.")


def _participant_admin_url(participant_id) -> str:
    return reverse("admin:pokemon_participant_change", args=[participant_id])


def lookup_participant(participant_id, seed) -> dict:
    """Resolve a QR payload to a participant admin URL without marking attendance.

    Returns admin_url and non-blocking warning messages for unpaid / wrong seed /
    already attended. Raises AttendanceError if the participant cannot be found.
    """
    if seed is None or seed == "":
        raise AttendanceError("QR-code niet herkend. Probeer opnieuw te scannen.")

    if participant_id is None:
        raise AttendanceError("Deelnemer niet gevonden voor deze QR-code.", status=404)

    try:
        participant = Participant.objects.select_related(
            "payment", "ticket", "ticket__event"
        ).get(pk=participant_id)
    except (Participant.DoesNotExist, ValueError, TypeError):
        raise AttendanceError("Deelnemer niet gevonden voor deze QR-code.", status=404)

    warnings: list[str] = []

    if participant.payment is None or participant.payment.status != PaymentStatus.PAID:
        warnings.append("Dit ticket is nog niet betaald.")

    if seed != participant.random_seed:
        warnings.append("Deze QR-code is ongeldig of gewijzigd.")

    if participant.attended:
        warnings.append("Dit ticket is al gebruikt.")

    return {
        "participant_id": participant.pk,
        "admin_url": _participant_admin_url(participant.pk),
        "warnings": warnings,
    }


def lookup_raw_qr(raw: str) -> dict:
    """Parse raw scanner input with the same gate parser, then look up the participant."""
    try:
        ticket = parse_qr(raw)
    except QRParseError:
        raise AttendanceError("QR-code niet herkend. Probeer opnieuw te scannen.")

    return lookup_participant(ticket.participant_id, ticket.seed)


def check_in_raw_qr(raw: str) -> dict:
    """Parse raw scanner input and mark the participant as attended (gate-style hard checks)."""
    try:
        ticket = parse_qr(raw)
    except QRParseError:
        raise AttendanceError("QR-code niet herkend. Probeer opnieuw te scannen.")

    return check_in_participant(ticket.participant_id, ticket.seed)


def check_in_participant(participant_id, seed, *, event_id=None, ticket_id=None) -> dict:
    """Validate QR payload and mark the participant as attended.

    Optional event_id / ticket_id restrict which tickets this gate accepts.
    Returns a success dict with message/ticket, or raises AttendanceError.
    """
    if participant_id is None or seed is None or seed == "":
        raise AttendanceError("QR-code niet herkend. Probeer opnieuw te scannen.")

    required_event_id = _optional_int(event_id)
    required_ticket_id = _optional_int(ticket_id)

    try:
        participant = Participant.objects.select_related(
            "payment", "ticket", "ticket__event"
        ).get(pk=participant_id)
    except (Participant.DoesNotExist, ValueError, TypeError):
        raise AttendanceError("QR-code niet herkend. Probeer opnieuw te scannen.", status=404)

    admin_url = _participant_admin_url(participant.pk)

    def _reject(message: str, status: int = 400):
        raise AttendanceError(
            message,
            status,
            admin_url=admin_url,
            participant_id=participant.pk,
        )

    if participant.payment is None or participant.payment.status != PaymentStatus.PAID:
        _reject("Dit ticket is nog niet betaald.")

    if seed != participant.random_seed:
        _reject("Deze QR-code is ongeldig of gewijzigd.")

    if required_event_id is not None and participant.ticket.event_id != required_event_id:
        _reject("Dit ticket hoort niet bij dit evenement.")

    if required_ticket_id is not None and participant.ticket_id != required_ticket_id:
        _reject("Dit is niet het juiste tickettype voor deze ingang.")

    if participant.attended:
        _reject("Dit ticket is al gebruikt.")

    participant.attended = True
    participant.save(update_fields=["attended"])

    ticket_str = str(participant.ticket)
    return {
        "success": True,
        "message": ticket_str,
        "ticket": ticket_str,
        "ticket_id": participant.ticket_id,
        "event_id": participant.ticket.event_id,
        "event": str(participant.ticket.event),
        "participant_id": participant.pk,
        "admin_url": admin_url,
    }
