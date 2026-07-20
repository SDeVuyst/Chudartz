from pokemon.models import Participant, PaymentStatus


class AttendanceError(Exception):
    def __init__(self, message: str, status: int = 400):
        self.message = message
        self.status = status
        super().__init__(message)


def _optional_int(value):
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        raise AttendanceError("Invalid event_id or ticket_id.")


def check_in_participant(participant_id, seed, *, event_id=None, ticket_id=None) -> dict:
    """Validate QR payload and mark the participant as attended.

    Optional event_id / ticket_id restrict which tickets this gate accepts.
    Returns a success dict with message/ticket, or raises AttendanceError.
    """
    if participant_id is None or seed is None or seed == "":
        raise AttendanceError("QR code not recognised!")

    required_event_id = _optional_int(event_id)
    required_ticket_id = _optional_int(ticket_id)

    try:
        participant = Participant.objects.select_related(
            "payment", "ticket", "ticket__event"
        ).get(pk=participant_id)
    except (Participant.DoesNotExist, ValueError, TypeError):
        raise AttendanceError("QR code not recognised!", status=404)

    if participant.payment is None or participant.payment.status != PaymentStatus.PAID:
        raise AttendanceError("Fraud Detected! Customer has not payed yet.")

    if seed != participant.random_seed:
        raise AttendanceError("Fraud Detected! QR code has been tampered with.")

    if required_event_id is not None and participant.ticket.event_id != required_event_id:
        raise AttendanceError("Wrong event for this entrance!")

    if required_ticket_id is not None and participant.ticket_id != required_ticket_id:
        raise AttendanceError("Wrong ticket type for this entrance!")

    if participant.attended:
        raise AttendanceError("Participant already attended!")

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
    }
