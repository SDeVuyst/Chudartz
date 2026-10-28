"""Tests for the event detail page: agenda (.ics), JSON-LD and 'tickets vanaf'."""

import json
from datetime import datetime, timedelta

import pytz
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from djmoney.money import Money

from pokemon.models import (
    CelType,
    Evenement,
    StandhouderInschrijving,
    StandhouderInschrijvingStatus,
    StandhouderTafelKeuze,
    Ticket,
    Zaalplan,
    ZaalplanCel,
)
from pokemon.services.calendar import agenda_context, build_ics, google_calendar_url
from pokemon.services.evenement_seo import build_event_jsonld
from pokemon.views import _sectie_achtergronden, _ticket_prijs_vanaf

BRUSSELS = pytz.timezone("Europe/Brussels")


def _maak_evenement(**overrides):
    velden = {
        "titel": "Pokébeurs Gent, editie 2",
        "slug": "pokebeurs-gent",
        "intro_op_index": "Kopen; verkopen, ruilen",
        "titel_sectie_a": "Over",
        "tekst_sectie_a": "<p>Tekst</p>",
        "start_datum": BRUSSELS.localize(datetime(2030, 7, 6, 10, 0)),
        "einde_datum": BRUSSELS.localize(datetime(2030, 7, 6, 17, 0)),
        "max_deelnemers": 100,
        "locatie_kort": "Gent",
        "locatie_lang": "Expo Gent\nMaaltekouter 1, 9051 Gent",
        "afbeelding": "darts/test.png",
        "enable_inschrijvingen": True,
        "toon_op_site": True,
    }
    velden.update(overrides)
    return Evenement.objects.create(**velden)


def _maak_ticket(evenement, **overrides):
    velden = {
        "event": evenement,
        "titel": "Standaard",
        "price": Money(8, "EUR"),
        "icon": "ticket",
        "max_deelnemers": 50,
        "disable_ticket": False,
    }
    velden.update(overrides)
    return Ticket.objects.create(**velden)


@override_settings(ROOT_URLCONF="pokemon.urls")
class AgendaTests(TestCase):
    def setUp(self):
        self.evenement = _maak_evenement()

    def test_ics_gebruikt_belgische_tijdzone_en_escaped_tekst(self):
        ics = build_ics(self.evenement)

        self.assertIn("BEGIN:VEVENT", ics)
        self.assertIn("BEGIN:VTIMEZONE\r\nTZID:Europe/Brussels", ics)
        self.assertIn("DTSTART;TZID=Europe/Brussels:20300706T100000", ics)
        self.assertIn("DTEND;TZID=Europe/Brussels:20300706T170000", ics)
        self.assertIn("SUMMARY:Pokébeurs Gent\\, editie 2", ics)
        self.assertIn("DESCRIPTION:Kopen\\; verkopen\\, ruilen", ics)
        self.assertIn("LOCATION:Expo Gent\\nMaaltekouter 1\\, 9051 Gent", ics)
        self.assertTrue(ics.endswith("\r\n"))

    def test_ics_regels_zijn_gevouwen(self):
        self.evenement.intro_op_index = "x" * 200
        ics = build_ics(self.evenement)

        for regel in ics.split("\r\n"):
            self.assertLessEqual(len(regel.encode("utf-8")), 75)

    def test_google_url_bevat_datums(self):
        url = google_calendar_url(self.evenement)

        self.assertTrue(url.startswith("https://calendar.google.com/calendar/render?"))
        self.assertIn("dates=20300706T100000%2F20300706T170000", url)
        self.assertIn("ctz=Europe%2FBrussels", url)

    def test_agenda_context_voor_email(self):
        context = agenda_context(self.evenement)

        self.assertIn("agenda_google_url", context)
        self.assertTrue(context["agenda_ics_url"].endswith("/evenement/pokebeurs-gent/agenda.ics"))

    def test_agenda_view(self):
        response = self.client.get(reverse("evenement_agenda", kwargs={"slug": self.evenement.slug}))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["Content-Type"].startswith("text/calendar"))
        self.assertIn('filename="pokebeurs-gent.ics"', response["Content-Disposition"])

    def test_agenda_view_verborgen_evenement(self):
        self.evenement.toon_op_site = False
        self.evenement.save()

        response = self.client.get(reverse("evenement_agenda", kwargs={"slug": self.evenement.slug}))

        self.assertEqual(response.status_code, 404)


class PrijsVanafTests(TestCase):
    def setUp(self):
        self.evenement = _maak_evenement()

    def test_laagste_prijs_van_beschikbare_tickets(self):
        tickets = [
            _maak_ticket(self.evenement, price=Money(12, "EUR")),
            _maak_ticket(self.evenement, price=Money(8, "EUR")),
            _maak_ticket(self.evenement, price=Money(2, "EUR"), disable_ticket=True),
        ]

        self.assertEqual(_ticket_prijs_vanaf(tickets), (False, Money(8, "EUR")))

    def test_gratis_ticket(self):
        tickets = [
            _maak_ticket(self.evenement, price=Money(12, "EUR")),
            _maak_ticket(self.evenement, is_gratis=True),
        ]

        self.assertEqual(_ticket_prijs_vanaf(tickets), (True, None))

    def test_geen_tickets(self):
        self.assertEqual(_ticket_prijs_vanaf([]), (False, None))


