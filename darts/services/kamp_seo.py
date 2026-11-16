import json
import os
import re
from html import unescape

from django.templatetags.static import static
from django.urls import reverse
from django.utils.html import strip_tags
from django.utils.translation import gettext as _
from django.utils import timezone

ORGANIZER_NAME = "ChudartZ"
ORGANIZER_URL = "https://chudartz.com"
# SITE_URL in stack.env is van chudartz-collectibles.com; darts heeft een eigen variabele.
SITE_URL = os.environ.get("DARTS_SITE_URL", ORGANIZER_URL).rstrip("/")

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


def absolute_url(path):
    """Absolute URL op het publieke domein.

    `request.build_absolute_uri` geeft achter de nginx-proxy `http://` terug,
    dus voor canonical/OG/JSON-LD gebruiken we altijd SITE_URL.
    """
    if path.startswith(("http://", "https://")):
        return path
    return SITE_URL + path


def default_image_url():
    return absolute_url(static("img/logo-black.png"))


def kamp_meta_description(kamp, limit=155):
    text = plain_description(kamp, limit=limit)
    if text:
        return text
    return str(_("Dartskamp %(titel)s in %(locatie)s, georganiseerd door ChudartZ. Schrijf je nu in!")) % {
        "titel": kamp.titel,
        "locatie": kamp.locatie_kort,
    }


def _iso(value):
    return timezone.localtime(value).isoformat()


def _offer_availability(kamp):
    if kamp.is_sold_out:
        return "https://schema.org/SoldOut"
    if not kamp.enable_inschrijvingen or not kamp.is_in_future:
        return "https://schema.org/OutOfStock"
    return "https://schema.org/InStock"


def build_kamp_jsonld(kamp, request=None):
    event_url = absolute_url(reverse("dartskamp", kwargs={"slug": kamp.slug}))
    signup_url = absolute_url(reverse("inschrijven_dartskamp", kwargs={"slug": kamp.slug}))
    overview_url = absolute_url(reverse("dartskampen"))
    image_url = absolute_url(kamp.afbeelding.url) if kamp.afbeelding else default_image_url()

    price = kamp.prijs
    offer = {
        "@type": "Offer",
        "name": str(_("Deelname")),
        "availability": _offer_availability(kamp),
        "url": signup_url if kamp.enable_inschrijvingen and kamp.is_in_future else event_url,
    }
    if price is not None:
        offer["price"] = f"{price.amount:.2f}"
        offer["priceCurrency"] = str(price.currency)

    event = {
        "@context": "https://schema.org",
        "@type": "Event",
        "name": kamp.titel,
        "description": plain_description(kamp) or kamp_meta_description(kamp),
        "startDate": _iso(kamp.start_datum),
        "endDate": _iso(kamp.einde_datum),
        "eventStatus": "https://schema.org/EventScheduled",
        "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
        "url": event_url,
        "image": [image_url],
        "location": {
            "@type": "Place",
            "name": kamp.locatie_kort,
            "address": kamp.locatie_lang,
        },
        "organizer": {
            "@type": "Organization",
            "name": ORGANIZER_NAME,
            "url": ORGANIZER_URL,
            "logo": default_image_url(),
        },
        "performer": {
            "@type": "Organization",
            "name": ORGANIZER_NAME,
        },
        "offers": offer,
    }
    breadcrumbs = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": absolute_url(reverse("index"))},
            {"@type": "ListItem", "position": 2, "name": str(_("Dartskampen")), "item": overview_url},
            {"@type": "ListItem", "position": 3, "name": kamp.titel, "item": event_url},
        ],
    }

    return json.dumps([event, breadcrumbs], ensure_ascii=False).translate(_JSON_SCRIPT_ESCAPES)
