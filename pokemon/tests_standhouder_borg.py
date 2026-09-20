"""Tests for standhouder tafelborg + vragenborg breakdown."""

import json
from decimal import Decimal
from unittest.mock import MagicMock, PropertyMock, patch

from django.template.loader import render_to_string
from django.test import SimpleTestCase
from django.utils import timezone
from djmoney.money import Money

from pokemon.models import (
    Evenement,
    StandhouderInschrijving,
    StandhouderVraag,
    StandhouderVraagAntwoord,
    VraagType,
    Zaalplan,
    ZaalplanCel,
    CelType,
)


def _evenement(**kwargs):
    now = timezone.now()
    defaults = {
        "titel": "Borg Event",
        "intro_op_index": "intro",
        "slug": "borg-event",
        "titel_sectie_a": "Sectie",
        "tekst_sectie_a": "tekst",
        "start_datum": now,
        "einde_datum": now,
        "max_deelnemers": 100,
        "locatie_kort": "Gent",
        "locatie_lang": "Gent",
        "afbeelding": "test.jpg",
        "standhouder_inbegrepen": "",
        "standhouder_prijzen": "",
        "standhouder_zaalplan_actief": False,
        "standhouder_prijs_per_tafel": Money(Decimal("15.00"), "EUR"),
        "standhouder_borg_per_tafel": Money(Decimal("0.00"), "EUR"),
        "standhouder_prijs_excl_btw": False,
        "standhouder_prijs_btw_percentage": Decimal("21.00"),
    }
    defaults.update(kwargs)
    return Evenement(**defaults)


def _boolean_borg_vraag(pk=1, volgorde=0, toeslag="15.00", **kwargs):
    defaults = {
        "pk": pk,
        "tekst": f"Vraagtekst {pk}",
        "vraag_type": VraagType.BOOLEAN,
        "volgorde": volgorde,
        "is_borg": True,
        "prijs_toeslag": Money(Decimal(toeslag), "EUR"),
        "prijs_toeslag_excl_btw": False,
        "prijs_toeslag_btw_percentage": Decimal("21.00"),
    }
    defaults.update(kwargs)
    return StandhouderVraag(**defaults)


def _patch_antwoorden(inschrijving, antwoorden):
    related = MagicMock()
    related.select_related.return_value = antwoorden
    # borg_regels uses order_by on the queryset
    ordered = MagicMock()
    ordered.select_related.return_value = antwoorden
    # also support .order_by().select_related()
    qs = MagicMock()
    qs.select_related.return_value = antwoorden
    qs.order_by.return_value = qs
    # chain: antwoorden.select_related("vraag").order_by(...)
    select_related_result = MagicMock()
    select_related_result.__iter__ = lambda self: iter(antwoorden)
    select_related_result.order_by.return_value = antwoorden
    related.select_related.return_value = select_related_result
    # For borg_bedrag_vragen: for antwoord in self.antwoorden.select_related("vraag")
    # iterating select_related result
    return patch.object(StandhouderInschrijving, "antwoorden", related)


def _mock_vragen_qs(vraag_ids):
    """Mock evenement.standhouder_vragen.order_by().values_list()."""
    qs = MagicMock()
    qs.order_by.return_value = qs
    qs.values_list.return_value = list(vraag_ids)
    return qs


class EffectieveBorgCelTests(SimpleTestCase):
    def test_null_borg_is_zero(self):
        zaalplan = Zaalplan(standaard_prijs=Money(Decimal("50.00"), "EUR"))
        cel = ZaalplanCel(zaalplan=zaalplan, rij=0, kolom=0, cel_type=CelType.TAFEL)
        self.assertIsNone(cel.borg)
        self.assertEqual(cel.effectieve_borg, Decimal("0"))

    def test_borg_lager_dan_prijs(self):
        zaalplan = Zaalplan(standaard_prijs=Money(Decimal("50.00"), "EUR"))
        cel = ZaalplanCel(
            zaalplan=zaalplan,
            rij=0,
            kolom=0,
            cel_type=CelType.TAFEL,
            borg=Money(Decimal("10.00"), "EUR"),
        )
        self.assertEqual(cel.effectieve_borg, Decimal("10.00"))

    def test_borg_geclampt_tot_prijs(self):
        zaalplan = Zaalplan(standaard_prijs=Money(Decimal("15.00"), "EUR"))
        cel = ZaalplanCel(
            zaalplan=zaalplan,
            rij=0,
            kolom=0,
            cel_type=CelType.TAFEL,
            borg=Money(Decimal("99.00"), "EUR"),
        )
        self.assertEqual(cel.effectieve_borg, Decimal("15.00"))

    def test_borg_met_prijs_override(self):
        zaalplan = Zaalplan(standaard_prijs=Money(Decimal("50.00"), "EUR"))
        cel = ZaalplanCel(
            zaalplan=zaalplan,
            rij=0,
            kolom=0,
            cel_type=CelType.TAFEL,
            prijs=Money(Decimal("20.00"), "EUR"),
            borg=Money(Decimal("12.00"), "EUR"),
        )
        self.assertEqual(cel.effectieve_prijs.amount, Decimal("20.00"))
        self.assertEqual(cel.effectieve_borg, Decimal("12.00"))


