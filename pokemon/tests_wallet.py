"""Tests for Apple Wallet / Google Wallet ticket passes."""

import base64
import hashlib
import io
import json
import os
import zipfile
from datetime import datetime, timedelta
from decimal import Decimal
from unittest import mock

import jwt
import pytz
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs7
from cryptography.x509.oid import NameOID
from django.core.mail import EmailMessage
from django.test import RequestFactory, SimpleTestCase
from djmoney.money import Money

from pokemon import views
from pokemon.models import Evenement, Participant, Payment, Ticket
from pokemon.services import wallet, wallet_apple, wallet_google

BRUSSELS = pytz.timezone("Europe/Brussels")


def _b64(data):
    return base64.b64encode(data).decode()


def _make_cert(common_name, key, issuer_name=None, issuer_key=None):
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    now = datetime.now(pytz.utc)
    return (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer_name or subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=1))
        .sign(issuer_key or key, hashes.SHA256())
    )


def _pem(cert):
    return cert.public_bytes(serialization.Encoding.PEM)


def _wallet_env():
    wwdr_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    wwdr = _make_cert("Test WWDR", wwdr_key)
    pass_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pass_cert = _make_cert("Pass Type ID: pass.test", pass_key, wwdr.subject, wwdr_key)
    google_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    service_account = {
        "type": "service_account",
        "client_email": "wallet@test.iam.gserviceaccount.com",
        "private_key_id": "test-key-id",
        "private_key": google_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ).decode(),
    }
    env = {
        "APPLE_PASS_TYPE_ID": "pass.test",
        "APPLE_TEAM_ID": "TEAM123456",
        "APPLE_PASS_CERT_B64": _b64(_pem(pass_cert)),
        "APPLE_PASS_KEY_B64": _b64(
            pass_key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.TraditionalOpenSSL,
                serialization.NoEncryption(),
            )
        ),
        "APPLE_WWDR_CERT_B64": _b64(_pem(wwdr)),
        "GOOGLE_WALLET_ISSUER_ID": "3388000000000000001",
        "GOOGLE_WALLET_SERVICE_ACCOUNT_B64": _b64(json.dumps(service_account).encode()),
    }
    return env, pass_cert, wwdr, google_key.public_key()


NO_WALLET_ENV = {
    name: ""
    for name in [
        "APPLE_PASS_TYPE_ID",
        "APPLE_TEAM_ID",
        "APPLE_PASS_CERT_B64",
        "APPLE_PASS_KEY_B64",
        "APPLE_WWDR_CERT_B64",
        "GOOGLE_WALLET_ISSUER_ID",
        "GOOGLE_WALLET_SERVICE_ACCOUNT_B64",
    ]
}


def _participant(pk=7, seed="aB3dE5gH7j", **evenement_overrides):
    velden = {
        "pk": 3,
        "titel": "Pokébeurs Gent",
        "slug": "pokebeurs-gent",
        "start_datum": BRUSSELS.localize(datetime(2030, 7, 6, 10, 0)),
        "einde_datum": BRUSSELS.localize(datetime(2030, 7, 6, 17, 0)),
        "locatie_kort": "Gent",
        "locatie_lang": "Expo Gent\nMaaltekouter 1, 9051 Gent",
        "latitude": Decimal("51.0244"),
        "longitude": Decimal("3.6919"),
    }
    velden.update(evenement_overrides)
    evenement = Evenement(**velden)
    ticket = Ticket(pk=5, titel="Early Bird", price=Money(8, "EUR"), event=evenement)
    payment = Payment(pk=11, first_name="Ash", last_name="Ketchum")
    return Participant(pk=pk, random_seed=seed, ticket=ticket, payment=payment)


