from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction
from django.urls import reverse

from pokemon.models import Payment, PaymentStatus, StandhouderInschrijvingStatus
from pokemon.payment import MollieClient


class StandhouderValidationError(Exception):
    pass


@dataclass
class FinalizeResult:
    redirect_url: str | None = None
    email_sent: bool = False
    voorlopig: bool = False


def _split_naam(naam: str) -> tuple[str, str]:
    parts = (naam or "").strip().split(None, 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return parts[0] if parts else "", ""


@transaction.atomic
def finalize_inschrijving(inschrijving, request) -> FinalizeResult:
    inschrijving.bereken_totaal()

    try:
        inschrijving.valideer_tafels_beschikbaar()
    except ValueError as exc:
        raise StandhouderValidationError(str(exc)) from exc

    evenement = inschrijving.evenement
    totaal = inschrijving.totaal_bedrag.amount if inschrijving.totaal_bedrag else Decimal("0")

    if evenement.standhouder_betaling_verplicht:
        if totaal <= 0:
            raise StandhouderValidationError(
                "Het totaalbedrag moet groter zijn dan €0 om online te betalen."
            )

        voornaam, achternaam = _split_naam(inschrijving.naam)
        payment = Payment.objects.create(
            mail=inschrijving.email,
            first_name=voornaam,
            last_name=achternaam,
            amount=totaal,
            status=PaymentStatus.OPEN,
        )
        inschrijving.payment = payment
        inschrijving.status = StandhouderInschrijvingStatus.WACHT_OP_BETALING
        inschrijving.save(update_fields=["payment", "status", "totaal_bedrag"])

        redirect_url = request.build_absolute_uri(
            reverse("standhouder_success", kwargs={"slug": evenement.slug})
        )
        mollie_payment = MollieClient().create_mollie_payment(
            amount=totaal,
            description=f"Standhouder {inschrijving.bedrijfsnaam} - {evenement.titel}",
            redirect_url=redirect_url,
        )
        payment.mollie_id = mollie_payment.id
        payment.save(update_fields=["mollie_id"])

        return FinalizeResult(redirect_url=mollie_payment.checkout_url)

    inschrijving.status = StandhouderInschrijvingStatus.INGEDIEND
    inschrijving.save(update_fields=["status", "totaal_bedrag"])
    email_sent = inschrijving.verstuur_bevestiging(voorlopig=True)
    return FinalizeResult(email_sent=email_sent, voorlopig=True)


def verwerk_standhouder_betaling(payment, mollie_status: str) -> None:
    from pokemon.models import StandhouderInschrijving

    try:
        inschrijving = StandhouderInschrijving.objects.select_related("evenement").get(
            payment=payment
        )
    except StandhouderInschrijving.DoesNotExist:
        return

    if mollie_status == PaymentStatus.PAID:
        if inschrijving.status != StandhouderInschrijvingStatus.BETAALD:
            inschrijving.status = StandhouderInschrijvingStatus.BETAALD
            inschrijving.save(update_fields=["status"])
            inschrijving.verstuur_bevestiging(voorlopig=False)
    elif mollie_status in (
        PaymentStatus.EXPIRED,
        PaymentStatus.CANCELED,
        PaymentStatus.FAILED,
    ):
        if inschrijving.status == StandhouderInschrijvingStatus.WACHT_OP_BETALING:
            inschrijving.status = StandhouderInschrijvingStatus.VERLOPEN
            inschrijving.save(update_fields=["status"])
