"""Seed demo-evenementen met multiselect-vragen en verifieer prijsflow."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from decimal import Decimal

import pytz
from django.core.management.base import BaseCommand
from django.test import Client
from djmoney.money import Money

from pokemon.models import (
    CelType,
    Evenement,
    StandhouderInschrijving,
    StandhouderInschrijvingStatus,
    StandhouderVraag,
    VraagType,
    Zaalplan,
    ZaalplanCel,
)
from pokemon.standhouder_wizard import build_prijsopbouw, save_vraag_antwoorden
from pokemon.forms import build_standhouder_vragen_form

BRUSSELS = pytz.timezone("Europe/Brussels")
IMAGE = "darts/test.png"


def _ensure_event(slug, **kwargs):
    defaults = {
        "titel": slug,
        "intro_op_index": "Multiselect demo",
        "titel_sectie_a": "Info",
        "tekst_sectie_a": "<p>Demo</p>",
        "start_datum": BRUSSELS.localize(datetime.now() + timedelta(days=30)),
        "einde_datum": BRUSSELS.localize(datetime.now() + timedelta(days=30, hours=8)),
        "max_deelnemers": 200,
        "locatie_kort": "Gent",
        "locatie_lang": "Gent Expo",
        "afbeelding": IMAGE,
        "standhouder_inbegrepen": "Tafel\nStoel",
        "standhouder_prijzen": "Zie wizard",
        "enable_standhouder": True,
        "toon_op_site": True,
        "standhouder_betaling_verplicht": False,
        "standhouder_max_tafels": 3,
    }
    defaults.update(kwargs)
    evenement, created = Evenement.objects.update_or_create(slug=slug, defaults=defaults)
    return evenement, created


def _replace_vragen(evenement, vragen_spec):
    StandhouderVraag.objects.filter(evenement=evenement).delete()
    created = []
    for i, spec in enumerate(vragen_spec):
        created.append(
            StandhouderVraag.objects.create(evenement=evenement, volgorde=i, **spec)
        )
    return created


class Command(BaseCommand):
    help = "Seed multiselect standhouder-demo's en verifieer prijzen end-to-end"

    def handle(self, *args, **options):
        self.stdout.write("=== Seed + E2E multiselect standhouder ===")

        event_a, _ = _ensure_event(
            "ms-demo-zonder-zaalplan",
            titel="MS Demo zonder zaalplan",
            standhouder_zaalplan_actief=False,
            standhouder_prijs_per_tafel=Money(Decimal("40.00"), "EUR"),
            standhouder_borg_per_tafel=Money(Decimal("10.00"), "EUR"),
            standhouder_prijs_excl_btw=False,
        )
        vragen_a = _replace_vragen(
            event_a,
            [
                {
                    "tekst": "Opmerkingen stand",
                    "vraag_type": VraagType.TEKST,
                    "verplicht": False,
                },
                {
                    "tekst": "Extra stoelen?",
                    "vraag_type": VraagType.BOOLEAN,
                    "verplicht": True,
                    "prijs_toeslag": Money(Decimal("10.00"), "EUR"),
                },
                {
                    "tekst": "Ligging",
                    "vraag_type": VraagType.SELECT,
                    "opties": "Voor\nAchter",
                    "verplicht": True,
                    "prijs_toeslag": Money(Decimal("5.00"), "EUR"),
                },
                {
                    "tekst": "Extra's",
                    "vraag_type": VraagType.MULTISELECT,
                    "opties": json.dumps(
                        [
                            {"label": "Gratis folder", "prijs": None},
                            {"label": "Stroom", "prijs": "15.00"},
                            {"label": "WiFi", "prijs": "25.00"},
                            {"label": "Parkeren", "prijs": "10.00"},
                        ]
                    ),
                    "verplicht": True,
                    "min_selecties": 1,
                    "max_selecties": 3,
                    "prijs_toeslag_excl_btw": False,
                },
                {
                    "tekst": "Akkoord huisregels",
                    "vraag_type": VraagType.CHECKBOX,
                    "verplicht": True,
                },
                {
                    "tekst": "Niet-terugbetaalbare reservatiekost",
                    "vraag_type": VraagType.BOOLEAN,
                    "verplicht": False,
                    "prijs_toeslag": Money(Decimal("15.00"), "EUR"),
                    "is_borg": True,
                },
            ],
        )

        event_b, _ = _ensure_event(
            "ms-demo-met-zaalplan",
            titel="MS Demo met zaalplan",
            standhouder_zaalplan_actief=True,
            standhouder_prijs_per_tafel=Money(Decimal("0.00"), "EUR"),
        )
        zaalplan, _ = Zaalplan.objects.update_or_create(
            evenement=event_b,
            defaults={
                "rijen": 2,
                "kolommen": 3,
                "standaard_prijs": Money(Decimal("60.00"), "EUR"),
                "prijs_excl_btw": False,
            },
        )
        ZaalplanCel.objects.filter(zaalplan=zaalplan).delete()
        tafel_cels = []
        for rij in range(2):
            for kolom in range(3):
                cel = ZaalplanCel.objects.create(
                    zaalplan=zaalplan,
                    rij=rij,
                    kolom=kolom,
                    cel_type=CelType.TAFEL if kolom < 2 else CelType.LEEG,
                    prijs=Money(Decimal("55.00"), "EUR") if (rij, kolom) == (0, 0) else None,
                )
                if cel.cel_type == CelType.TAFEL:
                    tafel_cels.append(cel)

        vragen_b = _replace_vragen(
            event_b,
            [
                {
                    "tekst": "Extra's (excl. BTW)",
                    "vraag_type": VraagType.MULTISELECT,
                    "opties": json.dumps(
                        [
                            {"label": "Stroom", "prijs": "20.00"},
                            {"label": "Koeling", "prijs": "30.00"},
                        ]
                    ),
                    "verplicht": True,
                    "min_selecties": 1,
                    "max_selecties": 2,
                    "prijs_toeslag_excl_btw": True,
                    "prijs_toeslag_btw_percentage": Decimal("21.00"),
                },
                {
                    "tekst": "Borgopties",
                    "vraag_type": VraagType.MULTISELECT,
                    "opties": json.dumps(
                        [
                            {"label": "Reservatiekost", "prijs": "50.00"},
                            {"label": "Geen borg", "prijs": None},
                        ]
                    ),
                    "verplicht": True,
                    "min_selecties": 1,
                    "max_selecties": 1,
                    "is_borg": True,
                },
                {
                    "tekst": "VIP-hoek?",
                    "vraag_type": VraagType.BOOLEAN,
                    "verplicht": True,
                    "prijs_toeslag": Money(Decimal("12.00"), "EUR"),
                },
            ],
        )

        self._verify_event_a(event_a, vragen_a)
        self._verify_event_b(event_b, vragen_b, tafel_cels)
        self._verify_http_wizard(event_a)

        self.stdout.write(self.style.SUCCESS("Alle E2E-controles geslaagd."))
        self.stdout.write(
            f"Event A (zonder zaalplan): /nl/evenement/{event_a.slug}/standhouder-worden/"
        )
        self.stdout.write(
            f"Event B (met zaalplan): /nl/evenement/{event_b.slug}/standhouder-worden/"
        )

    def _verify_event_a(self, evenement, vragen):
        self.stdout.write("--- Event A prijscontrole ---")
        inschrijving = StandhouderInschrijving.objects.create(
            evenement=evenement,
            bedrijfsnaam="Demo BV",
            naam="Tester",
            email="tester@example.com",
            telefoon="+32470000000",
            aantal_tafels_manueel=2,
            status=StandhouderInschrijvingStatus.CONCEPT,
        )
        multi = next(v for v in vragen if v.vraag_type == VraagType.MULTISELECT)
        boolean = next(v for v in vragen if v.vraag_type == VraagType.BOOLEAN)
        select = next(v for v in vragen if v.vraag_type == VraagType.SELECT)
        tekst = next(v for v in vragen if v.vraag_type == VraagType.TEKST)
        checkbox = next(v for v in vragen if v.vraag_type == VraagType.CHECKBOX)

        Form = build_standhouder_vragen_form(vragen, 2, vraag_aantal_tafels=False)
        form = Form(
            {
                f"vraag_{tekst.pk}": "Hallo",
                f"vraag_{boolean.pk}": "true",
                f"vraag_{select.pk}": "Voor",
                f"vraag_{multi.pk}": ["Stroom", "Parkeren"],
                f"vraag_{checkbox.pk}": "on",
            }
        )
        assert form.is_valid(), form.errors
        save_vraag_antwoorden(inschrijving, form.cleaned_data, vragen)

        totaal = inschrijving.bereken_totaal()
        regels, opbouw = build_prijsopbouw(inschrijving)
        # 2*40 + 10 + 5 + 15 + 10 = 120
        expected = Decimal("120.00")
        assert totaal == expected, f"totaal {totaal} != {expected}"
        assert opbouw == expected, f"opbouw {opbouw} != {expected}"
        assert totaal == opbouw
        self.stdout.write(f"  OK totaal={totaal} regels={len(regels)}")
        inschrijving.delete()

    def _verify_event_b(self, evenement, vragen, tafel_cels):
        self.stdout.write("--- Event B prijscontrole (zaalplan + BTW + borg) ---")
        from pokemon.standhouder_wizard import save_tafel_keuzes

        inschrijving = StandhouderInschrijving.objects.create(
            evenement=evenement,
            bedrijfsnaam="Zaal BV",
            naam="Tester",
            email="zaal@example.com",
            telefoon="+32470000001",
            status=StandhouderInschrijvingStatus.CONCEPT,
        )
        # Kies tafel met override €55 + standaard €60
        save_tafel_keuzes(inschrijving, [tafel_cels[0].pk, tafel_cels[1].pk])

        multi = next(v for v in vragen if v.tekst.startswith("Extra"))
        borg = next(v for v in vragen if v.is_borg)
        boolean = next(v for v in vragen if v.vraag_type == VraagType.BOOLEAN)

        Form = build_standhouder_vragen_form(vragen, inschrijving.aantal_tafels)
        form = Form(
            {
                f"vraag_{multi.pk}": ["Stroom", "Koeling"],
                f"vraag_{borg.pk}": ["Reservatiekost"],
                f"vraag_{boolean.pk}": "true",
            }
        )
        assert form.is_valid(), form.errors
        save_vraag_antwoorden(inschrijving, form.cleaned_data, vragen)

        totaal = inschrijving.bereken_totaal()
        regels, opbouw = build_prijsopbouw(inschrijving)
        # tafels: 55 + 60 = 115
        # multi excl: 20+30=50 + btw 10.50 = 60.50
        # borg: 50
        # boolean: 12
        # totaal = 115 + 60.50 + 50 + 12 = 237.50
        expected = Decimal("237.50")
        assert totaal == expected, f"totaal {totaal} != {expected}"
        assert opbouw == expected, f"opbouw {opbouw} != {expected}"
        assert inschrijving.borg_bedrag == Decimal("50.00")
        self.stdout.write(
            f"  OK totaal={totaal} borg={inschrijving.borg_bedrag} regels={len(regels)}"
        )
        for r in regels:
            self.stdout.write(f"    - {r['omschrijving']}: €{r['bedrag']}")
        inschrijving.delete()

    def _verify_http_wizard(self, evenement):
        self.stdout.write("--- HTTP wizard flow Event A ---")
        client = Client(HTTP_HOST="localhost")
        # Start
        r = client.get(f"/nl/evenement/{evenement.slug}/standhouder-worden/")
        assert r.status_code in (200, 302), r.status_code
        # Gegevens redirect expected when no zaalplan
        r = client.get(f"/nl/evenement/{evenement.slug}/standhouder-worden/gegevens/")
        assert r.status_code == 200, r.status_code
        r = client.post(
            f"/nl/evenement/{evenement.slug}/standhouder-worden/gegevens/",
            {
                "bedrijfsnaam": "HTTP Demo",
                "naam": "HTTP Tester",
                "email": "http@example.com",
                "telefoon": "+32471112233",
                "opmerkingen": "",
            },
        )
        assert r.status_code == 302, (r.status_code, r.content[:200])

        # Eerste vragen-POST: aantal tafels (geen vragen tot aantal bekend)
        r = client.post(
            f"/nl/evenement/{evenement.slug}/standhouder-worden/vragen/",
            {"aantal_tafels": "2"},
        )
        assert r.status_code == 302, r.status_code

        vragen = list(
            StandhouderVraag.objects.filter(evenement=evenement).order_by("volgorde")
        )
        multi = next(v for v in vragen if v.vraag_type == VraagType.MULTISELECT)
        boolean = next(v for v in vragen if v.vraag_type == VraagType.BOOLEAN)
        select = next(v for v in vragen if v.vraag_type == VraagType.SELECT)
        tekst = next(v for v in vragen if v.vraag_type == VraagType.TEKST)
        checkbox = next(v for v in vragen if v.vraag_type == VraagType.CHECKBOX)

        r = client.post(
            f"/nl/evenement/{evenement.slug}/standhouder-worden/vragen/",
            {
                "aantal_tafels": "2",
                f"vraag_{tekst.pk}": "Via HTTP",
                f"vraag_{boolean.pk}": "true",
                f"vraag_{select.pk}": "Achter",
                f"vraag_{multi.pk}": ["WiFi", "Gratis folder"],
                f"vraag_{checkbox.pk}": "on",
            },
        )
        assert r.status_code == 302, (r.status_code, r.content[:500] if r.status_code != 302 else "")

        r = client.get(f"/nl/evenement/{evenement.slug}/standhouder-worden/overzicht/")
        assert r.status_code == 200, r.status_code
        # 2*40 + 10 + 5 + 25 = 120
        content = r.content.decode("utf-8")
        assert (
            "120,00" in content
            or "120.00" in content
            or ">€120<" in content
            or "€120" in content
        ), content[content.find("prijsopbouw") : content.find("prijsopbouw") + 900]
        self.stdout.write("  OK HTTP overzicht toont €120")
