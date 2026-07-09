from decimal import Decimal

from django.utils.translation import gettext_lazy as _

from pokemon.models import Evenement, Ticket

MAX_TICKETS_PER_TYPE = 10


def session_key(evenement):
    return f"ticket_wizard_{evenement.slug}"


def pending_payment_session_key(evenement):
    return f"ticket_pending_{evenement.slug}"


TICKET_STAP_URLS = {
    "tickets": "ticket_kopen",
    "gegevens": "ticket_gegevens",
    "overzicht": "ticket_overzicht",
}


def get_wizard_data(request, evenement):
    return request.session.get(session_key(evenement), {})


def set_wizard_data(request, evenement, data):
    request.session[session_key(evenement)] = data
    request.session.modified = True


def clear_wizard_data(request, evenement):
    request.session.pop(session_key(evenement), None)


def get_ticket_quantities(wizard_data):
    raw = wizard_data.get("ticket_quantities", {})
    return {int(k): int(v) for k, v in raw.items() if int(v) > 0}


def heeft_tickets(wizard_data):
    return bool(get_ticket_quantities(wizard_data))


def heeft_ticket_gegevens(wizard_data):
    return bool(wizard_data.get("email"))


def get_beschikbare_tickets(evenement):
    return Ticket.objects.filter(event=evenement, disable_ticket=False).order_by("pk")


def build_wizard_stappen(evenement, huidige_stap, wizard_data=None):
    stappen = [
        {"nummer": 1, "label": _("Tickets"), "url_name": "ticket_kopen"},
        {"nummer": 2, "label": _("Gegevens"), "url_name": "ticket_gegevens"},
        {"nummer": 3, "label": _("Overzicht"), "url_name": "ticket_overzicht"},
    ]
    wizard_data = wizard_data or {}
    for stap in stappen:
        stap["is_reachable"] = stap["nummer"] < huidige_stap
    return stappen


def ticket_base_context(request, evenement, stap):
    stap_nummers = {"tickets": 1, "gegevens": 2, "overzicht": 3, "success": 4}
    wizard_data = get_wizard_data(request, evenement)
    return {
        "evenement": evenement,
        "wizard_stap": stap_nummers.get(stap, 1),
        "stappen": build_wizard_stappen(evenement, stap_nummers.get(stap, 1), wizard_data),
        "wizard_data": wizard_data,
        "tickets": get_beschikbare_tickets(evenement),
        "max_tickets_per_type": MAX_TICKETS_PER_TYPE,
    }


def serialize_tickets_for_js(evenement):
    items = []
    for ticket in get_beschikbare_tickets(evenement):
        if ticket.is_sold_out:
            continue
        items.append({
            "id": ticket.pk,
            "titel": ticket.titel,
            "prijs": str(ticket.price.amount),
            "max": min(ticket.remaining_tickets, MAX_TICKETS_PER_TYPE),
            "icon": ticket.icon,
        })
    return items
