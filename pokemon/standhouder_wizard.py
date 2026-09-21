from decimal import Decimal

from django.db import transaction
from django.utils.translation import gettext as _

from pokemon.models import (
    CelType,
    Sponsor,
    StandhouderInschrijving,
    StandhouderInschrijvingStatus,
    StandhouderTafelKeuze,
    StandhouderVraag,
    StandhouderVraagAntwoord,
    VraagType,
    Zaalplan,
    ZaalplanCel,
    bedrag_met_btw,
)


def session_key(evenement):
    return f"standhouder_{evenement.slug}"


def email_sent_session_key(evenement):
    return f"standhouder_email_sent_{evenement.slug}"


def voorlopig_session_key(evenement):
    return f"standhouder_voorlopig_{evenement.slug}"


def pending_inschrijving_session_key(evenement):
    return f"standhouder_pending_{evenement.slug}"


def studio_preview_session_key(evenement):
    return f"standhouder_studio_preview_{evenement.slug}"


def kortingscode_session_key(evenement):
    return f"standhouder_kortingscode_{evenement.slug}"


def get_standhouder_kortingscode(request, evenement):
    return (request.session.get(kortingscode_session_key(evenement)) or "").strip()


def set_standhouder_kortingscode(request, evenement, code):
    key = kortingscode_session_key(evenement)
    if code:
        request.session[key] = code.strip()
    else:
        request.session.pop(key, None)


def clear_standhouder_kortingscode(request, evenement):
    request.session.pop(kortingscode_session_key(evenement), None)


STANDHOUDER_STAP_URLS = {
    "tafels": "standhouder",
    "gegevens": "standhouder_gegevens",
    "vragen": "standhouder_vragen",
    "overzicht": "standhouder_overzicht",
}


def get_concept_inschrijving(request, evenement, *, session_key_fn=session_key):
    pk = request.session.get(session_key_fn(evenement))
    if not pk:
        return None
    return StandhouderInschrijving.objects.filter(
        pk=pk,
        evenement=evenement,
        status=StandhouderInschrijvingStatus.CONCEPT,
    ).first()


def set_concept_inschrijving(request, inschrijving, *, session_key_fn=session_key):
    request.session[session_key_fn(inschrijving.evenement)] = inschrijving.pk


def clear_concept_inschrijving(request, evenement, *, session_key_fn=session_key):
    request.session.pop(session_key_fn(evenement), None)


def get_or_create_concept_inschrijving(request, evenement, *, session_key_fn=session_key):
    inschrijving = get_concept_inschrijving(request, evenement, session_key_fn=session_key_fn)
    if inschrijving:
        return inschrijving
    inschrijving = StandhouderInschrijving.objects.create(
        evenement=evenement,
        status=StandhouderInschrijvingStatus.CONCEPT,
    )
    set_concept_inschrijving(request, inschrijving, session_key_fn=session_key_fn)
    return inschrijving


def get_or_create_studio_preview_inschrijving(request, evenement):
    return get_or_create_concept_inschrijving(
        request, evenement, session_key_fn=studio_preview_session_key
    )


def get_studio_preview_inschrijving(request, evenement):
    return get_concept_inschrijving(
        request, evenement, session_key_fn=studio_preview_session_key
    )


def clear_studio_preview_inschrijving(request, evenement):
    inschrijving = get_studio_preview_inschrijving(request, evenement)
    clear_concept_inschrijving(
        request, evenement, session_key_fn=studio_preview_session_key
    )
    if inschrijving and inschrijving.status == StandhouderInschrijvingStatus.CONCEPT:
        inschrijving.delete()


def serialize_standhouder_vraag(vraag):
    toeslag = None
    if vraag.prijs_toeslag is not None:
        toeslag = str(vraag.prijs_toeslag.amount)

    if vraag.vraag_type == VraagType.MULTISELECT:
        opties_serialized = [
            {
                "label": o["label"],
                "prijs": str(o["prijs"]) if o["prijs"] is not None else None,
            }
            for o in vraag.multiselect_opties()
        ]
        opties_raw = vraag.opties
    else:
        opties_serialized = None
        opties_raw = vraag.opties

    return {
        "id": vraag.pk,
        "tekst": vraag.tekst,
        "vraag_type": vraag.vraag_type,
        "opties": opties_raw,
        "opties_parsed": opties_serialized,
        "verplicht": vraag.verplicht,
        "volgorde": vraag.volgorde,
        "prijs_toeslag": toeslag,
        "prijs_toeslag_excl_btw": vraag.prijs_toeslag_excl_btw,
        "prijs_toeslag_btw_percentage": str(vraag.prijs_toeslag_btw_percentage),
        "is_borg": vraag.is_borg,
        "min_selecties": vraag.min_selecties,
        "max_selecties": vraag.max_selecties,
        "min_tafels": vraag.min_tafels,
        "max_tafels": vraag.max_tafels,
    }


