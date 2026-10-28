import json

from django.urls import reverse
from django.utils import timezone

ORGANIZER_NAME = "ChudartZ Collectibles"
ORGANIZER_URL = "https://chudartz-collectibles.com"

_JSON_SCRIPT_ESCAPES = {
    ord("<"): "\\u003c",
    ord(">"): "\\u003e",
    ord("&"): "\\u0026",
}


def _iso(value):
    return timezone.localtime(value).isoformat()


def _offer_availability(evenement, ticket):
    if evenement.is_sold_out or ticket.is_sold_out:
        return "https://schema.org/SoldOut"
    if ticket.enkel_inkom:
        return "https://schema.org/InStoreOnly"
    if not evenement.enable_inschrijvingen:
        return "https://schema.org/OutOfStock"
    return "https://schema.org/InStock"


def build_event_jsonld(evenement, tickets, request):
    slug = {"slug": evenement.slug}
    event_url = request.build_absolute_uri(reverse("evenement", kwargs=slug, urlconf="pokemon.urls"))
    tickets_url = request.build_absolute_uri(reverse("ticket_kopen", kwargs=slug, urlconf="pokemon.urls"))

    location = {
        "@type": "Place",
        "name": evenement.locatie_kort,
        "address": evenement.locatie_lang,
    }
    if evenement.latitude is not None and evenement.longitude is not None:
        location["geo"] = {
            "@type": "GeoCoordinates",
            "latitude": float(evenement.latitude),
            "longitude": float(evenement.longitude),
        }

    offers = []
    for ticket in tickets:
        if ticket.disable_ticket:
            continue
        offers.append({
            "@type": "Offer",
            "name": ticket.titel,
            "price": "0.00" if ticket.is_gratis else f"{ticket.price.amount:.2f}",
            "priceCurrency": str(ticket.price.currency) if ticket.price is not None else "EUR",
            "availability": _offer_availability(evenement, ticket),
            "url": event_url if ticket.enkel_inkom else tickets_url,
        })

    data = {
        "@context": "https://schema.org",
        "@type": "Event",
        "name": evenement.titel,
        "description": evenement.intro_op_index,
        "startDate": _iso(evenement.start_datum),
        "endDate": _iso(evenement.einde_datum),
        "eventStatus": "https://schema.org/EventScheduled",
        "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
        "url": event_url,
        "location": location,
        "organizer": {
            "@type": "Organization",
            "name": ORGANIZER_NAME,
            "url": ORGANIZER_URL,
        },
    }
    if evenement.afbeelding:
        data["image"] = [request.build_absolute_uri(evenement.afbeelding.url)]
    if offers:
        data["offers"] = offers

    return json.dumps(data, ensure_ascii=False).translate(_JSON_SCRIPT_ESCAPES)
