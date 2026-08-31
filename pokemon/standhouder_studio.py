"""Admin standhouder studio: preview context builders (reuses public wizard helpers)."""

from django.urls import reverse
from django.utils.translation import gettext as _

from pokemon.forms import (
    StandhouderGegevensForm,
    build_standhouder_vragen_form,
)
from pokemon.models import VraagType
from pokemon.standhouder_wizard import (
    build_prijsopbouw,
    get_applicable_vragen,
    get_or_create_studio_preview_inschrijving,
    get_zaalplan,
    serialize_zaalplan_grid,
    standhouder_base_context,
)


PREVIEW_STEPS_ZAALPLAN = ("tafels", "gegevens", "vragen", "overzicht")
PREVIEW_STEPS_MANUEEL = ("gegevens", "vragen", "overzicht")


def preview_steps_for(evenement):
    if evenement.standhouder_zaalplan_actief:
        return list(PREVIEW_STEPS_ZAALPLAN)
    return list(PREVIEW_STEPS_MANUEEL)


def normalize_preview_step(evenement, step):
    allowed = preview_steps_for(evenement)
    if step in allowed:
        return step
    return allowed[0]


def studio_preview_base_context(request, evenement, step):
    """Like standhouder_base_context but for studio preview (separate concept session)."""
    step = normalize_preview_step(evenement, step)
    context = standhouder_base_context(request, evenement, step)
    inschrijving = get_or_create_studio_preview_inschrijving(request, evenement)
    context["inschrijving"] = inschrijving
    context["preview_embed"] = True
    context["studio_preview"] = True
    context["preview_step"] = step

    # Make wizard nav jump within the iframe preview URLs
    preview_base = reverse("admin:pokemon_standhouder_studio_preview", args=[evenement.pk])
    for stap in context["stappen"]:
        stap["preview_url"] = f"{preview_base}?step={stap['key']}"
        stap["is_reachable"] = True

    return context, inschrijving, step


def build_preview_step_context(request, evenement, step):
    import json

    context, inschrijving, step = studio_preview_base_context(request, evenement, step)
    template = "admin/pokemon/standhouder_preview/step.html"

    if step == "tafels":
        zaalplan = get_zaalplan(evenement)
        context["zaalplan"] = zaalplan
        context["grid_json"] = (
            json.dumps(serialize_zaalplan_grid(zaalplan, inschrijving)) if zaalplan else "null"
        )
    elif step == "gegevens":
        context["form"] = StandhouderGegevensForm(instance=inschrijving)
    elif step == "vragen":
        vraag_aantal = not evenement.standhouder_zaalplan_actief
        if vraag_aantal:
            if inschrijving.aantal_tafels_manueel:
                vragen = get_applicable_vragen(evenement, inschrijving.aantal_tafels_manueel)
            else:
                vragen = []
            aantal_voor_filter = inschrijving.aantal_tafels_manueel or 0
        else:
            vragen = get_applicable_vragen(evenement, inschrijving.aantal_tafels)
            aantal_voor_filter = inschrijving.aantal_tafels

        VragenForm = build_standhouder_vragen_form(
            vragen,
            aantal_voor_filter,
            vraag_aantal_tafels=vraag_aantal,
            max_tafels=evenement.standhouder_max_tafels,
        )
        initial = {}
        if vraag_aantal and inschrijving.aantal_tafels_manueel:
            initial["aantal_tafels"] = inschrijving.aantal_tafels_manueel
        for antwoord in inschrijving.antwoorden.select_related("vraag"):
            field_name = f"vraag_{antwoord.vraag_id}"
            if antwoord.vraag.vraag_type == VraagType.BOOLEAN:
                initial[field_name] = antwoord.antwoord
            elif antwoord.vraag.vraag_type == VraagType.CHECKBOX:
                initial[field_name] = antwoord.antwoord == "true"
            else:
                initial[field_name] = antwoord.antwoord
        context["form"] = VragenForm(initial=initial)
        context["vragen"] = vragen
    elif step == "overzicht":
        try:
            inschrijving.bereken_totaal()
            regels, totaal = build_prijsopbouw(inschrijving)
        except Exception:
            regels, totaal = [], 0
        context["prijsopbouw"] = regels
        context["totaal"] = totaal
        context["antwoorden"] = inschrijving.antwoorden.select_related("vraag").order_by(
            "vraag__volgorde"
        )
        context["online_betaling"] = evenement.standhouder_betaling_verplicht

    return context, template


def handle_preview_post(request, evenement, step, inschrijving):
    """Process interactive preview form posts. Returns (redirect_step, error_or_None)."""
    from pokemon.forms import StandhouderGegevensForm, build_standhouder_vragen_form
    from pokemon.standhouder_wizard import (
        get_applicable_vragen,
        save_tafel_keuzes,
        save_vraag_antwoorden,
    )

    action = request.POST.get("preview_action")
    step = normalize_preview_step(evenement, step)

    if action == "save_tafels":
        tafel_ids = [t for t in request.POST.getlist("tafels") if t]
        if not tafel_ids:
            return step, "Selecteer minstens één tafel."
        try:
            save_tafel_keuzes(inschrijving, tafel_ids)
            return "gegevens", None
        except ValueError as exc:
            return step, str(exc)

    if action == "save_gegevens":
        form = StandhouderGegevensForm(request.POST, instance=inschrijving)
        if form.is_valid():
            form.save()
            return "vragen", None
        return step, form

    if action == "reload_vragen":
        if not evenement.standhouder_zaalplan_actief:
            raw = request.POST.get("aantal_tafels")
            try:
                aantal = int(raw)
            except (TypeError, ValueError):
                return step, _("Ongeldig aantal tafels.")
            if aantal < 1 or aantal > evenement.standhouder_max_tafels:
                return step, _("Aantal tafels buiten limiet.")
            inschrijving.aantal_tafels_manueel = aantal
            inschrijving.save(update_fields=["aantal_tafels_manueel"])
        return "vragen", None

    if action == "save_vragen":
        vraag_aantal = not evenement.standhouder_zaalplan_actief
        if vraag_aantal and inschrijving.aantal_tafels_manueel:
            vragen = get_applicable_vragen(evenement, inschrijving.aantal_tafels_manueel)
        elif not vraag_aantal:
            vragen = get_applicable_vragen(evenement, inschrijving.aantal_tafels)
        else:
            vragen = []

        aantal_voor_filter = (
            inschrijving.aantal_tafels_manueel or 0
            if vraag_aantal
            else inschrijving.aantal_tafels
        )
        VragenForm = build_standhouder_vragen_form(
            vragen,
            aantal_voor_filter,
            vraag_aantal_tafels=vraag_aantal,
            max_tafels=evenement.standhouder_max_tafels,
        )
        form = VragenForm(request.POST)
        if form.is_valid():
            if vraag_aantal:
                inschrijving.aantal_tafels_manueel = form.cleaned_data.get("aantal_tafels")
                inschrijving.save(update_fields=["aantal_tafels_manueel"])
                if not vragen:
                    applicable = get_applicable_vragen(
                        evenement, inschrijving.aantal_tafels_manueel
                    )
                    if applicable:
                        return "vragen", None
                    return "overzicht", None
            save_vraag_antwoorden(inschrijving, form.cleaned_data, vragen)
            return "overzicht", None
        return step, form

    return step, None
