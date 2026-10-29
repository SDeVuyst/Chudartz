"""Build Google Wallet "save" links (signed JWT) for event tickets."""

import logging
import time

import jwt
from django.templatetags.static import static

from chudartz.ticket_renderer import _format_access_period
from pokemon.services.wallet import (
    BACKGROUND_COLOR,
    ORGANIZATION_NAME,
    absolute_url,
    holder_name,
    iso_datetime,
    plain_text,
    toegang_tijden,
    venue_name,
)

logger = logging.getLogger(__name__)

SAVE_URL_PREFIX = "https://pay.google.com/gp/v/save/"
SAFE_JWT_LENGTH = 1800
LANGUAGE = "nl"
LOGO = "pokemon/img/android-chrome-512x512.png"
# Generated from wallet_apple.band_image((1032, 336)) so it matches the Apple strip.
HERO_IMAGE = "pokemon/img/wallet-band.png"


def _localized(value):
    return {"defaultValue": {"language": LANGUAGE, "value": value}}


def class_id(config, evenement):
    return f"{config.issuer_id}.evenement-{evenement.pk}"


def object_id(config, participant):
    return f"{config.issuer_id}.participant-{participant.pk}-{participant.random_seed}"


def event_class(config, evenement):
    data = {
        "id": class_id(config, evenement),
        "issuerName": ORGANIZATION_NAME,
        "reviewStatus": "UNDER_REVIEW",
        "eventName": _localized(evenement.titel),
        "venue": {
            "name": _localized(venue_name(evenement)),
            "address": _localized(plain_text(evenement.locatie_lang)),
        },
        "dateTime": {
            "start": iso_datetime(evenement.start_datum),
            "end": iso_datetime(evenement.einde_datum),
        },
        "logo": {
            "sourceUri": {"uri": absolute_url(static(LOGO))},
            "contentDescription": _localized(ORGANIZATION_NAME),
        },
        "heroImage": {
            "sourceUri": {"uri": absolute_url(static(HERO_IMAGE))},
            "contentDescription": _localized(ORGANIZATION_NAME),
        },
        "hexBackgroundColor": "#{:02x}{:02x}{:02x}".format(*BACKGROUND_COLOR),
        "homepageUri": {"uri": evenement.get_absolute_url(), "description": "Evenement"},
    }
    if evenement.latitude is not None and evenement.longitude is not None:
        data["locations"] = [
            {"latitude": float(evenement.latitude), "longitude": float(evenement.longitude)}
        ]
    return data


def ticket_object(config, participant):
    ticket = participant.ticket
    data = {
        "id": object_id(config, participant),
        "classId": class_id(config, ticket.event),
        "state": "ACTIVE",
        "ticketType": _localized(ticket.titel),
        "barcode": {"type": "QR_CODE", "value": participant.qr_payload},
        "textModulesData": [
            {"id": "toegang", "header": "Toegang", "body": toegang_tijden(ticket)},
            {"id": "locatie", "header": "Locatie", "body": plain_text(ticket.event.locatie_kort)},
            {"id": "periode", "header": "Datum & tijd", "body": _format_access_period(ticket)},
        ],
    }
    naam = holder_name(participant)
    if naam:
        data["ticketHolderName"] = naam
    return data


def jwt_claims(participants, config):
    classes = {}
    objects = []
    for participant in participants:
        evenement = participant.ticket.event
        classes.setdefault(evenement.pk, event_class(config, evenement))
        objects.append(ticket_object(config, participant))

    return {
        "iss": config.service_account_email,
        "aud": "google",
        "typ": "savetowallet",
        "iat": int(time.time()),
        "payload": {
            "eventTicketClasses": list(classes.values()),
            "eventTicketObjects": objects,
        },
    }


def save_url(participants, config):
    headers = {"kid": config.private_key_id} if config.private_key_id else None
    token = jwt.encode(jwt_claims(participants, config), config.private_key, algorithm="RS256", headers=headers)
    if len(token) > SAFE_JWT_LENGTH:
        logger.info("Wallet: Google save JWT is %s characters (safe limit %s)", len(token), SAFE_JWT_LENGTH)
    return SAVE_URL_PREFIX + token