class EventJsonLdTests(TestCase):
    def setUp(self):
        self.evenement = _maak_evenement(latitude="51.024500", longitude="3.694600")
        self.request = RequestFactory().get("/")

    def test_event_met_offers(self):
        tickets = [
            _maak_ticket(self.evenement, titel="Online", price=Money(8, "EUR")),
            _maak_ticket(self.evenement, titel="Deur", enkel_inkom=True, price=Money(10, "EUR")),
            _maak_ticket(self.evenement, titel="Uit", disable_ticket=True),
        ]

        data = json.loads(build_event_jsonld(self.evenement, tickets, self.request))

        self.assertEqual(data["@type"], "Event")
        self.assertEqual(data["startDate"], "2030-07-06T10:00:00+02:00")
        self.assertEqual(data["location"]["geo"]["latitude"], 51.0245)
        offers = {offer["name"]: offer for offer in data["offers"]}
        self.assertEqual(set(offers), {"Online", "Deur"})
        self.assertEqual(offers["Online"]["price"], "8.00")
        self.assertEqual(offers["Online"]["availability"], "https://schema.org/InStock")
        self.assertEqual(offers["Deur"]["availability"], "https://schema.org/InStoreOnly")

    def test_uitverkocht_ticket(self):
        ticket = _maak_ticket(self.evenement, max_deelnemers=0)

        data = json.loads(build_event_jsonld(self.evenement, [ticket], self.request))

        self.assertEqual(data["offers"][0]["availability"], "https://schema.org/SoldOut")

    def test_script_tag_wordt_ge_escaped(self):
        self.evenement.titel = "Beurs</script><script>alert(1)</script>"

        output = build_event_jsonld(self.evenement, [], self.request)

        self.assertNotIn("</script>", output)
        self.assertNotIn("<", output)
        self.assertEqual(json.loads(output)["name"], self.evenement.titel)


class StandhouderUitverkochtTests(TestCase):
    def setUp(self):
        self.evenement = _maak_evenement(standhouder_zaalplan_actief=True)
        zaalplan = Zaalplan.objects.create(evenement=self.evenement, rijen=1, kolommen=3)
        self.tafels = [
            ZaalplanCel.objects.create(zaalplan=zaalplan, rij=0, kolom=kolom, cel_type=CelType.TAFEL)
            for kolom in range(2)
        ]
        ZaalplanCel.objects.create(zaalplan=zaalplan, rij=0, kolom=2, cel_type=CelType.LEEG)

    def _boek(self, cel, status=StandhouderInschrijvingStatus.BETAALD):
        inschrijving = StandhouderInschrijving.objects.create(
            evenement=self.evenement,
            status=status,
            bedrijfsnaam="Stand BV",
            naam="Tester",
            email="stand@example.com",
            telefoon="+32470000000",
        )
        StandhouderTafelKeuze.objects.create(inschrijving=inschrijving, cel=cel)

    def test_vrije_tafel(self):
        self._boek(self.tafels[0])

        self.assertFalse(self.evenement.standhouder_tafels_uitverkocht)

    def test_alle_tafels_bezet(self):
        self._boek(self.tafels[0])
        self._boek(self.tafels[1], status=StandhouderInschrijvingStatus.INGEDIEND)

        self.assertTrue(self.evenement.standhouder_tafels_uitverkocht)

    def test_concept_telt_niet_als_bezet(self):
        self._boek(self.tafels[0])
        self._boek(self.tafels[1], status=StandhouderInschrijvingStatus.CONCEPT)

        self.assertFalse(self.evenement.standhouder_tafels_uitverkocht)

    def test_zonder_zaalplan_nooit_uitverkocht(self):
        self._boek(self.tafels[0])
        self._boek(self.tafels[1])
        self.evenement.standhouder_zaalplan_actief = False

        self.assertFalse(self.evenement.standhouder_tafels_uitverkocht)


@override_settings(ROOT_URLCONF="pokemon.urls")
class EvenementPaginaTests(TestCase):
    def test_pagina_rendert(self):
        evenement = _maak_evenement(
            standhouder_prijzen="Tafel: €50\n",
            standhouder_inbegrepen="Stoelen\r\nStroom",
        )
        online = _maak_ticket(evenement)
        deur = _maak_ticket(evenement, titel="Deur", enkel_inkom=True, price=Money(10, "EUR"))

        response = self.client.get(reverse("evenement", kwargs={"slug": evenement.slug}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "application/ld+json")
        self.assertContains(response, 'id="standhouder"')
        self.assertContains(response, "Tickets vanaf")
        self.assertContains(response, 'class="ticket-deur')
        self.assertEqual(response.context["prijs_vanaf"], Money(8, "EUR"))
        self.assertEqual(response.context["online_tickets"], [online])
        self.assertEqual(response.context["deur_tickets"], [deur])
        self.assertContains(response, "Liever ter plaatse betalen?")
        self.assertEqual(response.context["achtergrond"], {"standhouder": ""})

    def test_gratis_deurticket_vraagt_niet_om_te_betalen(self):
        evenement = _maak_evenement()
        _maak_ticket(evenement)
        _maak_ticket(evenement, titel="Kids", enkel_inkom=True, is_gratis=True)

        response = self.client.get(reverse("evenement", kwargs={"slug": evenement.slug}))

        self.assertNotContains(response, "Liever ter plaatse betalen?")
        self.assertContains(response, "Of kom gewoon langs")


class SectieAchtergrondTests(TestCase):
    def test_wisselt_af_over_zichtbare_secties(self):
        self.assertEqual(
            _sectie_achtergronden(standhouder=True, fotos=False, partners=True, andere_evenementen=True),
            {"standhouder": "", "partners": "light-background", "andere_evenementen": ""},
        )
