from django.db import transaction
from django.shortcuts import redirect
from django.urls import reverse

from pokemon.models import StandhouderInschrijvingStatus


class StandhouderValidationError(Exception):
    pass


@transaction.atomic
def finalize_inschrijving(inschrijving):
    inschrijving.bereken_totaal()

    try:
        inschrijving.valideer_tafels_beschikbaar()
    except ValueError as exc:
        raise StandhouderValidationError(str(exc)) from exc

    if inschrijving.evenement.standhouder_betaling_verplicht:
        # Fase 2 (later): Mollie-integratie
        # payment = Payment.objects.create(...)
        # inschrijving.payment = payment
        # inschrijving.status = StandhouderInschrijvingStatus.WACHT_OP_BETALING
        # inschrijving.save()
        # return redirect(mollie_checkout_url)
        raise StandhouderValidationError(
            "Online betaling is nog niet beschikbaar voor standhouders."
        )

    inschrijving.status = StandhouderInschrijvingStatus.INGEDIEND
    inschrijving.save()
    inschrijving.verstuur_bevestiging()

    return redirect(
        reverse(
            "standhouder_success",
            kwargs={"slug": inschrijving.evenement.slug},
        )
    )
