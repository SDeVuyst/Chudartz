from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction
from django.db.models import F
from django.urls import reverse
from django.utils.translation import gettext as _
from djmoney.money import Money

from pokemon.models import (
    Kortingscode,
    KortingscodeToepassingsgebied,
    Payment,
    PaymentStatus,
    StandhouderInschrijving,
    StandhouderInschrijvingStatus,
)
from pokemon.payment import MollieClient
from pokemon.standhouder_wizard import lock_tafelcellen


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


def validate_standhouder_kortingscode(code, evenement, subtotaal):
    if not code or not code.strip():
        return None, Decimal("0")

    kortingscode = Kortingscode.objects.filter(
        code__iexact=code.strip(),
        toepassingsgebied=KortingscodeToepassingsgebied.STANDHOUDERS,
    ).first()
    if not kortingscode:
        raise StandhouderValidationError(_("Deze kortingscode is ongeldig."))

    if not kortingscode.is_geldig_op_moment():
        raise StandhouderValidationError(_("Deze kortingscode is niet meer geldig."))

    event_ids = set(kortingscode.evenementen.values_list("pk", flat=True))
    if event_ids and evenement.pk not in event_ids:
        raise StandhouderValidationError(
            _("Deze kortingscode is niet geldig voor dit evenement.")
        )

    subtotaal = Decimal(str(subtotaal))
    if kortingscode.min_bedrag and subtotaal < kortingscode.min_bedrag.amount:
        raise StandhouderValidationError(
            _("Minimum bestelbedrag voor deze code is €%(bedrag)s.")
            % {"bedrag": kortingscode.min_bedrag.amount}
        )

    korting = kortingscode.bereken_korting(subtotaal)
    return kortingscode, korting


def _increment_kortingscode_gebruik(kortingscode):
    if not kortingscode:
        return
    Kortingscode.objects.filter(pk=kortingscode.pk).update(
        aantal_gebruikt=F("aantal_gebruikt") + 1
    )


@transaction.atomic
def finalize_inschrijving(inschrijving, request, kortingscode_str="") -> FinalizeResult:
    inschrijving = (
        StandhouderInschrijving.objects.select_for_update()
        .select_related("evenement")
        .get(pk=inschrijving.pk)
    )
    lock_tafelcellen(
        inschrijving.tafel_keuzes.order_by("cel_id").values_list("cel_id", flat=True)
    )

    subtotaal = inschrijving.bereken_totaal()

    try:
        inschrijving.valideer_tafels_beschikbaar()
    except ValueError as exc:
        raise StandhouderValidationError(str(exc)) from exc

    evenement = inschrijving.evenement
    kortingscode_obj = None
    korting_bedrag = Decimal("0")
    if kortingscode_str:
        kortingscode_obj, korting_bedrag = validate_standhouder_kortingscode(
            kortingscode_str, evenement, subtotaal
        )

    totaal = max(subtotaal - korting_bedrag, Decimal("0"))
    inschrijving.totaal_bedrag = Money(totaal, "EUR")

    if evenement.standhouder_betaling_verplicht:
        voornaam, achternaam = _split_naam(inschrijving.naam)
        payment = Payment.objects.create(
            mail=inschrijving.email,
            first_name=voornaam,
            last_name=achternaam,
            amount=totaal,
            subtotaal=subtotaal,
            korting_bedrag=korting_bedrag,
            kortingscode=kortingscode_obj,
            status=PaymentStatus.OPEN,
        )
        inschrijving.payment = payment
        inschrijving.status = StandhouderInschrijvingStatus.WACHT_OP_BETALING
        inschrijving.save(update_fields=["payment", "status", "totaal_bedrag"])

        redirect_url = request.build_absolute_uri(
            reverse("standhouder_success", kwargs={"slug": evenement.slug})
        )

        if totaal <= 0:
            payment.status = PaymentStatus.PAID
            payment.save()
            inschrijving.status = StandhouderInschrijvingStatus.BETAALD
            inschrijving.save(update_fields=["status"])
            email_sent = inschrijving.verstuur_bevestiging(voorlopig=False)
            return FinalizeResult(email_sent=email_sent, voorlopig=False)

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
    _increment_kortingscode_gebruik(kortingscode_obj)
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
