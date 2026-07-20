from pokemon.models import Participant, PaymentStatus


class AttendanceError(Exception):
    def __init__(self, message: str, status: int = 400):
        self.message = message
        self.status = status
        super().__init__(message)


def check_in_participant(participant_id, seed) -> dict:
    """Validate QR payload and mark the participant as attended.

    Returns a success dict with message/ticket, or raises AttendanceError.
    """
    if participant_id is None or seed is None or seed == "":
        raise AttendanceError("QR code not recognised!")

    try:
        participant = Participant.objects.select_related("payment", "ticket").get(
            pk=participant_id
        )
    except (Participant.DoesNotExist, ValueError, TypeError):
        raise AttendanceError("QR code not recognised!", status=404)

    if participant.payment is None or participant.payment.status != PaymentStatus.PAID:
        raise AttendanceError("Fraud Detected! Customer has not payed yet.")

    if seed != participant.random_seed:
        raise AttendanceError("Fraud Detected! QR code has been tampered with.")

    if participant.attended:
        raise AttendanceError("Participant already attended!")

    participant.attended = True
    participant.save(update_fields=["attended"])

    ticket_str = str(participant.ticket)
    return {
        "success": True,
        "message": ticket_str,
        "ticket": ticket_str,
    }
