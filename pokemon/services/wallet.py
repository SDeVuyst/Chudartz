"""Apple Wallet and Google Wallet passes for event tickets.

Credentials come from base64-encoded environment variables (see stack.env).
When they are missing, wallet links are simply left out of the emails.
"""

import base64
import binascii
import json
import logging
import os
from dataclasses import dataclass

from cryptography import x509
from cryptography.hazmat.primitives import serialization
from django.contrib.staticfiles import finders
from django.core import signing
from django.urls import reverse

from django.utils.html import strip_tags

from darts.templatetags.dutch_date import dutch_time
from pokemon.services.calendar import BRUSSELS, SITE_URL, _aware

logger = logging.getLogger(__name__)

APPLE_TOKEN_SALT = "pokemon.wallet.apple"
APPLE_BADGE = "apple-wallet-badge"
GOOGLE_BADGE = "google-wallet-badge"
ORGANIZATION_NAME = "ChudartZ Collectibles"
CONTACT_EMAIL = "chudartz@gmail.com"
BACKGROUND_COLOR = (30, 33, 38)
BAND_COLOR = (120, 10, 16)


@dataclass(frozen=True)
class AppleWalletConfig:
    pass_type_id: str
    team_id: str
    certificate: x509.Certificate
    private_key: object
    wwdr_certificate: x509.Certificate


@dataclass(frozen=True)
class GoogleWalletConfig:
    issuer_id: str
    service_account_email: str
    private_key: str
    private_key_id: str


def iso_datetime(value):
    return _aware(value).astimezone(BRUSSELS).replace(microsecond=0).isoformat()


def plain_text(value):
    return strip_tags(value or "").strip()


def holder_name(participant):
    payment = participant.payment
    if payment is None:
        return ""
    return " ".join(part for part in [payment.first_name, payment.last_name] if part).strip()


def venue_name(evenement):
    lines = [line.strip() for line in plain_text(evenement.locatie_lang).splitlines() if line.strip()]
    return lines[0] if lines else plain_text(evenement.locatie_kort)


def toegang_tijden(ticket):
    return f"{dutch_time(ticket.get_toegang_start())} - {dutch_time(ticket.get_toegang_einde())}"


def absolute_url(path):
    if path.startswith(("http://", "https://")):
        return path
    return SITE_URL + path


def _env_b64(name):
    value = os.environ.get(name, "").strip()
    if not value:
        return None
    try:
        return base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError):
        logger.warning("Wallet: %s is not valid base64", name)
        return None


def apple_config():
    pass_type_id = os.environ.get("APPLE_PASS_TYPE_ID", "").strip()
    team_id = os.environ.get("APPLE_TEAM_ID", "").strip()
    cert_pem = _env_b64("APPLE_PASS_CERT_B64")
    key_pem = _env_b64("APPLE_PASS_KEY_B64")
    wwdr_pem = _env_b64("APPLE_WWDR_CERT_B64")
    if not all([pass_type_id, team_id, cert_pem, key_pem, wwdr_pem]):
        return None
    try:
        return AppleWalletConfig(
            pass_type_id=pass_type_id,
            team_id=team_id,
            certificate=x509.load_pem_x509_certificate(cert_pem),
            private_key=serialization.load_pem_private_key(key_pem, password=None),
            wwdr_certificate=x509.load_pem_x509_certificate(wwdr_pem),
        )
    except ValueError:
        logger.exception("Wallet: could not load Apple pass certificates")
        return None


def google_config():
    issuer_id = os.environ.get("GOOGLE_WALLET_ISSUER_ID", "").strip()
    raw = _env_b64("GOOGLE_WALLET_SERVICE_ACCOUNT_B64")
    if not issuer_id or not raw:
        return None
    try:
        account = json.loads(raw)
        return GoogleWalletConfig(
            issuer_id=issuer_id,
            service_account_email=account["client_email"],
            private_key=account["private_key"],
            private_key_id=account.get("private_key_id", ""),
        )
    except (ValueError, KeyError):
        logger.exception("Wallet: could not load Google service account")
        return None


def apple_pass_token(*, payment=None, participant=None):
    if payment is not None:
        return signing.dumps({"p": payment.pk}, salt=APPLE_TOKEN_SALT)
    return signing.dumps({"d": participant.pk}, salt=APPLE_TOKEN_SALT)


def participants_for_apple_token(token):
    """Return the participants a signed Apple Wallet token refers to, or None if invalid."""
    from pokemon.models import Participant

    try:
        data = signing.loads(token, salt=APPLE_TOKEN_SALT)
    except signing.BadSignature:
        return None

    participants = Participant.objects.select_related("ticket__event", "payment").order_by("pk")
    if "p" in data:
        participants = participants.filter(payment_id=data["p"])
    elif "d" in data:
        participants = participants.filter(pk=data["d"])
    else:
        return None
    return list(participants)


def apple_pass_url(*, payment=None, participant=None):
    token = apple_pass_token(payment=payment, participant=participant)
    return SITE_URL + reverse("wallet_apple", kwargs={"token": token}, urlconf="pokemon.urls")


def wallet_context(participants, *, payment=None):
    """Template context with Add to Apple/Google Wallet links for the given participants."""
    from pokemon.services import wallet_google

    participants = list(participants)
    if not participants:
        return {}

    context = {}
    if apple_config():
        if payment is not None:
            context["apple_wallet_url"] = apple_pass_url(payment=payment)
        else:
            context["apple_wallet_url"] = apple_pass_url(participant=participants[0])
        context["apple_wallet_badge"] = bool(finders.find(f"pokemon/img/{APPLE_BADGE}.png"))

    config = google_config()
    if config:
        try:
            context["google_wallet_url"] = wallet_google.save_url(participants, config)
        except Exception:
            logger.exception("Wallet: could not build Google Wallet save URL")
    return context


def attach_wallet_passes(email, participants, links):
    """Attach the wallet badges and Apple passes that the rendered email refers to."""
    from darts.utils import helpers
    from pokemon.services import wallet_apple

    if links.get("google_wallet_url"):
        helpers.attach_image(email, GOOGLE_BADGE, from_pokemon=True)
    if not links.get("apple_wallet_url"):
        return
    if links.get("apple_wallet_badge"):
        helpers.attach_image(email, APPLE_BADGE, from_pokemon=True)

    config = apple_config()
    for participant in participants:
        try:
            content = wallet_apple.build_pkpass(participant, config)
        except Exception:
            logger.exception("Wallet: could not build Apple pass for participant %s", participant.pk)
            continue
        email.attach(f"ticket-{participant.pk}.pkpass", content, wallet_apple.PKPASS_CONTENT_TYPE)