class FlatTafelBorgTests(SimpleTestCase):
    def test_geen_borg_default(self):
        evenement = _evenement()
        inschrijving = StandhouderInschrijving(
            evenement=evenement, aantal_tafels_manueel=2
        )
        with _patch_antwoorden(inschrijving, []):
            self.assertEqual(inschrijving.borg_bedrag_tafels, Decimal("0"))
            self.assertEqual(inschrijving.borg_bedrag, Decimal("0"))
            self.assertFalse(inschrijving.heeft_borg)
            with patch.object(
                type(evenement),
                "standhouder_vragen",
                new_callable=PropertyMock,
                return_value=_mock_vragen_qs([]),
            ):
                self.assertEqual(inschrijving.borg_regels(), [])

    def test_borg_deel_van_prijs_maal_aantal(self):
        evenement = _evenement(
            standhouder_prijs_per_tafel=Money(Decimal("15.00"), "EUR"),
            standhouder_borg_per_tafel=Money(Decimal("10.00"), "EUR"),
        )
        inschrijving = StandhouderInschrijving(
            evenement=evenement, aantal_tafels_manueel=2
        )
        with _patch_antwoorden(inschrijving, []):
            self.assertEqual(inschrijving.bereken_totaal(), Decimal("30.00"))
            self.assertEqual(inschrijving.borg_bedrag_tafels, Decimal("20.00"))
            self.assertEqual(inschrijving.borg_bedrag, Decimal("20.00"))
            self.assertTrue(inschrijving.heeft_borg)

    def test_borg_gelijk_aan_prijs(self):
        evenement = _evenement(
            standhouder_prijs_per_tafel=Money(Decimal("15.00"), "EUR"),
            standhouder_borg_per_tafel=Money(Decimal("15.00"), "EUR"),
        )
        inschrijving = StandhouderInschrijving(
            evenement=evenement, aantal_tafels_manueel=2
        )
        with _patch_antwoorden(inschrijving, []):
            self.assertEqual(inschrijving.borg_bedrag_tafels, Decimal("30.00"))
            self.assertEqual(inschrijving.bereken_totaal(), Decimal("30.00"))

    def test_borg_geclampt_boven_prijs(self):
        evenement = _evenement(
            standhouder_prijs_per_tafel=Money(Decimal("15.00"), "EUR"),
            standhouder_borg_per_tafel=Money(Decimal("40.00"), "EUR"),
        )
        inschrijving = StandhouderInschrijving(
            evenement=evenement, aantal_tafels_manueel=1
        )
        with _patch_antwoorden(inschrijving, []):
            self.assertEqual(inschrijving.borg_bedrag_tafels, Decimal("15.00"))
            self.assertEqual(inschrijving.bereken_totaal(), Decimal("15.00"))

    def test_nul_tafels(self):
        evenement = _evenement(
            standhouder_borg_per_tafel=Money(Decimal("10.00"), "EUR"),
        )
        inschrijving = StandhouderInschrijving(
            evenement=evenement, aantal_tafels_manueel=0
        )
        with _patch_antwoorden(inschrijving, []):
            self.assertEqual(inschrijving.borg_bedrag_tafels, Decimal("0"))
            self.assertEqual(inschrijving.bereken_totaal(), Decimal("0"))

    def test_flat_borg_met_btw(self):
        evenement = _evenement(
            standhouder_prijs_per_tafel=Money(Decimal("100.00"), "EUR"),
            standhouder_borg_per_tafel=Money(Decimal("50.00"), "EUR"),
            standhouder_prijs_excl_btw=True,
            standhouder_prijs_btw_percentage=Decimal("21.00"),
        )
        inschrijving = StandhouderInschrijving(
            evenement=evenement, aantal_tafels_manueel=1
        )
        with _patch_antwoorden(inschrijving, []):
            # totaal: 100 + 21 = 121
            self.assertEqual(inschrijving.bereken_totaal(), Decimal("121.00"))
            # borg: 50 + 21% = 60.50
            self.assertEqual(inschrijving.borg_bedrag_tafels, Decimal("60.50"))

    def test_flat_borg_regels_label(self):
        evenement = _evenement(
            standhouder_borg_per_tafel=Money(Decimal("10.00"), "EUR"),
        )
        inschrijving = StandhouderInschrijving(
            evenement=evenement, aantal_tafels_manueel=2
        )
        with _patch_antwoorden(inschrijving, []):
            with patch.object(
                type(evenement),
                "standhouder_vragen",
                new_callable=PropertyMock,
                return_value=_mock_vragen_qs([]),
            ):
                regels = inschrijving.borg_regels()
                self.assertEqual(len(regels), 1)
                self.assertEqual(regels[0]["omschrijving"], "2 tafel(s)")
                self.assertEqual(regels[0]["bedrag"], Decimal("20.00"))
                self.assertEqual(regels[0]["bron"], "tafel")


