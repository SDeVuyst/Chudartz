import os
from datetime import timezone as dt_timezone
from urllib.parse import urlencode

import pytz
from django.urls import reverse
from django.utils import timezone

from darts.services.kamp_seo import plain_description

SITE_URL = os.environ.get("SITE_URL", "https://chudartz.com").rstrip("/")
PRODID = "-//ChudartZ//Dartskampen//NL"
TZID = "Europe/Brussels"
BRUSSELS = pytz.timezone(TZID)

VTIMEZONE_BRUSSELS = [
    "BEGIN:VTIMEZONE",
    f"TZID:{TZID}",
    f"X-LIC-LOCATION:{TZID}",
    "BEGIN:DAYLIGHT",
    "TZOFFSETFROM:+0100",
    "TZOFFSETTO:+0200",
    "TZNAME:CEST",
    "DTSTART:19700329T020000",
    "RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU",
    "END:DAYLIGHT",
    "BEGIN:STANDARD",
    "TZOFFSETFROM:+0200",
    "TZOFFSETTO:+0100",
    "TZNAME:CET",
    "DTSTART:19701025T030000",
    "RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU",
    "END:STANDARD",
    "END:VTIMEZONE",
]


def _aware(value):
    if timezone.is_naive(value):
        return BRUSSELS.localize(value)
    return value


def _utc_stamp(value):
    return _aware(value).astimezone(dt_timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _brussels_stamp(value):
    return _aware(value).astimezone(BRUSSELS).strftime("%Y%m%dT%H%M%S")


def _escape(text):
    return (
        str(text or "")
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
        .replace("\r", "\\n")
    )


def _fold(line):
    """Fold content lines to max 75 octets as required by RFC 5545."""
    encoded = line.encode("utf-8")
    if len(encoded) <= 75:
        return line

    parts = []
    current = b""
    limit = 75
    for char in line:
        char_bytes = char.encode("utf-8")
        if len(current) + len(char_bytes) > limit:
            parts.append(current.decode("utf-8"))
            current = b""
            limit = 74
        current += char_bytes
    parts.append(current.decode("utf-8"))
    return "\r\n ".join(parts)


def kamp_path(kamp):
    return reverse("dartskamp", kwargs={"slug": kamp.slug}, urlconf="darts.urls")


def kamp_page_url(kamp, request=None):
    path = kamp_path(kamp)
    if request is not None:
        return request.build_absolute_uri(path)
    return SITE_URL + path


def build_ics(kamp, page_url=None):
    page_url = page_url or kamp_page_url(kamp)
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:{PRODID}",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        *VTIMEZONE_BRUSSELS,
        "BEGIN:VEVENT",
        f"UID:dartskamp-{kamp.pk}@chudartz.com",
        f"DTSTAMP:{_utc_stamp(timezone.now())}",
        f"DTSTART;TZID={TZID}:{_brussels_stamp(kamp.start_datum)}",
        f"DTEND;TZID={TZID}:{_brussels_stamp(kamp.einde_datum)}",
        f"SUMMARY:{_escape(kamp.titel)}",
        f"LOCATION:{_escape(kamp.locatie_lang)}",
        f"DESCRIPTION:{_escape(plain_description(kamp, limit=800))}",
        f"URL:{page_url}",
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    return "\r\n".join(_fold(line) for line in lines) + "\r\n"


def google_calendar_url(kamp, page_url=None):
    page_url = page_url or kamp_page_url(kamp)
    params = {
        "action": "TEMPLATE",
        "text": kamp.titel,
        "dates": f"{_brussels_stamp(kamp.start_datum)}/{_brussels_stamp(kamp.einde_datum)}",
        "ctz": TZID,
        "details": f"{plain_description(kamp, limit=800)}\n\n{page_url}".strip(),
        "location": kamp.locatie_lang,
    }
    return "https://calendar.google.com/calendar/render?" + urlencode(params)
