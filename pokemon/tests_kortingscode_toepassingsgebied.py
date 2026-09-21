"""Tests for kortingscode toepassingsgebied (tickets vs standhouders)."""

from datetime import datetime, timedelta
from decimal import Decimal

import pytz
from django.test import TestCase
from djmoney.money import Money

from pokemon.models import (
    Evenement,
    Kortingscode,
    KortingscodeToepassingsgebied,
    KortingscodeType,
    StandhouderInschrijving,
    StandhouderInschrijvingStatus,
    Ticket,
)
from pokemon.services.standhouder import (
    StandhouderValidationError,
    validate_standhouder_kortingscode,
)
from pokemon.services.ticket import TicketValidationError, validate_kortingscode
from pokemon.standhouder_wizard import build_prijsopbouw

BRUSSELS = pytz.timezone("Europe/Brussels")


class KortingscodeToepassingsgebiedTests(TestCase):
    def setUp(self):
        self.evenement = Evenement.objects.create(
            titel="Test Event",
            slug="test-korting-scope",
            intro_op_index="x",
            titel_sectie_a="x",
            tekst_sectie_a="<p>x</p>",
            start_datum=BRUSSELS.localize(datetime.now() + timedelta(days=10)),
            einde_datum=BRUSSELS.localize(datetime.now() + timedelta(days=10, hours=8)),
            max_deelnemers=100,
            locatie_kort="Gent",
            locatie_lang="Gent",
            afbeelding="darts/test.png",
            enable_inschrijvingen=True,
            enable_standhouder=True,
            standhouder_zaalplan_actief=False,
            standhouder_prijs_per_tafel=Money(100, "EUR"),
        )
        self.ticket = Ticket.objects.create(
            event=self.evenement,
            titel="Standard",
            price=Money(50, "EUR"),
            icon="bi-ticket",
            max_deelnemers=50,
            disable_ticket=False,
        )
        self.ticket_code = Kortingscode.objects.create(
            code="DUPLICAAT",
            toepassingsgebied=KortingscodeToepassingsgebied.TICKETS,
            discount_type=KortingscodeType.PERCENT,
            amount=Decimal("15"),
            actief=True,
        )
        self.stand_code = Kortingscode.objects.create(
            code="DUPLICAAT",
            toepassingsgebied=KortingscodeToepassingsgebied.STANDHOUDERS,
            discount_type=KortingscodeType.FIXED,
            amount=Decimal("50"),
            actief=True,
        )

    def test_duplicate_code_allowed_across_scopes(self):
        self.assertEqual(
            Kortingscode.objects.filter(code__iexact="DUPLICAAT").count(), 2
        )

    def test_ticket_lookup_uses_ticket_instance(self):
        quantities = {self.ticket.pk: 2}
        obj, korting = validate_kortingscode("DUPLICAAT", self.evenement, quantities)
        self.assertEqual(obj.pk, self.ticket_code.pk)
        self.assertEqual(korting, Decimal("15.00"))  # 15% of 100

    def test_ticket_rejects_standhouder_only_code(self):
        Kortingscode.objects.filter(pk=self.ticket_code.pk).delete()
        with self.assertRaises(TicketValidationError):
            validate_kortingscode("DUPLICAAT", self.evenement, {self.ticket.pk: 1})

    def test_standhouder_lookup_uses_standhouder_instance(self):
        obj, korting = validate_standhouder_kortingscode(
            "DUPLICAAT", self.evenement, Decimal("200")
        )
        self.assertEqual(obj.pk, self.stand_code.pk)
        self.assertEqual(korting, Decimal("50"))

    def test_standhouder_rejects_ticket_only_code(self):
        Kortingscode.objects.filter(pk=self.stand_code.pk).delete()
        with self.assertRaises(StandhouderValidationError):
            validate_standhouder_kortingscode("DUPLICAAT", self.evenement, Decimal("200"))

    def test_prijsopbouw_includes_korting_line(self):
        inschrijving = StandhouderInschrijving.objects.create(
            evenement=self.evenement,
            status=StandhouderInschrijvingStatus.CONCEPT,
            bedrijfsnaam="Test BV",
            naam="Test User",
            email="test@example.com",
            telefoon="+32470000000",
            aantal_tafels_manueel=2,
        )
        regels, totaal = build_prijsopbouw(
            inschrijving, self.stand_code, Decimal("50")
        )
        self.assertTrue(any(r.get("is_korting") for r in regels))
        self.assertEqual(totaal, Decimal("150"))  # 2*100 - 50
