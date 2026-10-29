"""Build signed Apple Wallet passes (.pkpass) for event tickets."""

import hashlib
import io
import json
import zipfile
from datetime import timedelta
from functools import lru_cache

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.serialization import pkcs7
from django.contrib.staticfiles import finders
from PIL import Image, ImageOps

from chudartz.ticket_renderer import _format_access_period
from darts.templatetags.dutch_date import MONTHS_DUTCH, dutch_time
from pokemon.services.calendar import BRUSSELS, _aware
from pokemon.services.wallet import (
    BACKGROUND_COLOR,
    BAND_COLOR,
    CONTACT_EMAIL,
    ORGANIZATION_NAME,
    holder_name,
    iso_datetime,
    plain_text,
    toegang_tijden,
    venue_name,
)

PKPASS_CONTENT_TYPE = "application/vnd.apple.pkpass"
PKPASSES_CONTENT_TYPE = "application/vnd.apple.pkpasses"

FOREGROUND_COLOR = (255, 255, 255)
LABEL_COLOR = (240, 96, 104)

SCALES = (1, 2, 3)
ICON_SIZE = (29, 29)
LOGO_MAX_SIZE = (160, 50)
STRIP_SIZE = (375, 98)
BAND_LOGO_HEIGHT = 0.78


def _rgb(color):
    return "rgb({},{},{})".format(*color)


def _png_bytes(image):
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def _suffix(scale):
    return "" if scale == 1 else f"@{scale}x"


def _scaled(size, scale):
    return (size[0] * scale, size[1] * scale)


def _static_rgba(path):
    return Image.open(finders.find(path)).convert("RGBA")