class ZaalplanTafelBorgTests(SimpleTestCase):
    def _inschrijving_met_cellen(self, cellen, antwoorden=None):
        evenement = _evenement(standhouder_zaalplan_actief=True)
        inschrijving = StandhouderInschrijving(evenement=evenement)
        qs = MagicMock()
        qs.select_related.return_value = cellen
        # iterate gekozen_tafels and gekozen_tafels.select_related
        type(inschrijving).gekozen_tafels = PropertyMock(return_value=qs)
        # Also allow iterating qs itself for aantal etc.
        qs.__iter__ = lambda self: iter(cellen)
        qs.count.return_value = len(cellen)
        return inschrijving

    def test_alle_cellen_zonder_borg(self):
        zaalplan = Zaalplan(
            standaard_prijs=Money(Decimal("40.00"), "EUR"),
            prijs_excl_btw=False,
            btw_percentage=Decimal("21.00"),
        )
        cel = ZaalplanCel(
            zaalplan=zaalplan, rij=0, kolom=0, cel_type=CelType.TAFEL, label="A1"
        )
        inschrijving = self._inschrijving_met_cellen([cel])
        with _patch_antwoorden(inschrijving, []):
            self.assertEqual(inschrijving.borg_bedrag_tafels, Decimal("0"))
            self.assertEqual(inschrijving.bereken_totaal(), Decimal("40.00"))

    def test_mix_een_met_een_zonder(self):
        zaalplan = Zaalplan(
            standaard_prijs=Money(Decimal("40.00"), "EUR"),
            prijs_excl_btw=False,
            btw_percentage=Decimal("21.00"),
        )
        cel_a = ZaalplanCel(
            zaalplan=zaalplan,
            rij=0,
            kolom=0,
            cel_type=CelType.TAFEL,
            label="A1",
            borg=Money(Decimal("10.00"), "EUR"),
        )
        cel_b = ZaalplanCel(
            zaalplan=zaalplan, rij=0, kolom=1, cel_type=CelType.TAFEL, label="A2"
        )
        inschrijving = self._inschrijving_met_cellen([cel_a, cel_b])
        with _patch_antwoorden(inschrijving, []):
            self.assertEqual(inschrijving.borg_bedrag_tafels, Decimal("10.00"))
            self.assertEqual(inschrijving.bereken_totaal(), Decimal("80.00"))
            with patch.object(
                type(inschrijving.evenement),
                "standhouder_vragen",
                new_callable=PropertyMock,
                return_value=_mock_vragen_qs([]),
            ):
                regels = inschrijving.borg_regels()
                self.assertEqual(len(regels), 1)
                self.assertEqual(regels[0]["omschrijving"], "Tafel A1")

    def test_telt_als_niet_vermenigvuldigt_borg(self):
        """Borg geldt per object, niet × telt_als_tafels."""
        zaalplan = Zaalplan(
            standaard_prijs=Money(Decimal("60.00"), "EUR"),
            prijs_excl_btw=False,
            btw_percentage=Decimal("21.00"),
        )
        cel = ZaalplanCel(
            zaalplan=zaalplan,
            rij=0,
            kolom=0,
            cel_type=CelType.TAFEL,
            label="Big",
            telt_als_tafels=3,
            borg=Money(Decimal("20.00"), "EUR"),
        )
        inschrijving = self._inschrijving_met_cellen([cel])
        with _patch_antwoorden(inschrijving, []):
            self.assertEqual(cel.tafelgewicht, 3)
            self.assertEqual(inschrijving.borg_bedrag_tafels, Decimal("20.00"))
            self.assertEqual(inschrijving.bereken_totaal(), Decimal("60.00"))

    def test_zaalplan_borg_met_btw(self):
        zaalplan = Zaalplan(
            standaard_prijs=Money(Decimal("100.00"), "EUR"),
            prijs_excl_btw=True,
            btw_percentage=Decimal("21.00"),
        )
        cel = ZaalplanCel(
            zaalplan=zaalplan,
            rij=0,
            kolom=0,
            cel_type=CelType.TAFEL,
            label="A1",
            borg=Money(Decimal("50.00"), "EUR"),
        )
        inschrijving = self._inschrijving_met_cellen([cel])
        with _patch_antwoorden(inschrijving, []):
            self.assertEqual(inschrijving.bereken_totaal(), Decimal("121.00"))
            self.assertEqual(inschrijving.borg_bedrag_tafels, Decimal("60.50"))


