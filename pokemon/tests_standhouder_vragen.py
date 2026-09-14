import json
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from django.utils import timezone
from djmoney.money import Money

from pokemon.forms import (
    build_standhouder_vragen_form,
    deserialize_vraag_antwoord_initial,
    serialize_vraag_antwoord,
)
from pokemon.models import (
    Evenement,
    StandhouderInschrijving,
    StandhouderVraag,
    StandhouderVraagAntwoord,
    VraagType,
    bedrag_met_btw,
)
from pokemon.standhouder_wizard import build_prijsopbouw


def _vraag(**kwargs):
    defaults = {
        "tekst": "Testvraag",
        "vraag_type": VraagType.MULTISELECT,
        "opties": json.dumps([
            {"label": "Gratis", "prijs": None},
            {"label": "Stroom", "prijs": "15.00"},
            {"label": "WiFi", "prijs": "25.00"},
            {"label": "Parkeren", "prijs": "10.00"},
        ]),
        "verplicht": False,
        "min_selecties": 1,
        "max_selecties": 3,
        "prijs_toeslag_excl_btw": False,
        "prijs_toeslag_btw_percentage": Decimal("21.00"),
    }
    defaults.update(kwargs)
    vraag = StandhouderVraag(**defaults)
    vraag.pk = kwargs.get("pk", 1)
    return vraag


def _evenement(**kwargs):
    now = timezone.now()
    defaults = {
        "titel": "Test Event",
        "intro_op_index": "intro",
        "slug": "test-multiselect",
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
        "standhouder_prijs_per_tafel": Money(Decimal("50.00"), "EUR"),
        "standhouder_prijs_excl_btw": False,
        "standhouder_prijs_btw_percentage": Decimal("21.00"),
    }
    defaults.update(kwargs)
    return Evenement(**defaults)


class MultiselectOptieParsingTests(SimpleTestCase):
    def test_multiselect_opties_parsed(self):
        vraag = _vraag()
        opties = vraag.multiselect_opties()
        self.assertEqual(len(opties), 4)
        self.assertIsNone(opties[0]["prijs"])
        self.assertEqual(opties[1]["prijs"], Decimal("15.00"))
        self.assertEqual(vraag.opties_voor_form(), ["Gratis", "Stroom", "WiFi", "Parkeren"])

    def test_select_blijft_platte_tekst(self):
        vraag = StandhouderVraag(
            tekst="Kleur",
            vraag_type=VraagType.SELECT,
            opties="Rood\nBlauw\n",
        )
        self.assertEqual(vraag.opties_lijst, ["Rood", "Blauw"])
        self.assertEqual(vraag.multiselect_opties(), [])

    def test_optie_prijs_map_negeert_gratis(self):
        vraag = _vraag()
        self.assertEqual(
            vraag.optie_prijs_map(),
            {
                "Stroom": Decimal("15.00"),
                "WiFi": Decimal("25.00"),
                "Parkeren": Decimal("10.00"),
            },
        )


class MultiselectFormValidatieTests(SimpleTestCase):
    def test_min_selecties_verplicht(self):
        vraag = _vraag(pk=10, verplicht=True, min_selecties=None, max_selecties=3)
        Form = build_standhouder_vragen_form([vraag], aantal_tafels=1)
        form = Form({})
        self.assertFalse(form.is_valid())
        self.assertIn(f"vraag_{vraag.pk}", form.errors)

    def test_max_selecties_overschreden(self):
        vraag = _vraag(pk=11, min_selecties=1, max_selecties=2)
        Form = build_standhouder_vragen_form([vraag], aantal_tafels=1)
        form = Form({
            f"vraag_{vraag.pk}": ["Gratis", "Stroom", "WiFi"],
        })
        self.assertFalse(form.is_valid())

    def test_geldige_selectie(self):
        vraag = _vraag(pk=12, min_selecties=1, max_selecties=3)
        Form = build_standhouder_vragen_form([vraag], aantal_tafels=1)
        form = Form({
            f"vraag_{vraag.pk}": ["Stroom", "WiFi"],
        })
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data[f"vraag_{vraag.pk}"], ["Stroom", "WiFi"])

    def test_ongeldige_optie_geweigerd(self):
        vraag = _vraag(pk=13, min_selecties=1, max_selecties=3)
        Form = build_standhouder_vragen_form([vraag], aantal_tafels=1)
        form = Form({
            f"vraag_{vraag.pk}": ["NietBestaand"],
        })
        self.assertFalse(form.is_valid())


class MultiselectSerialisatieTests(SimpleTestCase):
    def test_serialize_en_deserialize_roundtrip(self):
        vraag = _vraag()
        raw = serialize_vraag_antwoord(vraag, ["Stroom", "WiFi"])
        self.assertEqual(json.loads(raw), ["Stroom", "WiFi"])
        initial = deserialize_vraag_antwoord_initial(vraag, raw)
        self.assertEqual(initial, ["Stroom", "WiFi"])

    def test_serialize_lege_lijst(self):
        vraag = _vraag()
        self.assertEqual(serialize_vraag_antwoord(vraag, []), "[]")
        self.assertEqual(deserialize_vraag_antwoord_initial(vraag, "[]"), [])


