from decimal import Decimal

from django.db import transaction
from django.urls import reverse
from django.utils.translation import gettext as _

from pokemon.models import (
    Kortingscode,
    Participant,
    Payment,
    PaymentStatus,
    Ticket,
)
from pokemon.payment import MollieClient
from pokemon.ticket_wizard import MAX_TICKETS_PER_TYPE, get_ticket_quantities


class TicketValidationError(Exception):
    pass


def validate_ticket_selection(evenement, quantities):
    if not evenement.enable_inschrijvingen:
        raise TicketValidationError(_("Inschrijvingen zijn gesloten."))

    if evenement.is_sold_out:
        raise TicketValidationError(_("Dit evenement is uitverkocht."))

    if not quantities:
        raise TicketValidationError(_("Selecteer minstens één ticket."))

    total_qty = 0
    for ticket_id, qty in quantities.items():
        try:
            ticket = Ticket.objects.get(pk=ticket_id, event=evenement)
        except Ticket.DoesNotExist:
            raise TicketValidationError(_("Ongeldig ticket."))

        if ticket.disable_ticket or ticket.is_sold_out:
            raise TicketValidationError(_("Eén of meer tickets zijn niet meer beschikbaar."))

        if qty < 0:
            raise TicketValidationError(_("Ongeldig aantal tickets."))

        if qty > ticket.remaining_tickets:
            raise TicketValidationError(
                _("Niet genoeg tickets beschikbaar voor %(ticket)s.") % {"ticket": ticket.titel}
            )

        if qty > MAX_TICKETS_PER_TYPE:
            raise TicketValidationError(
                _("Maximaal %(max)s tickets per type per bestelling.")
                % {"max": MAX_TICKETS_PER_TYPE}
            )

        total_qty += qty

    if total_qty < 1:
        raise TicketValidationError(_("Selecteer minstens één ticket."))

    if evenement.remaining_tickets < total_qty:
        raise TicketValidationError(_("Niet genoeg tickets beschikbaar voor dit evenement."))


def validate_kortingscode(code, evenement, quantities):
    if not code or not code.strip():
        return None, Decimal("0")

    kortingscode = Kortingscode.objects.filter(code__iexact=code.strip()).first()
    if not kortingscode:
        raise TicketValidationError(_("Deze kortingscode is ongeldig."))

    if not kortingscode.is_geldig_op_moment():
        raise TicketValidationError(_("Deze kortingscode is niet meer geldig."))

    event_ids = set(kortingscode.evenementen.values_list("pk", flat=True))
    if event_ids and evenement.pk not in event_ids:
        raise TicketValidationError(_("Deze kortingscode is niet geldig voor dit evenement."))

    ticket_ids = set(kortingscode.tickets.values_list("pk", flat=True))
    if ticket_ids:
        selected_ids = set(quantities.keys())
        if not selected_ids.intersection(ticket_ids):
            raise TicketValidationError(_("Deze kortingscode is niet geldig voor de geselecteerde tickets."))

    subtotaal = bereken_subtotaal(evenement, quantities)

    if kortingscode.min_bedrag and subtotaal < kortingscode.min_bedrag.amount:
        raise TicketValidationError(
            _("Minimum bestelbedrag voor deze code is €%(bedrag)s.")
            % {"bedrag": kortingscode.min_bedrag.amount}
        )

    korting = kortingscode.bereken_korting(subtotaal)
    return kortingscode, korting


def bereken_subtotaal(evenement, quantities):
    subtotaal = Decimal("0")
    for ticket_id, qty in quantities.items():
        ticket = Ticket.objects.get(pk=ticket_id, event=evenement)
        subtotaal += qty * ticket.price.amount
    return subtotaal.quantize(Decimal("0.01"))


def build_prijsopbouw(evenement, quantities, kortingscode=None, korting_bedrag=None):
    regels = []
    for ticket_id, qty in quantities.items():
        ticket = Ticket.objects.get(pk=ticket_id, event=evenement)
        bedrag = (qty * ticket.price.amount).quantize(Decimal("0.01"))
        regels.append({
            "omschrijving": f"{qty}× {ticket.titel}",
            "bedrag": bedrag,
        })

    subtotaal = bereken_subtotaal(evenement, quantities)
    if kortingscode and korting_bedrag and korting_bedrag > 0:
        regels.append({
            "omschrijving": _("Korting (%(code)s)") % {"code": kortingscode.code},
            "bedrag": korting_bedrag,
            "is_korting": True,
        })

    totaal = max(subtotaal - (korting_bedrag or Decimal("0")), Decimal("0"))
    return regels, subtotaal, totaal


def finalize_checkout(request, evenement, wizard_data):
    quantities = get_ticket_quantities(wizard_data)
    validate_ticket_selection(evenement, quantities)

    email = wizard_data.get("email", "").strip()
    if not email:
        raise TicketValidationError(_("Vul een geldig e-mailadres in."))

    kortingscode_obj = None
    korting_bedrag = Decimal("0")
    code = wizard_data.get("kortingscode", "")
    if code:
        kortingscode_obj, korting_bedrag = validate_kortingscode(code, evenement, quantities)

    subtotaal = bereken_subtotaal(evenement, quantities)
    totaal = max(subtotaal - korting_bedrag, Decimal("0"))

    with transaction.atomic():
        payment = Payment.objects.create(
            mail=email,
            first_name=wizard_data.get("first_name") or None,
            last_name=wizard_data.get("last_name") or None,
            amount=totaal,
            subtotaal=subtotaal,
            korting_bedrag=korting_bedrag,
            kortingscode=kortingscode_obj,
        )

        for ticket_id, qty in quantities.items():
            ticket = Ticket.objects.get(pk=ticket_id, event=evenement)
            for _ in range(qty):
                Participant.objects.create(
                    mail=email,
                    payment=payment,
                    ticket=ticket,
                )

    redirect_url = request.build_absolute_uri(
        reverse("evenement_success", kwargs={"slug": evenement.slug})
    )

    if totaal <= 0:
        payment.status = PaymentStatus.PAID
        payment.save()
        return payment, redirect_url

    mollie_payment = MollieClient().create_mollie_payment(
        amount=totaal,
        description=f"ChudartZ Collectibles - {evenement.titel}",
        redirect_url=redirect_url,
    )

    payment.mollie_id = mollie_payment.id
    payment.save()

    return payment, mollie_payment.checkout_url


def verwerk_ticket_betaling(payment, status):
    """Hook voor ticket-betalingen na Mollie-webhook (korting wordt in Payment.save afgehandeld)."""
    pass
