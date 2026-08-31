from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
import logging
import os

from django.core.cache import cache
from mollie.api.client import Client

logger = logging.getLogger(__name__)

CACHE_TIMEOUT = 600
DAYS = 30
MOLLIE_DASHBOARD_URL = "https://my.mollie.com/dashboard/org_19161509/home"

ACCOUNTS = {
    "darts": "MOLLIE_API_KEY",
    "collectibles": "MOLLIE_API_KEY_COLLECTIBLES",
}


def _fetch_account_stats(api_key):
    counts = {"paid": 0, "open": 0, "failed": 0, "paid_amount": 0.0}

    if not api_key:
        return counts

    client = Client()
    client.set_api_key(api_key)
    cutoff = (date.today() - timedelta(days=DAYS)).isoformat()
    paid_amount = Decimal("0")

    collection = client.payments.list(limit=250)
    while True:
        for payment in collection:
            created = (payment.get("createdAt") or "")[:10]
            if not created or created < cutoff:
                continue

            status = payment.get("status", "")
            amount = Decimal(payment.get("amount", {}).get("value", "0") or "0")

            if status == "paid":
                paid_amount += amount
                counts["paid"] += 1
            elif status == "open":
                counts["open"] += 1
            elif status in ("failed", "expired", "canceled"):
                counts["failed"] += 1

        if not collection.has_next():
            break
        collection = collection.get_next()

    counts["paid_amount"] = float(paid_amount)
    return counts


def get_mollie_stats(account):
    cache_key = f"admin_dashboard_mollie_stats_{account}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    env_var = ACCOUNTS.get(account)
    api_key = os.environ.get(env_var) if env_var else None

    try:
        totals = _fetch_account_stats(api_key)
        result = {
            "ok": True,
            "error": None,
            "totals": totals,
            "mollie_url": MOLLIE_DASHBOARD_URL,
        }
    except Exception:
        logger.exception("Mollie API error for %s", account)
        result = {
            "ok": False,
            "error": f"Mollie API niet bereikbaar voor {account}",
            "totals": {"paid": 0, "open": 0, "failed": 0, "paid_amount": 0.0},
            "mollie_url": MOLLIE_DASHBOARD_URL,
        }

    cache.set(cache_key, result, CACHE_TIMEOUT)
    return result
