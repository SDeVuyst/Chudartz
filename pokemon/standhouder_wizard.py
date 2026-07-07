from decimal import Decimal

from pokemon.models import (
    CelType,
    Sponsor,
    StandhouderInschrijving,
    StandhouderInschrijvingStatus,
    StandhouderTafelKeuze,
    StandhouderVraag,
    StandhouderVraagAntwoord,
    Zaalplan,
    ZaalplanCel,
)


def session_key(evenement):
    return f"standhouder_{evenement.slug}"


def get_concept_inschrijving(request, evenement):
    pk = request.session.get(session_key(evenement))
    if not pk:
        return None
    return StandhouderInschrijving.objects.filter(
        pk=pk,
        evenement=evenement,
        status=StandhouderInschrijvingStatus.CONCEPT,
    ).first()


def set_concept_inschrijving(request, inschrijving):
    request.session[session_key(inschrijving.evenement)] = inschrijving.pk


def clear_concept_inschrijving(request, evenement):
    request.session.pop(session_key(evenement), None)


def get_or_create_concept_inschrijving(request, evenement):
    inschrijving = get_concept_inschrijving(request, evenement)
    if inschrijving:
        return inschrijving
    inschrijving = StandhouderInschrijving.objects.create(
        evenement=evenement,
        status=StandhouderInschrijvingStatus.CONCEPT,
    )
    set_concept_inschrijving(request, inschrijving)
    return inschrijving


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
            "groep": cel.groep,
            "primary_id": primary.pk,
            "is_primary": primary.pk == cel.pk,
            "buren": buren_zelfde_groep(cel),
            "bezet": primary.pk in bezet_ids,
            "gereserveerd": primary.gereserveerd,
            "geselecteerd": primary.pk in selected_ids,
        })

    return {
        "rijen": zaalplan.rijen,
        "kolommen": zaalplan.kolommen,
        "standaard_prijs": str(zaalplan.standaard_prijs.amount),
        "cellen": cellen,
    }


def save_tafel_keuzes(inschrijving, tafel_ids):
    zaalplan = get_zaalplan(inschrijving.evenement)
    if not zaalplan:
        raise ValueError("Geen zaalplan geconfigureerd.")

    cellen = ZaalplanCel.objects.filter(
        pk__in=tafel_ids,
        zaalplan=zaalplan,
        cel_type=CelType.TAFEL,
    )
    if cellen.count() != len(set(str(t) for t in tafel_ids)):
        raise ValueError("Ongeldige tafelselectie.")

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


def build_prijsopbouw(inschrijving):
    regels = []
    for cel in inschrijving.gekozen_tafels:
        regels.append({
            "omschrijving": f"Tafel {cel.display_label}",
            "bedrag": cel.effectieve_prijs.amount,
        })
    for antwoord in inschrijving.antwoorden.select_related("vraag"):
        if antwoord.heeft_toeslag():
            regels.append({
                "omschrijving": antwoord.vraag.tekst,
                "bedrag": antwoord.vraag.prijs_toeslag.amount,
            })
    totaal = sum((r["bedrag"] for r in regels), Decimal("0"))
    return regels, totaal


def standhouder_base_context(request, evenement, stap):
    from django.utils.translation import gettext as _
    return {
        "evenement": evenement,
        "sponsors": Sponsor.objects.all().order_by("-volgorde_footer") or [],
        "wizard_stap": stap,
        "inschrijving": get_concept_inschrijving(request, evenement),
        "stappen": [
            {"nummer": 1, "label": _("Tafels")},
            {"nummer": 2, "label": _("Gegevens")},
            {"nummer": 3, "label": _("Vragen")},
            {"nummer": 4, "label": _("Overzicht")},
        ],
    }