def heeft_gegevens(inschrijving):
    return bool(
        inschrijving.bedrijfsnaam
        and inschrijving.naam
        and inschrijving.email
        and inschrijving.telefoon
    )


def get_zaalplan(evenement):
    try:
        return evenement.zaalplan
    except Zaalplan.DoesNotExist:
        return None


def get_bezette_cel_ids(exclude_inschrijving_id=None):
    qs = StandhouderTafelKeuze.objects.filter(
        inschrijving__status__in=StandhouderInschrijvingStatus.BEZET,
    )
    if exclude_inschrijving_id:
        qs = qs.exclude(inschrijving_id=exclude_inschrijving_id)
    return set(qs.values_list("cel_id", flat=True))


def serialize_zaalplan_grid(zaalplan, inschrijving=None):
    exclude_id = inschrijving.pk if inschrijving else None
    bezet_ids = get_bezette_cel_ids(exclude_inschrijving_id=exclude_id)
    selected_ids = set()
    if inschrijving:
        selected_ids = set(
            inschrijving.tafel_keuzes.values_list("cel_id", flat=True)
        )

    alle_cellen = list(zaalplan.cellen.order_by("rij", "kolom"))

    # Groepen bepalen: groep_id -> lijst leden
    groepen = {}
    for cel in alle_cellen:
        if cel.groep:
            groepen.setdefault(cel.groep, []).append(cel)

    primary_van = {}
    for groep_id, leden in groepen.items():
        primary_van[groep_id] = min(leden, key=lambda c: (c.rij, c.kolom))

    # Snelle lookup op (rij, kolom) -> groep
    groep_op_positie = {(c.rij, c.kolom): c.groep for c in alle_cellen}

    def buren_zelfde_groep(cel):
        if not cel.groep:
            return {"boven": False, "onder": False, "links": False, "rechts": False}
        return {
            "boven": groep_op_positie.get((cel.rij - 1, cel.kolom)) == cel.groep,
            "onder": groep_op_positie.get((cel.rij + 1, cel.kolom)) == cel.groep,
            "links": groep_op_positie.get((cel.rij, cel.kolom - 1)) == cel.groep,
            "rechts": groep_op_positie.get((cel.rij, cel.kolom + 1)) == cel.groep,
        }

    cellen = []
    for cel in alle_cellen:
        primary = primary_van[cel.groep] if cel.groep else cel
        cellen.append({
            "id": cel.pk,
            "rij": cel.rij,
            "kolom": cel.kolom,
            "type": primary.cel_type,
            "label": primary.display_label,
            "tekst": primary.label,
            "prijs": str(primary.effectieve_prijs.amount),
            "prijs_override": (
                str(primary.prijs.amount) if primary.prijs is not None else None
            ),
            "borg": (
                str(primary.borg.amount) if primary.borg is not None else None
            ),
            "effectieve_borg": str(primary.effectieve_borg),
            "groep": cel.groep,
            "primary_id": primary.pk,
            "is_primary": primary.pk == cel.pk,
            "buren": buren_zelfde_groep(cel),
            "bezet": primary.pk in bezet_ids,
            "gereserveerd": primary.gereserveerd,
            "geselecteerd": primary.pk in selected_ids,
            "telt_als": primary.tafelgewicht,
        })

    return {
        "rijen": zaalplan.rijen,
        "kolommen": zaalplan.kolommen,
        "standaard_prijs": str(zaalplan.standaard_prijs.amount),
        "prijs_excl_btw": zaalplan.prijs_excl_btw,
        "btw_percentage": str(zaalplan.btw_percentage),
        "max_tafels": zaalplan.evenement.standhouder_max_tafels,
        "cellen": cellen,
    }


