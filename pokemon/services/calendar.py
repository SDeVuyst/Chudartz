from datetime import timezone as dt_timezone
from urllib.parse import urlencode

import pytz
from django.urls import reverse
from django.utils import timezone

SITE_URL = "https://chudartz-collectibles.com"
PRODID = "-//ChudartZ Collectibles//Evenementen//NL"
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


def evenement_url(evenement):
    return evenement.get_absolute_url()


def evenement_ics_url(evenement):
    return SITE_URL + reverse("evenement_agenda", kwargs={"slug": evenement.slug}, urlconf="pokemon.urls")


def build_ics(evenement):
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:{PRODID}",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        *VTIMEZONE_BRUSSELS,
        "BEGIN:VEVENT",
        f"UID:evenement-{evenement.pk}@chudartz-collectibles.com",
        f"DTSTAMP:{_utc_stamp(timezone.now())}",
        f"DTSTART;TZID={TZID}:{_brussels_stamp(evenement.start_datum)}",
        f"DTEND;TZID={TZID}:{_brussels_stamp(evenement.einde_datum)}",
        f"SUMMARY:{_escape(evenement.titel)}",
        f"LOCATION:{_escape(evenement.locatie_lang)}",
        f"DESCRIPTION:{_escape(evenement.intro_op_index)}",
        f"URL:{evenement_url(evenement)}",
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    return "\r\n".join(_fold(line) for line in lines) + "\r\n"


def google_calendar_url(evenement):
    params = {
        "action": "TEMPLATE",
        "text": evenement.titel,
        "dates": f"{_brussels_stamp(evenement.start_datum)}/{_brussels_stamp(evenement.einde_datum)}",
        "ctz": TZID,
        "details": f"{evenement.intro_op_index}\n\n{evenement_url(evenement)}".strip(),
        "location": evenement.locatie_lang,
    }
    return "https://calendar.google.com/calendar/render?" + urlencode(params)


def agenda_context(evenement):
    return {
        "agenda_google_url": google_calendar_url(evenement),
        "agenda_ics_url": evenement_ics_url(evenement),
    }