class VragenBorgEnCombinatieTests(SimpleTestCase):
    def test_alleen_vraag_borg_label_nummer(self):
        evenement = _evenement(standhouder_prijs_per_tafel=Money(Decimal("0"), "EUR"))
        inschrijving = StandhouderInschrijving(
            evenement=evenement, aantal_tafels_manueel=1
        )
        # Drie vragen; borg is de 4e in de lijst (volgorde index 3 -> Vraag 4)
        v1 = _boolean_borg_vraag(pk=1, volgorde=0, is_borg=False, toeslag="0")
        v1.prijs_toeslag = None
        v2 = _boolean_borg_vraag(pk=2, volgorde=1, is_borg=False)
        v2.prijs_toeslag = None
        v3 = _boolean_borg_vraag(pk=3, volgorde=2, is_borg=False)
        v3.prijs_toeslag = None
        v4 = _boolean_borg_vraag(pk=4, volgorde=3, toeslag="15.00")
        antwoord = StandhouderVraagAntwoord(vraag=v4, antwoord="true")

        with _patch_antwoorden(inschrijving, [antwoord]):
            self.assertEqual(inschrijving.borg_bedrag_vragen, Decimal("15.00"))
            self.assertEqual(inschrijving.borg_bedrag_tafels, Decimal("0"))
            with patch.object(
                type(evenement),
                "standhouder_vragen",
                new_callable=PropertyMock,
                return_value=_mock_vragen_qs([1, 2, 3, 4]),
            ):
                regels = inschrijving.borg_regels()
                self.assertEqual(len(regels), 1)
                self.assertEqual(regels[0]["omschrijving"], "Vraag 4")
                self.assertEqual(regels[0]["bedrag"], Decimal("15.00"))
                self.assertEqual(regels[0]["bron"], "vraag")

    def test_niet_borg_vraag_telt_niet_mee(self):
        evenement = _evenement(standhouder_prijs_per_tafel=Money(Decimal("0"), "EUR"))
        inschrijving = StandhouderInschrijving(
            evenement=evenement, aantal_tafels_manueel=1
        )
        vraag = _boolean_borg_vraag(pk=1, is_borg=False, toeslag="25.00")
        antwoord = StandhouderVraagAntwoord(vraag=vraag, antwoord="true")
        with _patch_antwoorden(inschrijving, [antwoord]):
            self.assertEqual(inschrijving.borg_bedrag_vragen, Decimal("0"))
            self.assertEqual(inschrijving.bereken_totaal(), Decimal("25.00"))

    def test_borg_vraag_nee(self):
        evenement = _evenement(standhouder_prijs_per_tafel=Money(Decimal("0"), "EUR"))
        inschrijving = StandhouderInschrijving(
            evenement=evenement, aantal_tafels_manueel=1
        )
        vraag = _boolean_borg_vraag(pk=1, toeslag="15.00")
        antwoord = StandhouderVraagAntwoord(vraag=vraag, antwoord="false")
        with _patch_antwoorden(inschrijving, [antwoord]):
            self.assertFalse(antwoord.heeft_toeslag())
            self.assertEqual(inschrijving.borg_bedrag_vragen, Decimal("0"))

    def test_combinatie_tafel_en_vraag(self):
        evenement = _evenement(
            standhouder_prijs_per_tafel=Money(Decimal("15.00"), "EUR"),
            standhouder_borg_per_tafel=Money(Decimal("10.00"), "EUR"),
        )
        inschrijving = StandhouderInschrijving(
            evenement=evenement, aantal_tafels_manueel=2
        )
        vraag = _boolean_borg_vraag(pk=7, volgorde=0, toeslag="15.00")
        antwoord = StandhouderVraagAntwoord(vraag=vraag, antwoord="true")
        with _patch_antwoorden(inschrijving, [antwoord]):
            self.assertEqual(inschrijving.borg_bedrag_tafels, Decimal("20.00"))
            self.assertEqual(inschrijving.borg_bedrag_vragen, Decimal("15.00"))
            self.assertEqual(inschrijving.borg_bedrag, Decimal("35.00"))
            # Borg-vraag telt niet mee in totaalprijs (enkel in borg_melding)
            self.assertEqual(inschrijving.bereken_totaal(), Decimal("30.00"))
            with patch.object(
                type(evenement),
                "standhouder_vragen",
                new_callable=PropertyMock,
                return_value=_mock_vragen_qs([7]),
            ):
                regels = inschrijving.borg_regels()
                self.assertEqual(len(regels), 2)
                self.assertEqual(regels[0]["bron"], "tafel")
                self.assertEqual(regels[1]["omschrijving"], "Vraag 1")

    def test_multiselect_borg(self):
        evenement = _evenement(standhouder_prijs_per_tafel=Money(Decimal("0"), "EUR"))
        inschrijving = StandhouderInschrijving(
            evenement=evenement, aantal_tafels_manueel=1
        )
        vraag = StandhouderVraag(
            pk=301,
            tekst="Extra",
            vraag_type=VraagType.MULTISELECT,
            is_borg=True,
            volgorde=0,
            opties=json.dumps([
                {"label": "Stroom", "prijs": "15.00"},
                {"label": "Parkeren", "prijs": "10.00"},
            ]),
            prijs_toeslag_excl_btw=False,
            prijs_toeslag_btw_percentage=Decimal("21.00"),
        )
        antwoord = StandhouderVraagAntwoord(
            vraag=vraag, antwoord=json.dumps(["Stroom", "Parkeren"])
        )
        with _patch_antwoorden(inschrijving, [antwoord]):
            self.assertEqual(inschrijving.borg_bedrag_vragen, Decimal("25.00"))
            # Borg-vraag niet in totaal/prijsopbouw
            self.assertEqual(inschrijving.bereken_totaal(), Decimal("0"))
            from pokemon.standhouder_wizard import build_prijsopbouw

            regels, opbouw = build_prijsopbouw(inschrijving)
            self.assertEqual(opbouw, Decimal("0"))
            self.assertEqual(regels, [])