def valideer_max_tafels(evenement, aantal):
    max_tafels = evenement.standhouder_max_tafels
    if aantal > max_tafels:
        raise ValueError(
            _("U kunt maximaal %(max)s tafel(s) selecteren. %(contact)s")
            % {
                "max": max_tafels,
                "contact": evenement.standhouder_tafel_limiet_bericht(),
            }
        )


def lock_tafelcellen(cel_ids):
    """Vergrendel de gekozen cellen in vaste volgorde, zodat twee afrondingen
    niet dezelfde tafel tegelijk als vrij kunnen zien."""
    ids = sorted({int(pk) for pk in cel_ids})
    if not ids:
        return
    list(ZaalplanCel.objects.select_for_update().filter(pk__in=ids).order_by("pk"))


@transaction.atomic
def save_tafel_keuzes(inschrijving, tafel_ids):
    zaalplan = get_zaalplan(inschrijving.evenement)
    if not zaalplan:
        raise ValueError("Geen zaalplan geconfigureerd.")

    unique_ids = set(str(t) for t in tafel_ids)

    cellen = list(ZaalplanCel.objects.select_for_update().filter(
        pk__in=tafel_ids,
        zaalplan=zaalplan,
        cel_type=CelType.TAFEL,
    ).order_by("pk"))
    if len(cellen) != len(unique_ids):
        raise ValueError("Ongeldige tafelselectie.")

    # Een object kan voor meer dan één tafel meetellen (telt_als_tafels).
    valideer_max_tafels(
        inschrijving.evenement,
        sum(cel.tafelgewicht for cel in cellen),
    )

    bezet_ids = get_bezette_cel_ids(exclude_inschrijving_id=inschrijving.pk)
    for cel in cellen:
        if cel.pk in bezet_ids or cel.gereserveerd:
            raise ValueError(f"Tafel {cel.display_label} is niet meer beschikbaar.")

    inschrijving.tafel_keuzes.all().delete()
    StandhouderTafelKeuze.objects.bulk_create([
        StandhouderTafelKeuze(inschrijving=inschrijving, cel=cel)
        for cel in cellen
    ])


def get_applicable_vragen(evenement, aantal_tafels):
    vragen = StandhouderVraag.objects.filter(evenement=evenement).order_by("volgorde", "id")
    result = []
    for vraag in vragen:
        if vraag.min_tafels and aantal_tafels < vraag.min_tafels:
            continue
        if vraag.max_tafels and aantal_tafels > vraag.max_tafels:
            continue
        result.append(vraag)
    return result


def save_vraag_antwoorden(inschrijving, cleaned_data, vragen):
    inschrijving.antwoorden.all().delete()
    for vraag in vragen:
        field_name = f"vraag_{vraag.pk}"
        if field_name not in cleaned_data:
            continue
        from pokemon.forms import serialize_vraag_antwoord
        StandhouderVraagAntwoord.objects.create(
            inschrijving=inschrijving,
            vraag=vraag,
            antwoord=serialize_vraag_antwoord(vraag, cleaned_data[field_name]),
        )


