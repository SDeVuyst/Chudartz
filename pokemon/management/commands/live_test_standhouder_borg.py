"""
Live Docker smoke-test voor standhouder tafelborg + vragenborg.
Maakt twee demo-events aan en assert alle kernscenario's.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from decimal import Decimal

import pytz
from django.core.management.base import BaseCommand
from django.template.loader import render_to_string
from djmoney.money import Money

from pokemon.models import (
    CelType,
    Evenement,
    StandhouderInschrijving,
    StandhouderInschrijvingStatus,
    StandhouderTafelKeuze,
    StandhouderVraag,
    StandhouderVraagAntwoord,
    VraagType,
    Zaalplan,
    ZaalplanCel,
)
from pokemon.standhouder_wizard import build_prijsopbouw

BRUSSELS = pytz.timezone("Europe/Brussels")
IMAGE = "darts/test.png"
SLUG_FLAT = "live-borg-zonder-zaalplan"
SLUG_ZAAL = "live-borg-met-zaalplan"


class Command(BaseCommand):
    help = "Live borg smoke-test: nieuw event + alle borg-scenario's"

    def handle(self, *args, **options):
        self.results = []
        self.stdout.write(self.style.NOTICE("=== LIVE BORG TEST (Docker) ==="))

        flat = self._setup_flat_event()
        zaal = self._setup_zaalplan_event()

        self._case_flat_geen_borg(flat)
        self._case_flat_deel_borg(flat)
        self._case_flat_clamp(flat)
        self._case_flat_btw(flat)
        self._case_zaal_mix(zaal)
        self._case_zaal_telt_als(zaal)
        self._case_combinatie(flat)
        self._case_vraag_nummer_label(flat)
        self._case_template_melding(flat)
        self._case_totaal_geen_dubbel(flat)

        failed = [r for r in self.results if not r[0]]
        self.stdout.write("")
        for ok, name, detail in self.results:
            mark = "PASS" if ok else "FAIL"
            style = self.style.SUCCESS if ok else self.style.ERROR
            self.stdout.write(style(f"[{mark}] {name}: {detail}"))

        self.stdout.write("")
        if failed:
            self.stdout.write(self.style.ERROR(f"{len(failed)} FAILED / {len(self.results)} total"))
            raise SystemExit(1)
        self.stdout.write(
            self.style.SUCCESS(f"ALL {len(self.results)} LIVE CASES PASSED")
        )
        self.stdout.write(f"Events: {SLUG_FLAT}, {SLUG_ZAAL}")

    def _ok(self, name, cond, detail=""):
        self.results.append((bool(cond), name, detail if detail else ("ok" if cond else "assertion failed")))

    def _ensure_event(self, slug, **kwargs):
        defaults = {
            "titel": slug,
            "intro_op_index": "Live borg test",
            "titel_sectie_a": "Info",
            "tekst_sectie_a": "<p>Live borg</p>",
            "start_datum": BRUSSELS.localize(datetime.now() + timedelta(days=45)),
            "einde_datum": BRUSSELS.localize(datetime.now() + timedelta(days=45, hours=8)),
            "max_deelnemers": 100,
            "locatie_kort": "Gent",
            "locatie_lang": "Gent Expo",
            "afbeelding": IMAGE,
            "standhouder_inbegrepen": "Tafel",
            "standhouder_prijzen": "Live test",
            "enable_standhouder": True,
            "toon_op_site": True,
            "standhouder_betaling_verplicht": False,
            "standhouder_max_tafels": 5,
        }
        defaults.update(kwargs)
        evenement, _ = Evenement.objects.update_or_create(slug=slug, defaults=defaults)
        return evenement

    def _setup_flat_event(self):
        evenement = self._ensure_event(
            SLUG_FLAT,
            titel="Live Borg zonder zaalplan",
            standhouder_zaalplan_actief=False,
            standhouder_prijs_per_tafel=Money(Decimal("15.00"), "EUR"),
            standhouder_borg_per_tafel=Money(Decimal("10.00"), "EUR"),
            standhouder_prijs_excl_btw=False,
            standhouder_prijs_btw_percentage=Decimal("21.00"),
        )
        StandhouderVraag.objects.filter(evenement=evenement).delete()
        StandhouderVraag.objects.create(
            evenement=evenement,
            tekst="Opmerking",
            vraag_type=VraagType.TEKST,
            volgorde=0,
            verplicht=False,
        )
        StandhouderVraag.objects.create(
            evenement=evenement,
            tekst="Extra stoel",
            vraag_type=VraagType.BOOLEAN,
            volgorde=1,
            verplicht=False,
            prijs_toeslag=Money(Decimal("5.00"), "EUR"),
            is_borg=False,
        )
        StandhouderVraag.objects.create(
            evenement=evenement,
            tekst="WiFi",
            vraag_type=VraagType.BOOLEAN,
            volgorde=2,
            verplicht=False,
            prijs_toeslag=Money(Decimal("8.00"), "EUR"),
            is_borg=False,
        )
        StandhouderVraag.objects.create(
            evenement=evenement,
            tekst="Reservatiekost",
            vraag_type=VraagType.BOOLEAN,
            volgorde=3,
            verplicht=False,
            prijs_toeslag=Money(Decimal("15.00"), "EUR"),
            is_borg=True,
        )
        return evenement

    def _setup_zaalplan_event(self):
        evenement = self._ensure_event(
            SLUG_ZAAL,
            titel="Live Borg met zaalplan",
            standhouder_zaalplan_actief=True,
            standhouder_prijs_per_tafel=Money(Decimal("0"), "EUR"),
            standhouder_borg_per_tafel=Money(Decimal("0"), "EUR"),
        )
        StandhouderVraag.objects.filter(evenement=evenement).delete()
        zaalplan, _ = Zaalplan.objects.update_or_create(
            evenement=evenement,
            defaults={
                "rijen": 2,
                "kolommen": 3,
                "standaard_prijs": Money(Decimal("40.00"), "EUR"),
                "prijs_excl_btw": False,
                "btw_percentage": Decimal("21.00"),
            },
        )
        zaalplan.cellen.all().delete()
        zaalplan.genereer_rooster()
        # Place three tables
        cels = list(zaalplan.cellen.order_by("rij", "kolom")[:3])
        for i, cel in enumerate(cels):
            cel.cel_type = CelType.TAFEL
            cel.label = f"T{i+1}"
            if i == 0:
                cel.borg = Money(Decimal("10.00"), "EUR")
            elif i == 1:
                cel.borg = None
            else:
                cel.prijs = Money(Decimal("60.00"), "EUR")
                cel.borg = Money(Decimal("20.00"), "EUR")
                cel.telt_als_tafels = 2
            cel.save()
        return evenement

    def _inschrijving(self, evenement, **kwargs):
        defaults = {
            "bedrijfsnaam": "Live Test BV",
            "naam": "Tester",
            "email": "live-borg@example.com",
            "telefoon": "0470000000",
            "status": StandhouderInschrijvingStatus.CONCEPT,
        }
        defaults.update(kwargs)
        return StandhouderInschrijving.objects.create(evenement=evenement, **defaults)

    def _case_flat_geen_borg(self, evenement):
        evenement.standhouder_borg_per_tafel = Money(Decimal("0"), "EUR")
        evenement.save(update_fields=["standhouder_borg_per_tafel"])
        insc = self._inschrijving(evenement, aantal_tafels_manueel=2)
        self._ok(
            "1 flat geen borg",
            not insc.heeft_borg and insc.borg_bedrag == 0 and insc.borg_regels() == [],
            f"borg={insc.borg_bedrag} regels={insc.borg_regels()}",
        )
        # restore for next cases
        evenement.standhouder_borg_per_tafel = Money(Decimal("10.00"), "EUR")
        evenement.save(update_fields=["standhouder_borg_per_tafel"])

    def _case_flat_deel_borg(self, evenement):
        insc = self._inschrijving(evenement, aantal_tafels_manueel=2)
        totaal = insc.bereken_totaal()
        self._ok(
            "3 flat borg 10 van 15 ×2",
            totaal == Decimal("30.00")
            and insc.borg_bedrag_tafels == Decimal("20.00")
            and insc.borg_bedrag == Decimal("20.00"),
            f"totaal={totaal} borg_tafels={insc.borg_bedrag_tafels}",
        )
        regels = insc.borg_regels()
        self._ok(
            "flat regels label",
            len(regels) == 1 and regels[0]["omschrijving"] == "2 tafel(s)",
            str(regels),
        )

    def _case_flat_clamp(self, evenement):
        evenement.standhouder_borg_per_tafel = Money(Decimal("99.00"), "EUR")
        evenement.save(update_fields=["standhouder_borg_per_tafel"])
        insc = self._inschrijving(evenement, aantal_tafels_manueel=1)
        totaal = insc.bereken_totaal()
        self._ok(
            "4 flat clamp borg>prijs",
            totaal == Decimal("15.00") and insc.borg_bedrag_tafels == Decimal("15.00"),
            f"totaal={totaal} borg={insc.borg_bedrag_tafels}",
        )
        evenement.standhouder_borg_per_tafel = Money(Decimal("10.00"), "EUR")
        evenement.save(update_fields=["standhouder_borg_per_tafel"])

    def _case_flat_btw(self, evenement):
        evenement.standhouder_prijs_per_tafel = Money(Decimal("100.00"), "EUR")
        evenement.standhouder_borg_per_tafel = Money(Decimal("50.00"), "EUR")
        evenement.standhouder_prijs_excl_btw = True
        evenement.save(
            update_fields=[
                "standhouder_prijs_per_tafel",
                "standhouder_borg_per_tafel",
                "standhouder_prijs_excl_btw",
            ]
        )
        insc = self._inschrijving(evenement, aantal_tafels_manueel=1)
        totaal = insc.bereken_totaal()
        self._ok(
            "6 flat BTW borg",
            totaal == Decimal("121.00") and insc.borg_bedrag_tafels == Decimal("60.50"),
            f"totaal={totaal} borg={insc.borg_bedrag_tafels}",
        )
        # restore
        evenement.standhouder_prijs_per_tafel = Money(Decimal("15.00"), "EUR")
        evenement.standhouder_borg_per_tafel = Money(Decimal("10.00"), "EUR")
        evenement.standhouder_prijs_excl_btw = False
        evenement.save(
            update_fields=[
                "standhouder_prijs_per_tafel",
                "standhouder_borg_per_tafel",
                "standhouder_prijs_excl_btw",
            ]
        )

    def _kies_tafels(self, inschrijving, cellen):
        StandhouderTafelKeuze.objects.filter(inschrijving=inschrijving).delete()
        for cel in cellen:
            StandhouderTafelKeuze.objects.create(inschrijving=inschrijving, cel=cel)

    def _case_zaal_mix(self, evenement):
        zaalplan = evenement.zaalplan
        cellen = list(
            zaalplan.cellen.filter(cel_type=CelType.TAFEL).order_by("rij", "kolom")
        )
        insc = self._inschrijving(evenement)
        self._kies_tafels(insc, cellen[:2])  # T1 with borg 10, T2 without
        totaal = insc.bereken_totaal()
        regels = insc.borg_regels()
        self._ok(
            "7+8 zaal mix",
            totaal == Decimal("80.00")
            and insc.borg_bedrag_tafels == Decimal("10.00")
            and len(regels) == 1
            and "T1" in regels[0]["omschrijving"],
            f"totaal={totaal} borg={insc.borg_bedrag_tafels} regels={regels}",
        )

    def _case_zaal_telt_als(self, evenement):
        zaalplan = evenement.zaalplan
        cel = zaalplan.cellen.filter(label="T3").first()
        insc = self._inschrijving(evenement)
        self._kies_tafels(insc, [cel])
        totaal = insc.bereken_totaal()
        self._ok(
            "12 telt_als niet × borg",
            cel.tafelgewicht == 2
            and totaal == Decimal("60.00")
            and insc.borg_bedrag_tafels == Decimal("20.00"),
            f"gewicht={cel.tafelgewicht} totaal={totaal} borg={insc.borg_bedrag_tafels}",
        )

    def _case_combinatie(self, evenement):
        insc = self._inschrijving(evenement, aantal_tafels_manueel=2)
        vraag = evenement.standhouder_vragen.get(is_borg=True)
        StandhouderVraagAntwoord.objects.create(
            inschrijving=insc, vraag=vraag, antwoord="true"
        )
        totaal = insc.bereken_totaal()
        # 2*15 = 30 (vraagborg niet in totaal); borg = 20 + 15 = 35
        regels = insc.borg_regels()
        self._ok(
            "18 combinatie tafel+vraag",
            totaal == Decimal("30.00")
            and insc.borg_bedrag == Decimal("35.00")
            and insc.borg_bedrag_tafels == Decimal("20.00")
            and insc.borg_bedrag_vragen == Decimal("15.00")
            and len(regels) == 2,
            f"totaal={totaal} borg={insc.borg_bedrag} regels={regels}",
        )

    def _case_vraag_nummer_label(self, evenement):
        insc = self._inschrijving(evenement, aantal_tafels_manueel=0)
        evenement.standhouder_borg_per_tafel = Money(Decimal("0"), "EUR")
        evenement.save(update_fields=["standhouder_borg_per_tafel"])
        vraag = evenement.standhouder_vragen.get(is_borg=True)
        StandhouderVraagAntwoord.objects.create(
            inschrijving=insc, vraag=vraag, antwoord="true"
        )
        regels = insc.borg_regels()
        # 4th question (0-based volgorde 3) -> Vraag 4
        self._ok(
            "14 label Vraag 4",
            len(regels) == 1 and regels[0]["omschrijving"] == "Vraag 4",
            str(regels),
        )
        evenement.standhouder_borg_per_tafel = Money(Decimal("10.00"), "EUR")
        evenement.save(update_fields=["standhouder_borg_per_tafel"])

    def _case_template_melding(self, evenement):
        insc = self._inschrijving(evenement, aantal_tafels_manueel=2)
        vraag = evenement.standhouder_vragen.get(is_borg=True)
        StandhouderVraagAntwoord.objects.create(
            inschrijving=insc, vraag=vraag, antwoord="true"
        )
        insc.bereken_totaal()
        html = render_to_string(
            "pokemon/pages/standhouder/_borg_melding.html",
            {"inschrijving": insc},
        )
        email = render_to_string(
            "pokemon/email/_borg_melding.html",
            {"inschrijving": insc},
        )
        self._ok(
            "21+22 template breakdown",
            "Vraag 4" in html
            and "2 tafel(s)" in html
            and "borg-melding" in html
            and "Vraag 4" in email
            and "niet terugbetaald" in email.lower(),
            f"html_len={len(html)} email_len={len(email)}",
        )
        # geen borg
        insc2 = self._inschrijving(evenement, aantal_tafels_manueel=1)
        evenement.standhouder_borg_per_tafel = Money(Decimal("0"), "EUR")
        evenement.save(update_fields=["standhouder_borg_per_tafel"])
        html2 = render_to_string(
            "pokemon/pages/standhouder/_borg_melding.html",
            {"inschrijving": insc2},
        )
        self._ok("25 geen melding", html2.strip() == "", repr(html2[:80]))
        evenement.standhouder_borg_per_tafel = Money(Decimal("10.00"), "EUR")
        evenement.save(update_fields=["standhouder_borg_per_tafel"])

    def _case_totaal_geen_dubbel(self, evenement):
        insc = self._inschrijving(evenement, aantal_tafels_manueel=2)
        totaal = insc.bereken_totaal()
        _, opbouw = build_prijsopbouw(insc)
        self._ok(
            "20 geen dubbele optelling",
            totaal == Decimal("30.00") and opbouw == Decimal("30.00"),
            f"totaal={totaal} opbouw={opbouw} borg={insc.borg_bedrag}",
        )