class MultiselectPrijsTests(SimpleTestCase):
    def test_toeslag_som_van_opties(self):
        vraag = _vraag()
        antwoord = StandhouderVraagAntwoord(
            vraag=vraag,
            antwoord=json.dumps(["Gratis", "Stroom", "WiFi"]),
        )
        self.assertEqual(antwoord.toeslag_bedrag(), Decimal("40.00"))
        self.assertTrue(antwoord.heeft_toeslag())
        self.assertEqual(antwoord.weergave(), "Gratis, Stroom, WiFi")

    def test_alleen_gratis_geen_toeslag(self):
        vraag = _vraag()
        antwoord = StandhouderVraagAntwoord(
            vraag=vraag,
            antwoord=json.dumps(["Gratis"]),
        )
        self.assertEqual(antwoord.toeslag_bedrag(), Decimal("0"))
        self.assertFalse(antwoord.heeft_toeslag())

    def test_toeslag_met_btw(self):
        vraag = _vraag(prijs_toeslag_excl_btw=True, prijs_toeslag_btw_percentage=Decimal("21.00"))
        antwoord = StandhouderVraagAntwoord(
            vraag=vraag,
            antwoord=json.dumps(["Stroom"]),
        )
        excl = antwoord.toeslag_bedrag()
        incl, btw = bedrag_met_btw(excl, True, Decimal("21.00"))
        self.assertEqual(excl, Decimal("15.00"))
        self.assertEqual(btw, Decimal("3.15"))
        self.assertEqual(incl, Decimal("18.15"))


class MultiselectComboPrijsTests(SimpleTestCase):
    def test_combo_boolean_select_multiselect_prijsopbouw(self):
        evenement = _evenement(standhouder_prijs_per_tafel=Money(Decimal("50.00"), "EUR"))
        inschrijving = StandhouderInschrijving(
            evenement=evenement,
            aantal_tafels_manueel=2,
        )

        boolean_vraag = StandhouderVraag(
            tekst="Extra stoelen",
            vraag_type=VraagType.BOOLEAN,
            prijs_toeslag=Money(Decimal("10.00"), "EUR"),
            prijs_toeslag_excl_btw=False,
            prijs_toeslag_btw_percentage=Decimal("21.00"),
        )
        boolean_vraag.pk = 101

        select_vraag = StandhouderVraag(
            tekst="Ligging",
            vraag_type=VraagType.SELECT,
            opties="Voor\nAchter",
            prijs_toeslag=Money(Decimal("5.00"), "EUR"),
            prijs_toeslag_excl_btw=False,
            prijs_toeslag_btw_percentage=Decimal("21.00"),
        )
        select_vraag.pk = 102

        multi_vraag = _vraag(pk=103, prijs_toeslag_excl_btw=False)

        antwoorden = [
            StandhouderVraagAntwoord(vraag=boolean_vraag, antwoord="true"),
            StandhouderVraagAntwoord(vraag=select_vraag, antwoord="Voor"),
            StandhouderVraagAntwoord(
                vraag=multi_vraag,
                antwoord=json.dumps(["Stroom", "Parkeren"]),
            ),
        ]

        related = MagicMock()
        related.select_related.return_value = antwoorden

        with patch.object(StandhouderInschrijving, "antwoorden", related):
            totaal = inschrijving.bereken_totaal()
            # 2 * 50 + 10 + 5 + 15 + 10 = 140
            self.assertEqual(totaal, Decimal("140.00"))

            regels, opbouw_totaal = build_prijsopbouw(inschrijving)
            self.assertEqual(opbouw_totaal, Decimal("140.00"))
            self.assertEqual(totaal, opbouw_totaal)

            multi_regels = [
                r for r in regels
                if "Stroom" in r["omschrijving"] or "Parkeren" in r["omschrijving"]
            ]
            self.assertEqual(len(multi_regels), 2)

    def test_multiselect_excl_btw_in_prijsopbouw(self):
        evenement = _evenement(standhouder_prijs_per_tafel=Money(Decimal("0.00"), "EUR"))
        inschrijving = StandhouderInschrijving(
            evenement=evenement,
            aantal_tafels_manueel=1,
        )

        multi_vraag = _vraag(
            pk=201,
            prijs_toeslag_excl_btw=True,
            prijs_toeslag_btw_percentage=Decimal("21.00"),
        )
        antwoord = StandhouderVraagAntwoord(
            vraag=multi_vraag,
            antwoord=json.dumps(["WiFi"]),
        )
        related = MagicMock()
        related.select_related.return_value = [antwoord]

        with patch.object(StandhouderInschrijving, "antwoorden", related):
            totaal = inschrijving.bereken_totaal()
            # 25 + 21% = 30.25
            self.assertEqual(totaal, Decimal("30.25"))

            regels, opbouw_totaal = build_prijsopbouw(inschrijving)
            # prijsopbouw toont excl + btw apart: 25 + 5.25 = 30.25
            self.assertEqual(opbouw_totaal, Decimal("30.25"))
            self.assertEqual(totaal, opbouw_totaal)
            self.assertTrue(any(r["is_btw"] for r in regels))

    def test_borg_multiselect(self):
        evenement = _evenement(standhouder_prijs_per_tafel=Money(Decimal("0.00"), "EUR"))
        inschrijving = StandhouderInschrijving(
            evenement=evenement,
            aantal_tafels_manueel=1,
        )
        multi_vraag = _vraag(pk=301, is_borg=True)
        antwoord = StandhouderVraagAntwoord(
            vraag=multi_vraag,
            antwoord=json.dumps(["Stroom", "Parkeren"]),
        )
        related = MagicMock()
        related.select_related.return_value = [antwoord]

        with patch.object(StandhouderInschrijving, "antwoorden", related):
            self.assertEqual(inschrijving.borg_bedrag, Decimal("25.00"))
            self.assertTrue(inschrijving.heeft_borg)