def build_prijsopbouw(inschrijving, kortingscode=None, korting_bedrag=None):
    from django.utils.translation import gettext

    def btw_label(percentage):
        # Vermijd %-formatting met %% (gettext/ValueError-risico).
        return f"{gettext('BTW')} {percentage}%"

    def met_excl_label(omschrijving):
        return f"{omschrijving} ({gettext('excl. btw')})"

    regels = []
    if inschrijving.zaalplan_actief:
        btw_totaal = Decimal("0")
        btw_pct = None
        for cel in inschrijving.gekozen_tafels.select_related("zaalplan"):
            zaalplan = cel.zaalplan
            excl = cel.effectieve_prijs.amount
            _incl, btw = bedrag_met_btw(
                excl,
                zaalplan.prijs_excl_btw,
                zaalplan.btw_percentage,
            )
            omschrijving = f"Tafel {cel.display_label}"
            if zaalplan.prijs_excl_btw:
                omschrijving = met_excl_label(omschrijving)
                btw_totaal += btw
                btw_pct = zaalplan.btw_percentage
            regels.append({
                "omschrijving": omschrijving,
                "bedrag": excl,
                "is_btw": False,
            })
        if btw_totaal:
            regels.append({
                "omschrijving": btw_label(btw_pct),
                "bedrag": btw_totaal,
                "is_btw": True,
            })
    elif inschrijving.aantal_tafels_manueel:
        evenement = inschrijving.evenement
        excl = (
            inschrijving.aantal_tafels_manueel
            * evenement.standhouder_prijs_per_tafel.amount
        )
        _incl, btw = bedrag_met_btw(
            excl,
            evenement.standhouder_prijs_excl_btw,
            evenement.standhouder_prijs_btw_percentage,
        )
        omschrijving = f"{inschrijving.aantal_tafels_manueel} tafel(s)"
        if evenement.standhouder_prijs_excl_btw:
            omschrijving = met_excl_label(omschrijving)
        regels.append({
            "omschrijving": omschrijving,
            "bedrag": excl,
            "is_btw": False,
        })
        if btw:
            regels.append({
                "omschrijving": btw_label(evenement.standhouder_prijs_btw_percentage),
                "bedrag": btw,
                "is_btw": True,
            })
    for antwoord in inschrijving.antwoorden.select_related("vraag"):
        vraag = antwoord.vraag
        # Borg-vragen: enkel in borg_melding, niet in prijsopbouw/totaal.
        if vraag.is_borg:
            continue
        if vraag.vraag_type == VraagType.MULTISELECT:
            for omschrijving, excl in antwoord.toeslag_regels():
                _incl, btw = bedrag_met_btw(
                    excl,
                    vraag.prijs_toeslag_excl_btw,
                    vraag.prijs_toeslag_btw_percentage,
                )
                if vraag.prijs_toeslag_excl_btw:
                    omschrijving = met_excl_label(omschrijving)
                regels.append({
                    "omschrijving": omschrijving,
                    "bedrag": excl,
                    "is_btw": False,
                })
                if btw:
                    regels.append({
                        "omschrijving": btw_label(vraag.prijs_toeslag_btw_percentage),
                        "bedrag": btw,
                        "is_btw": True,
                    })
            continue

        if antwoord.heeft_toeslag():
            excl = antwoord.toeslag_bedrag()
            _incl, btw = bedrag_met_btw(
                excl,
                vraag.prijs_toeslag_excl_btw,
                vraag.prijs_toeslag_btw_percentage,
            )
            omschrijving = vraag.tekst
            if vraag.prijs_toeslag_excl_btw:
                omschrijving = met_excl_label(omschrijving)
            regels.append({
                "omschrijving": omschrijving,
                "bedrag": excl,
                "is_btw": False,
            })
            if btw:
                regels.append({
                    "omschrijving": btw_label(vraag.prijs_toeslag_btw_percentage),
                    "bedrag": btw,
                    "is_btw": True,
                })
    subtotaal = sum((r["bedrag"] for r in regels), Decimal("0"))
    if kortingscode and korting_bedrag and korting_bedrag > 0:
        regels.append({
            "omschrijving": gettext("Korting (%(code)s)") % {"code": kortingscode.code},
            "bedrag": korting_bedrag,
            "is_korting": True,
            "is_btw": False,
        })
    totaal = max(subtotaal - (korting_bedrag or Decimal("0")), Decimal("0"))
    return regels, totaal


def standhouder_base_context(request, evenement, actieve_key):
    from django.utils.translation import gettext as _

    if evenement.standhouder_zaalplan_actief:
        volgorde = [
            ("tafels", _("Tafels")),
            ("gegevens", _("Gegevens")),
            ("vragen", _("Vragen")),
            ("overzicht", _("Overzicht")),
        ]
    else:
        volgorde = [
            ("gegevens", _("Gegevens")),
            ("vragen", _("Vragen")),
            ("overzicht", _("Overzicht")),
        ]

    stappen = []
    actief_nummer = 1
    for i, (key, label) in enumerate(volgorde, start=1):
        if key == actieve_key:
            actief_nummer = i
        stappen.append({
            "nummer": i,
            "label": label,
            "key": key,
            "url_name": STANDHOUDER_STAP_URLS[key],
        })

    for stap in stappen:
        stap["is_reachable"] = stap["nummer"] < actief_nummer

    return {
        "evenement": evenement,
        "sponsors": Sponsor.objects.all().order_by("-volgorde_footer") or [],
        "wizard_stap": actief_nummer,
        "inschrijving": get_concept_inschrijving(request, evenement),
        "stappen": stappen,
        "zaalplan_actief": evenement.standhouder_zaalplan_actief,
    }
