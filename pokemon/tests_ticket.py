from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from djmoney.money import Money

from pokemon.models import Ticket
from pokemon.services.ticket import TicketValidationError, validate_ticket_selection
from pokemon.ticket_wizard import get_beschikbare_tickets


class TicketEigenschappenTests(SimpleTestCase):
    def test_regels_splits_and_strips_lines(self):
        self.assertEqual(
            Ticket._regels("  Toegang tot de beurs\n\n Early entry \n"),
            ["Toegang tot de beurs", "Early entry"],
        )

    def test_voordelen_en_nadelen_komen_uit_tekstvelden(self):
        ticket = Ticket(
            voordelen_tekst="Toegang tot alle hallen\nVIP lounge",
            nadelen_tekst="Geen early access",
        )
        self.assertEqual(ticket.voordelen, ["Toegang tot alle hallen", "VIP lounge"])
        self.assertEqual(ticket.nadelen, ["Geen early access"])

    def test_is_online_koopbaar_negeert_inkom_en_uitgeschakelde_tickets(self):
        self.assertTrue(Ticket(disable_ticket=False, enkel_inkom=False).is_online_koopbaar)
        self.assertFalse(Ticket(disable_ticket=True, enkel_inkom=False).is_online_koopbaar)
        self.assertFalse(Ticket(disable_ticket=False, enkel_inkom=True).is_online_koopbaar)

    def test_gratis_zet_prijs_op_nul(self):
        ticket = Ticket(is_gratis=True, price=Money(Decimal("12.50"), "EUR"), disable_ticket=False)
        with patch("django.db.models.Model.save"):
            Ticket.save(ticket)
        self.assertEqual(ticket.price.amount, Decimal("0.00"))


class TicketWizardBeschikbaarheidTests(SimpleTestCase):
    def test_get_beschikbare_tickets_sluit_inkomtickets_uit(self):
        evenement = SimpleNamespace()
        qs = SimpleNamespace()
        captured = {}

        def filter(**kwargs):
            captured.update(kwargs)
            return qs

        qs.filter = filter
        qs.order_by = lambda *_: qs

        with patch("pokemon.ticket_wizard.Ticket.objects") as objects:
            objects.filter.side_effect = filter
            get_beschikbare_tickets(evenement)

        self.assertEqual(captured["enkel_inkom"], False)
        self.assertEqual(captured["disable_ticket"], False)
        self.assertIs(captured["event"], evenement)

    def test_validate_weigert_inkomticket(self):
        evenement = SimpleNamespace(enable_inschrijvingen=True, is_sold_out=False)
        ticket = SimpleNamespace(
            disable_ticket=False,
            enkel_inkom=True,
            is_sold_out=False,
            remaining_tickets=10,
            titel="Inkom",
        )

        with patch("pokemon.services.ticket.Ticket.objects") as objects:
            objects.get.return_value = ticket
            with self.assertRaises(TicketValidationError):
                validate_ticket_selection(evenement, {1: 1})
