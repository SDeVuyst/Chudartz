import logging
import os

import requests
from django.core.cache import cache
from django.utils.dateparse import parse_datetime

logger = logging.getLogger(__name__)

CACHE_KEY = "admin_dashboard_calcom_bookings"
CACHE_TIMEOUT = 300
CALCOM_BOOKINGS_URL = "https://app.cal.com/bookings/upcoming"
CALCOM_API_URL = "https://api.cal.com/v2/bookings"


def _parse_booking(raw):
    attendees = raw.get("attendees") or []
    attendee_names = []
    for attendee in attendees:
        name = attendee.get("name") or attendee.get("email") or ""
        if name:
            attendee_names.append(name)

    uid = raw.get("uid") or raw.get("id") or ""
    booking_url = f"https://app.cal.com/booking/{uid}" if uid else CALCOM_BOOKINGS_URL

    start_raw = raw.get("start") or raw.get("startTime") or ""
    start = None
    if start_raw:
        start = parse_datetime(start_raw.replace("Z", "+00:00"))

    return {
        "title": raw.get("title") or raw.get("eventType", {}).get("title", "Afspraak"),
        "start": start,
        "attendees": attendee_names,
        "url": booking_url,
    }


def get_upcoming_bookings():
    cached = cache.get(CACHE_KEY)
    if cached is not None:
        return cached

    api_key = os.environ.get("CALCOM_API_KEY")
    if not api_key:
        return {
            "ok": False,
            "error": "CALCOM_API_KEY niet geconfigureerd",
            "bookings": [],
            "url": CALCOM_BOOKINGS_URL,
        }

    try:
        response = requests.get(
            CALCOM_API_URL,
            params={"status": "upcoming", "limit": 10},
            headers={
                "Authorization": f"Bearer {api_key}",
                "cal-api-version": "2026-05-01",
            },
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()

        raw_bookings = payload.get("data")
        if raw_bookings is None:
            raw_bookings = payload.get("bookings", [])

        bookings = [_parse_booking(item) for item in raw_bookings]
        result = {
            "ok": True,
            "error": None,
            "bookings": bookings,
            "url": CALCOM_BOOKINGS_URL,
        }
    except Exception as exc:
        logger.exception("Cal.com API error")
        result = {
            "ok": False,
            "error": str(exc),
            "bookings": [],
            "url": CALCOM_BOOKINGS_URL,
        }

    cache.set(CACHE_KEY, result, CACHE_TIMEOUT)
    return result