class WalletTestCase(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env, cls.pass_cert, cls.wwdr, cls.google_public_key = _wallet_env()

    def setUp(self):
        patcher = mock.patch.dict(os.environ, self.env)
        patcher.start()
        self.addCleanup(patcher.stop)


class ConfigTests(SimpleTestCase):
    @mock.patch.dict(os.environ, NO_WALLET_ENV)
    def test_missing_env_disables_wallet(self):
        self.assertIsNone(wallet.apple_config())
        self.assertIsNone(wallet.google_config())
        self.assertEqual(wallet.wallet_context([_participant()]), {})

    @mock.patch.dict(os.environ, {**NO_WALLET_ENV, "GOOGLE_WALLET_ISSUER_ID": "1", "GOOGLE_WALLET_SERVICE_ACCOUNT_B64": "REPLACE_ME"})
    def test_invalid_base64_disables_wallet(self):
        self.assertIsNone(wallet.google_config())


class ApplePassTests(WalletTestCase):
    def _open(self, participant=None):
        content = wallet_apple.build_pkpass(participant or _participant(), wallet.apple_config())
        return zipfile.ZipFile(io.BytesIO(content))

    def test_pkpass_contains_required_files(self):
        names = set(self._open().namelist())
        for required in ["pass.json", "manifest.json", "signature", "icon.png", "icon@2x.png", "logo.png", "strip@3x.png"]:
            self.assertIn(required, names)

    def test_manifest_hashes_match_files(self):
        archive = self._open()
        manifest = json.loads(archive.read("manifest.json"))
        self.assertEqual(set(manifest), set(archive.namelist()) - {"manifest.json", "signature"})
        for name, digest in manifest.items():
            self.assertEqual(hashlib.sha1(archive.read(name)).hexdigest(), digest)

    def test_signature_contains_signer_and_wwdr(self):
        certificates = pkcs7.load_der_pkcs7_certificates(self._open().read("signature"))
        self.assertIn(self.pass_cert, certificates)
        self.assertIn(self.wwdr, certificates)

    def test_pass_json_fields(self):
        data = json.loads(self._open().read("pass.json"))
        self.assertEqual(data["passTypeIdentifier"], "pass.test")
        self.assertEqual(data["teamIdentifier"], "TEAM123456")
        self.assertEqual(data["serialNumber"], "participant-7-aB3dE5gH7j")
        self.assertEqual(data["barcodes"][0]["message"], "7aB3dE5gH7j")
        self.assertEqual(data["relevantDate"], "2030-07-06T10:00:00+02:00")
        self.assertEqual(data["locations"][0]["latitude"], 51.0244)
        self.assertNotIn("altText", data["barcodes"][0])
        self.assertNotIn("ticketnummer", {field["key"] for field in data["eventTicket"]["backFields"]})
        self.assertEqual(data["semantics"]["eventName"], "Pokébeurs Gent")
        self.assertEqual(data["semantics"]["venueLocation"], {"latitude": 51.0244, "longitude": 3.6919})

    def test_band_layout(self):
        fields = json.loads(self._open().read("pass.json"))["eventTicket"]
        self.assertEqual(fields["headerFields"][0], {"key": "datum", "label": "10:00", "value": "6 jul 2030"})
        self.assertEqual(fields["primaryFields"], [])
        self.assertEqual(fields["secondaryFields"][0]["label"], "EXPO GENT")
        self.assertEqual(fields["secondaryFields"][0]["value"], "Pokébeurs Gent")
        rows = {field["key"]: (field.get("row", 0), field.get("textAlignment")) for field in fields["auxiliaryFields"]}
        self.assertEqual(rows, {
            "ticket": (0, None),
            "toegang": (0, "PKTextAlignmentRight"),
            "locatie": (1, None),
            "naam": (1, "PKTextAlignmentRight"),
        })

    def test_pass_without_coordinates_has_no_locations(self):
        data = json.loads(self._open(_participant(latitude=None, longitude=None)).read("pass.json"))
        self.assertNotIn("locations", data)

    def test_pkpasses_bundle_contains_each_ticket(self):
        content = wallet_apple.build_pkpasses([_participant(pk=1), _participant(pk=2)], wallet.apple_config())
        names = zipfile.ZipFile(io.BytesIO(content)).namelist()
        self.assertEqual(names, ["ticket-1.pkpass", "ticket-2.pkpass"])


class GoogleSaveUrlTests(WalletTestCase):
    def _claims(self, participants):
        url = wallet_google.save_url(participants, wallet.google_config())
        self.assertTrue(url.startswith(wallet_google.SAVE_URL_PREFIX))
        token = url[len(wallet_google.SAVE_URL_PREFIX):]
        return jwt.decode(token, self.google_public_key, algorithms=["RS256"], audience="google")

    def test_jwt_is_signed_with_service_account(self):
        claims = self._claims([_participant()])
        self.assertEqual(claims["iss"], "wallet@test.iam.gserviceaccount.com")
        self.assertEqual(claims["typ"], "savetowallet")

    def test_jwt_contains_class_and_object(self):
        payload = self._claims([_participant()])["payload"]
        [event_class] = payload["eventTicketClasses"]
        [ticket_object] = payload["eventTicketObjects"]
        self.assertEqual(event_class["id"], "3388000000000000001.evenement-3")
        self.assertEqual(event_class["eventName"]["defaultValue"]["value"], "Pokébeurs Gent")
        self.assertEqual(ticket_object["id"], "3388000000000000001.participant-7-aB3dE5gH7j")
        self.assertEqual(ticket_object["classId"], event_class["id"])
        self.assertEqual(ticket_object["barcode"], {"type": "QR_CODE", "value": "7aB3dE5gH7j"})
        self.assertEqual(ticket_object["ticketHolderName"], "Ash Ketchum")

    def test_google_pass_matches_apple_design(self):
        [event_class] = self._claims([_participant()])["payload"]["eventTicketClasses"]
        self.assertEqual(event_class["hexBackgroundColor"], "#1e2126")
        self.assertTrue(event_class["heroImage"]["sourceUri"]["uri"].endswith("/static/pokemon/img/wallet-band.png"))
        self.assertTrue(event_class["logo"]["sourceUri"]["uri"].endswith("/static/pokemon/img/android-chrome-512x512.png"))
        self.assertEqual(event_class["venue"]["name"]["defaultValue"]["value"], "Expo Gent")

    def test_one_class_per_event_for_multiple_tickets(self):
        payload = self._claims([_participant(pk=1), _participant(pk=2)])["payload"]
        self.assertEqual(len(payload["eventTicketClasses"]), 1)
        self.assertEqual(len(payload["eventTicketObjects"]), 2)


class WalletContextTests(WalletTestCase):
    def test_context_has_both_links(self):
        context = wallet.wallet_context([_participant()])
        self.assertIn("/pokemon/wallet/apple/", context["apple_wallet_url"])
        self.assertTrue(context["google_wallet_url"].startswith(wallet_google.SAVE_URL_PREFIX))

    def test_token_round_trip_rejects_tampering(self):
        token = wallet.apple_pass_token(participant=_participant())
        self.assertIsNone(wallet.participants_for_apple_token(token + "x"))
        self.assertIsNone(wallet.participants_for_apple_token("not-a-token"))

    def test_attach_wallet_passes_adds_pkpass_and_badges(self):
        participant = _participant()
        email = EmailMessage("s", "b", "from@test", ["to@test"])
        wallet.attach_wallet_passes(email, [participant], wallet.wallet_context([participant]))
        filenames = [
            attachment[0] if isinstance(attachment, tuple) else attachment.get_filename()
            for attachment in email.attachments
        ]
        self.assertIn("ticket-7.pkpass", filenames)
        self.assertIn("google-wallet-badge.png", filenames)


class WalletAppleViewTests(WalletTestCase):
    def setUp(self):
        super().setUp()
        self.factory = RequestFactory()

    def test_bad_token_returns_404(self):
        response = views.wallet_apple(self.factory.get("/"), "bad-token")
        self.assertEqual(response.status_code, 404)

    def test_single_participant_returns_pkpass(self):
        with mock.patch.object(wallet, "participants_for_apple_token", return_value=[_participant()]):
            response = views.wallet_apple(self.factory.get("/"), "token")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], wallet_apple.PKPASS_CONTENT_TYPE)

    def test_multiple_participants_return_pkpasses(self):
        participants = [_participant(pk=1), _participant(pk=2)]
        with mock.patch.object(wallet, "participants_for_apple_token", return_value=participants):
            response = views.wallet_apple(self.factory.get("/"), "token")
        self.assertEqual(response["Content-Type"], wallet_apple.PKPASSES_CONTENT_TYPE)

    @mock.patch.dict(os.environ, NO_WALLET_ENV)
    def test_unconfigured_returns_404(self):
        with mock.patch.object(wallet, "participants_for_apple_token", return_value=[_participant()]):
            response = views.wallet_apple(self.factory.get("/"), "token")
        self.assertEqual(response.status_code, 404)