def band_image(size):
    """The red band with the ChudartZ logo, shared by the Apple strip and the Google hero image."""
    band = Image.new("RGBA", size, BAND_COLOR + (255,))
    logo = ImageOps.contain(
        _static_rgba("pokemon/img/logo-black.png"),
        (size[0], int(size[1] * BAND_LOGO_HEIGHT)),
        Image.LANCZOS,
    )
    band.alpha_composite(logo, ((size[0] - logo.width) // 2, (size[1] - logo.height) // 2))
    return band.convert("RGB")


@lru_cache(maxsize=1)
def _images():
    icon = _static_rgba("pokemon/img/apple-touch-icon.png")
    mark = _static_rgba("pokemon/img/android-chrome-512x512.png")
    files = {}
    for scale in SCALES:
        suffix = _suffix(scale)
        files[f"icon{suffix}.png"] = _png_bytes(icon.resize(_scaled(ICON_SIZE, scale), Image.LANCZOS))
        files[f"logo{suffix}.png"] = _png_bytes(
            ImageOps.contain(mark, _scaled(LOGO_MAX_SIZE, scale), Image.LANCZOS)
        )
        files[f"strip{suffix}.png"] = _png_bytes(band_image(_scaled(STRIP_SIZE, scale)))
    return files


def _full_date(value):
    local = _aware(value).astimezone(BRUSSELS)
    return f"{local.day} {MONTHS_DUTCH[local.month][:3]} {local.year}"


def _semantics(participant):
    ticket = participant.ticket
    evenement = ticket.event
    semantics = {
        "eventName": evenement.titel,
        "eventType": "PKEventTypeConvention",
        "eventStartDate": iso_datetime(ticket.get_toegang_start()),
        "eventEndDate": iso_datetime(ticket.get_toegang_einde()),
        "venueName": venue_name(evenement),
        "venueRegionName": plain_text(evenement.locatie_kort),
    }
    if evenement.latitude is not None and evenement.longitude is not None:
        semantics["venueLocation"] = {
            "latitude": float(evenement.latitude),
            "longitude": float(evenement.longitude),
        }
    return semantics


def _right(field):
    return {**field, "textAlignment": "PKTextAlignmentRight"}


def _front_fields(participant):
    ticket = participant.ticket
    evenement = ticket.event
    start = ticket.get_toegang_start()

    auxiliary = [
        {"key": "ticket", "label": "TICKET", "value": ticket.titel},
        _right({"key": "toegang", "label": "TOEGANG", "value": toegang_tijden(ticket)}),
        {"key": "locatie", "label": "LOCATIE", "value": plain_text(evenement.locatie_kort), "row": 1},
    ]
    naam = holder_name(participant)
    if naam:
        auxiliary.append(_right({"key": "naam", "label": "NAAM", "value": naam, "row": 1}))

    return {
        "headerFields": [{"key": "datum", "label": dutch_time(start), "value": _full_date(start)}],
        "primaryFields": [],
        "secondaryFields": [
            {"key": "evenement", "label": venue_name(evenement).upper(), "value": evenement.titel}
        ],
        "auxiliaryFields": auxiliary,
    }


def serial_number(participant):
    return f"participant-{participant.pk}-{participant.random_seed}"


def pass_json(participant, config):
    ticket = participant.ticket
    evenement = ticket.event
    expires = max(ticket.get_toegang_einde(), evenement.einde_datum) + timedelta(hours=6)

    back = [
        {"key": "periode", "label": "Datum & tijd", "value": _format_access_period(ticket)},
        {"key": "adres", "label": "Adres", "value": plain_text(evenement.locatie_lang)},
        {
            "key": "website",
            "label": "Evenement",
            "value": evenement.get_absolute_url(),
            "attributedValue": f'<a href="{evenement.get_absolute_url()}">Bekijk evenement</a>',
        },
        {"key": "contact", "label": "Vragen?", "value": CONTACT_EMAIL},
    ]

    data = {
        "formatVersion": 1,
        "passTypeIdentifier": config.pass_type_id,
        "teamIdentifier": config.team_id,
        "serialNumber": serial_number(participant),
        "organizationName": ORGANIZATION_NAME,
        "description": f"Ticket {evenement.titel}",
        "backgroundColor": _rgb(BACKGROUND_COLOR),
        "foregroundColor": _rgb(FOREGROUND_COLOR),
        "labelColor": _rgb(LABEL_COLOR),
        "relevantDate": iso_datetime(ticket.get_toegang_start()),
        "expirationDate": iso_datetime(expires),
        "barcodes": [
            {
                "format": "PKBarcodeFormatQR",
                "message": participant.qr_payload,
                "messageEncoding": "iso-8859-1",
            }
        ],
        "semantics": _semantics(participant),
        "eventTicket": {**_front_fields(participant), "backFields": back},
    }

    if evenement.latitude is not None and evenement.longitude is not None:
        data["locations"] = [
            {
                "latitude": float(evenement.latitude),
                "longitude": float(evenement.longitude),
                "relevantText": f"Welkom op {evenement.titel}! Toon je ticket aan de ingang.",
            }
        ]
    return data


def _sign(manifest, config):
    return (
        pkcs7.PKCS7SignatureBuilder()
        .set_data(manifest)
        .add_signer(config.certificate, config.private_key, hashes.SHA256())
        .add_certificate(config.wwdr_certificate)
        .sign(
            serialization.Encoding.DER,
            [pkcs7.PKCS7Options.DetachedSignature, pkcs7.PKCS7Options.Binary],
        )
    )


def build_pkpass(participant, config):
    files = {"pass.json": json.dumps(pass_json(participant, config), ensure_ascii=False).encode("utf-8")}
    files.update(_images())

    manifest = json.dumps(
        {name: hashlib.sha1(content).hexdigest() for name, content in files.items()},
        sort_keys=True,
    ).encode("utf-8")

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
        archive.writestr("manifest.json", manifest)
        archive.writestr("signature", _sign(manifest, config))
    return buffer.getvalue()


def build_pkpasses(participants, config):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_STORED) as archive:
        for participant in participants:
            archive.writestr(f"ticket-{participant.pk}.pkpass", build_pkpass(participant, config))
    return buffer.getvalue()
