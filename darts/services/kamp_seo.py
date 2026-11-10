import json
import re
from html import unescape

from django.urls import reverse
from django.utils.html import strip_tags
from django.utils.translation import gettext as _
from django.utils import timezone

ORGANIZER_NAME = "ChudartZ"
ORGANIZER_URL = "https://chudartz.com"

_JSON_SCRIPT_ESCAPES = {
    ord("<"): "\\u003c",
    ord(">"): "\\u003e",
    ord("&"): "\\u0026",
}


def plain_description(kamp, limit=240):
    text = unescape(strip_tags(kamp.beschrijving or ""))
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    if limit and len(text) > limit:
        trimmed = text[:limit].rsplit(" ", 1)[0]
        text = (trimmed or text[:limit]).rstrip(".,;:") + "…"
    return text


def _iso(value):
    return timezone.localtime(value).isoformat()


def _offer_availability(kamp):
    if kamp.is_sold_out:
        return "https://schema.org/SoldOut"
    if not kamp.enable_inschrijvingen or not kamp.is_in_future:
        return "https://schema.org/OutOfStock"
    return "https://schema.org/InStock"


def build_kamp_jsonld(kamp, request):
    event_url = request.build_absolute_uri(reverse("dartskamp", kwargs={"slug": kamp.slug}))
    signup_url = request.build_absolute_uri(
        reverse("inschrijven_dartskamp", kwargs={"slug": kamp.slug})
    )
    price = kamp.prijs
    offer = {
        "@type": "Offer",
        "name": str(_("Deelname")),
        "price": f"{price.amount:.2f}",
        "priceCurrency": str(price.currency) if price is not None else "EUR",
        "availability": _offer_availability(kamp),
        "url": signup_url if kamp.enable_inschrijvingen and kamp.is_in_future else event_url,
    }
    data = {
        "@context": "https://schema.org",
        "@type": "Event",
        "name": kamp.titel,
        "description": plain_description(kamp),
        "startDate": _iso(kamp.start_datum),
        "endDate": _iso(kamp.einde_datum),
        "eventStatus": "https://schema.org/EventScheduled",
        "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
        "url": event_url,
        "location": {
            "@type": "Place",
            "name": kamp.locatie_kort,
            "address": kamp.locatie_lang,
        },
        "organizer": {
            "@type": "Organization",
            "name": ORGANIZER_NAME,
            "url": ORGANIZER_URL,
        },
        "offers": offer,
    }
    if kamp.afbeelding:
        data["image"] = [request.build_absolute_uri(kamp.afbeelding.url)]

    return json.dumps(data, ensure_ascii=False).translate(_JSON_SCRIPT_ESCAPES)
