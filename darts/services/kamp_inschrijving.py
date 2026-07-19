from decimal import Decimal

from django.db import transaction
from django.urls import reverse
from django.utils.translation import gettext as _

from darts.models import Dartskamp, Participant, Payment, PaymentStatus
from darts.payment import MollieClient


class KampValidationError(Exception):
    pass


def validate_inschrijving(kamp):
    if not kamp.toon_op_site:
        raise KampValidationError(_("Dit dartskamp is niet beschikbaar."))

    if not kamp.enable_inschrijvingen:
        raise KampValidationError(_("Inschrijvingen zijn gesloten."))

    if kamp.is_sold_out:
        raise KampValidationError(_("Dit dartskamp is volzet."))

    if not kamp.is_in_future and not kamp.is_bezig:
        raise KampValidationError(_("Inschrijvingen voor dit dartskamp zijn afgelopen."))


def validate_kindgegevens(wizard_data):
    required = (
        "voornaam",
        "achternaam",
        "geboortejaar",
        "email",
        "gsm",
        "straatnaam",
        "nummer",
        "postcode",
        "stad",
    )
    for field in required:
        if wizard_data.get(field) in (None, ""):
            raise KampValidationError(_("Vul alle persoonlijke gegevens in."))


def finalize_checkout(request, kamp, wizard_data):
    validate_inschrijving(kamp)
    validate_kindgegevens(wizard_data)

    price = Decimal(kamp.prijs.amount)

    with transaction.atomic():
        # Re-check capacity inside the transaction
        kamp = Dartskamp.objects.select_for_update().get(pk=kamp.pk)
        if kamp.is_sold_out:
            raise KampValidationError(_("Dit dartskamp is volzet."))

        payment = Payment.objects.create(
            first_name=wizard_data["voornaam"],
            last_name=wizard_data["achternaam"],
            mail=wizard_data["email"],
            amount=price,
            description=f"Dartskamp ChudartZ - {kamp.titel}",
        )

        Participant.objects.create(
            voornaam=wizard_data["voornaam"],
            achternaam=wizard_data["achternaam"],
            geboortejaar=wizard_data["geboortejaar"],
            email=wizard_data["email"],
            straatnaam=wizard_data["straatnaam"],
            nummer=wizard_data["nummer"],
            postcode=wizard_data["postcode"],
            stad=wizard_data["stad"],
            gsm=wizard_data["gsm"],
            payment=payment,
            dartskamp=kamp,
        )

    redirect_url = request.build_absolute_uri(
        reverse("inschrijven_dartskamp_success", kwargs={"slug": kamp.slug})
    )

    if price <= 0:
        payment.status = PaymentStatus.PAID
        payment.save()
        return payment, redirect_url

    mollie_payment = MollieClient().create_mollie_payment(
        amount=price,
        description=f"Dartskamp ChudartZ - {kamp.titel}",
        redirect_url=redirect_url,
    )

    payment.mollie_id = mollie_payment.id
    payment.save()

    return payment, mollie_payment.checkout_url