class BorgMeldingTemplateTests(SimpleTestCase):
    def test_melding_met_breakdown(self):
        evenement = _evenement(
            standhouder_borg_per_tafel=Money(Decimal("10.00"), "EUR"),
        )
        inschrijving = StandhouderInschrijving(
            evenement=evenement, aantal_tafels_manueel=2
        )
        vraag = _boolean_borg_vraag(pk=1, toeslag="5.00")
        antwoord = StandhouderVraagAntwoord(vraag=vraag, antwoord="true")
        with _patch_antwoorden(inschrijving, [antwoord]):
            with patch.object(
                type(evenement),
                "standhouder_vragen",
                new_callable=PropertyMock,
                return_value=_mock_vragen_qs([1]),
            ):
                html = render_to_string(
                    "pokemon/pages/standhouder/_borg_melding.html",
                    {"inschrijving": inschrijving},
                )
                compact = html.replace(" ", "").replace("\n", "")
                self.assertTrue("€25,00" in compact or "€25.00" in compact)
                self.assertIn("2 tafel(s)", html)
                self.assertIn("Vraag 1", html)
                self.assertIn("niet terugbetaald", html.lower())

    def test_geen_melding_zonder_borg(self):
        evenement = _evenement()
        inschrijving = StandhouderInschrijving(
            evenement=evenement, aantal_tafels_manueel=1
        )
        with _patch_antwoorden(inschrijving, []):
            html = render_to_string(
                "pokemon/pages/standhouder/_borg_melding.html",
                {"inschrijving": inschrijving},
            )
            self.assertEqual(html.strip(), "")
