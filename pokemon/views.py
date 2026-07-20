import json
from decimal import Decimal
from email.utils import formataddr

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.db.models import Case, FloatField, IntegerField, Value, When
from django.db.models.expressions import ExpressionWrapper
from django.db.models.functions import Extract
from django.http import (BadHeaderError, HttpResponse, HttpResponseBadRequest,
                         HttpResponseNotFound, JsonResponse)
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from darts.utils import helpers
from pokemon.forms import (
    ContactForm,
    StandhouderGegevensForm,
    StandhouderTafelsForm,
    TicketGegevensForm,
    StandhouderOverzichtForm,
    TicketOverzichtForm,
    build_standhouder_vragen_form,
)
from pokemon.models import (
    Evenement,
    EvenementFoto,
    GateDevice,
    Participant,
    Payment,
    PaymentStatus,
    Sponsor,
    StandhouderVraag,
    Ticket,
    VraagType,
    StandhouderInschrijving,
)
from pokemon.services.attendance import AttendanceError, check_in_participant
from pokemon.payment import MollieClient
from pokemon.services.standhouder import (
    StandhouderValidationError,
    finalize_inschrijving,
    verwerk_standhouder_betaling,
)
from pokemon.services.ticket import (
    TicketValidationError,
    build_prijsopbouw as build_ticket_prijsopbouw,
    finalize_checkout,
    validate_kortingscode,
    validate_ticket_selection,
    verwerk_ticket_betaling,
)
from pokemon.standhouder_wizard import (
    build_prijsopbouw,
    clear_concept_inschrijving,
    email_sent_session_key,
    get_applicable_vragen,
    get_concept_inschrijving,
    get_or_create_concept_inschrijving,
    get_zaalplan,
    heeft_gegevens,
    pending_inschrijving_session_key,
    save_tafel_keuzes,
    save_vraag_antwoorden,
    serialize_zaalplan_grid,
    standhouder_base_context,
    voorlopig_session_key,
)
from pokemon.ticket_wizard import (
    clear_wizard_data,
    get_ticket_quantities,
    get_wizard_data,
    heeft_ticket_gegevens,
    heeft_tickets,
    pending_payment_session_key,
    serialize_tickets_for_js,
    set_wizard_data,
    ticket_base_context,
)


def index(request):
    return TemplateResponse(request, 'pokemon/pages/index.html', get_default_context())

def over_ons(request):
    return TemplateResponse(request, 'pokemon/pages/about.html', get_default_context())

def sponsors(request):
    context = get_default_context()
    context['sponsors_pagina'] = Sponsor.objects.all().order_by('-volgorde_pagina')
    return TemplateResponse(request, 'pokemon/pages/sponsors.html', context)

def contact(request):
    # request must always be post
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method.'})
    
    if not helpers.verify_recaptcha(request.GET.get('recaptcha_token')):
        return JsonResponse({
            'success': False,
            'error': "reCAPTCHA gefaald. Gelieve opnieuw te proberen."
        })

    form = ContactForm(request.POST)

    if not form.is_valid():
        return JsonResponse({'success': False, 'error': 'Form is not valid.'})
    
    name =  form.cleaned_data['name']
    email = form.cleaned_data['email']
    phone = form.cleaned_data['phone']
    subject = form.cleaned_data['subject']
    message = form.cleaned_data['message']

    try:
        # Send mail to admins
        send_mail(
            f'Contact Form - {subject}',
            f'Name: {name}\nEmail: {email}\nPhone: {phone}\nMessage: {message}',
            formataddr(('Contact | ChudartZ Collectibles', settings.EMAIL_HOST_USER)),
            [settings.EMAIL_HOST_USER],
            fail_silently=False,
        )

        # Send confirmation mail to user
        send_mail(
            'Chudartz | Bericht Ontvangen',
            "Beste\n\nBedankt voor het invullen van het contactformulier. Wij hebben uw bericht in goede orde ontvangen en zullen zo snel mogelijk contact met u opnemen.\nHou voor de zekerheid ook even je spam in de gaten, soms belandt de mail daar.\n\nMet vriendelijke groeten\n\nTeam ChudartZ",
            formataddr(('Contact | ChudartZ', settings.EMAIL_HOST_USER)),
            [email],
            fail_silently=False
        )

        return JsonResponse({'success': True})
    
    except BadHeaderError:
        return JsonResponse({'success': False, 'error': 'Invalid header found.'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


def evenementen(request):
    today = timezone.now().date()
    evenementen = Evenement.objects.filter(toon_op_site=True).annotate(
        is_future=Case(
            When(start_datum__gte=today, then=Value(0)),
            default=Value(1),
            output_field=IntegerField(),
        ),
        sort_date=Case(
            When(is_future=0, then=Extract('start_datum', 'epoch')),
            default=ExpressionWrapper(
                -Extract('start_datum', 'epoch'),
                output_field=FloatField(),
            ),
            output_field=FloatField(),
        ),
    ).order_by('is_future', 'volgorde', 'sort_date')

    paginator = Paginator(evenementen, 12)

    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = get_default_context()
    context["evenementen"] = page_obj
    context["has_future_events"] = any(
        evenement.is_in_future or evenement.is_bezig for evenement in page_obj
    )
    context["has_past_events"] = any(
        not evenement.is_in_future and not evenement.is_bezig for evenement in page_obj
    )
    context["enable_pagination"] = paginator.num_pages > 1

    return TemplateResponse(request, 'pokemon/pages/evenementen.html', context)


def _get_gerelateerde_evenementen(evenement, limit=3):
    today = timezone.now().date()
    return Evenement.objects.filter(toon_op_site=True).exclude(pk=evenement.pk).annotate(
        is_future=Case(
            When(start_datum__gte=today, then=Value(0)),
            default=Value(1),
            output_field=IntegerField(),
        ),
        sort_date=Case(
            When(is_future=0, then=Extract('start_datum', 'epoch')),
            default=ExpressionWrapper(
                -Extract('start_datum', 'epoch'),
                output_field=FloatField(),
            ),
            output_field=FloatField(),
        ),
    ).order_by('is_future', 'volgorde', 'sort_date')[:limit]


def evenement(request, slug):
    evenement = get_object_or_404(Evenement, slug=slug)

    if not evenement.toon_op_site:
        return HttpResponseNotFound()

    context = {
        "evenement": evenement,
        "fotos": EvenementFoto.objects.filter(evenement=evenement).order_by("-volgorde"),
        "tickets": Ticket.objects.filter(event=evenement).order_by("pk"),
        "partners": evenement.partners.all(),
        'sponsors': Sponsor.objects.all().order_by('-volgorde_footer') or [],
        "gerelateerde_evenementen": _get_gerelateerde_evenementen(evenement),
        "tickets_kopen_mogelijk": evenement.enable_inschrijvingen and not evenement.is_sold_out,
    }
    return TemplateResponse(request, 'pokemon/pages/evenement.html', context)


def _get_ticket_evenement(slug):
    evenement = get_object_or_404(Evenement, slug=slug)
    if not evenement.toon_op_site:
        return None
    return evenement


def ticket_kopen(request, slug):
    """Stap 1: tickets selecteren."""
    evenement = _get_ticket_evenement(slug)
    if not evenement:
        return HttpResponseNotFound()

    if not evenement.enable_inschrijvingen or evenement.is_sold_out:
        return redirect("evenement", slug=slug)

    context = ticket_base_context(request, evenement, "tickets")
    wizard_data = get_wizard_data(request, evenement)
    context["tickets_json"] = json.dumps(serialize_tickets_for_js(evenement))
    context["selected_quantities_json"] = json.dumps(wizard_data.get("ticket_quantities", {}))

    if request.method == "POST":
        quantities = {}
        for ticket in context["tickets"]:
            if ticket.is_sold_out:
                continue
            key = f"ticket_{ticket.pk}"
            try:
                qty = int(request.POST.get(key, 0))
            except (TypeError, ValueError):
                qty = 0
            if qty > 0:
                quantities[str(ticket.pk)] = qty

        try:
            validate_ticket_selection(evenement, {int(k): v for k, v in quantities.items()})
            wizard_data["ticket_quantities"] = quantities
            set_wizard_data(request, evenement, wizard_data)
            return redirect("ticket_gegevens", slug=slug)
        except TicketValidationError as exc:
            context["error"] = str(exc)

    return TemplateResponse(request, "pokemon/pages/tickets/stap1.html", context)


def ticket_gegevens(request, slug):
    """Stap 2: contactgegevens."""
    evenement = _get_ticket_evenement(slug)
    if not evenement:
        return HttpResponseNotFound()

    wizard_data = get_wizard_data(request, evenement)
    if not heeft_tickets(wizard_data):
        return redirect("ticket_kopen", slug=slug)

    context = ticket_base_context(request, evenement, "gegevens")
    initial = {
        "email": wizard_data.get("email", ""),
        "first_name": wizard_data.get("first_name", ""),
        "last_name": wizard_data.get("last_name", ""),
    }

    if request.method == "POST":
        form = TicketGegevensForm(request.POST)
        if form.is_valid():
            wizard_data.update(form.cleaned_data)
            set_wizard_data(request, evenement, wizard_data)
            return redirect("ticket_overzicht", slug=slug)
    else:
        form = TicketGegevensForm(initial=initial)

    context["form"] = form
    return TemplateResponse(request, "pokemon/pages/tickets/stap2.html", context)


def ticket_overzicht(request, slug):
    """Stap 3: overzicht, kortingscode en betalen."""
    evenement = _get_ticket_evenement(slug)
    if not evenement:
        return HttpResponseNotFound()

    wizard_data = get_wizard_data(request, evenement)
    if not heeft_tickets(wizard_data):
        return redirect("ticket_kopen", slug=slug)
    if not heeft_ticket_gegevens(wizard_data):
        return redirect("ticket_gegevens", slug=slug)

    quantities = get_ticket_quantities(wizard_data)
    kortingscode_obj = None
    korting_bedrag = Decimal("0")
    code = wizard_data.get("kortingscode", "")

    if code:
        try:
            kortingscode_obj, korting_bedrag = validate_kortingscode(code, evenement, quantities)
        except TicketValidationError:
            wizard_data.pop("kortingscode", None)
            set_wizard_data(request, evenement, wizard_data)

    prijsopbouw, subtotaal, totaal = build_ticket_prijsopbouw(
        evenement, quantities, kortingscode_obj, korting_bedrag
    )

    context = ticket_base_context(request, evenement, "overzicht")
    context.update({
        "prijsopbouw": prijsopbouw,
        "subtotaal": subtotaal,
        "totaal": totaal,
        "kortingscode": code,
        "korting_bedrag": korting_bedrag,
        "quantities": quantities,
    })

    if request.method == "POST":
        if "apply_kortingscode" in request.POST:
            code_input = request.POST.get("kortingscode", "").strip()
            if code_input:
                try:
                    validate_kortingscode(code_input, evenement, quantities)
                    wizard_data["kortingscode"] = code_input
                    set_wizard_data(request, evenement, wizard_data)
                except TicketValidationError as exc:
                    context["error"] = str(exc)
                    context["form"] = TicketOverzichtForm(initial={"kortingscode": code_input})
                    return TemplateResponse(request, "pokemon/pages/tickets/stap3.html", context)
            else:
                wizard_data.pop("kortingscode", None)
                set_wizard_data(request, evenement, wizard_data)
            return redirect("ticket_overzicht", slug=slug)

        form = TicketOverzichtForm(request.POST)
        if form.is_valid():
            code_input = form.cleaned_data.get("kortingscode", "").strip()
            if code_input:
                try:
                    validate_kortingscode(code_input, evenement, quantities)
                    wizard_data["kortingscode"] = code_input
                except TicketValidationError as exc:
                    context["error"] = str(exc)
                    context["form"] = form
                    return TemplateResponse(request, "pokemon/pages/tickets/stap3.html", context)
            else:
                wizard_data.pop("kortingscode", None)

            set_wizard_data(request, evenement, wizard_data)

            try:
                payment, checkout_url = finalize_checkout(request, evenement, wizard_data)
                request.session[pending_payment_session_key(evenement)] = payment.pk
                clear_wizard_data(request, evenement)
                return redirect(checkout_url)
            except TicketValidationError as exc:
                context["error"] = str(exc)
                context["form"] = form
                return TemplateResponse(request, "pokemon/pages/tickets/stap3.html", context)

        context["form"] = form
    else:
        context["form"] = TicketOverzichtForm(initial={"kortingscode": code})

    return TemplateResponse(request, "pokemon/pages/tickets/stap3.html", context)


def ticket_validate_kortingscode(request, slug):
    """AJAX: valideer kortingscode en retourneer prijsopbouw."""
    if request.method != "POST":
        return JsonResponse({"valid": False, "error": "Invalid method"}, status=405)

    evenement = _get_ticket_evenement(slug)
    if not evenement:
        return JsonResponse({"valid": False, "error": "Not found"}, status=404)

    wizard_data = get_wizard_data(request, evenement)
    quantities = get_ticket_quantities(wizard_data)
    code = request.POST.get("kortingscode", "").strip()

    if not code:
        prijsopbouw, subtotaal, totaal = build_ticket_prijsopbouw(evenement, quantities)
        return JsonResponse({
            "valid": True,
            "subtotaal": str(subtotaal),
            "korting": "0.00",
            "totaal": str(totaal),
            "regels": [
                {"omschrijving": r["omschrijving"], "bedrag": str(r["bedrag"])}
                for r in prijsopbouw
            ],
        })

    try:
        kortingscode_obj, korting_bedrag = validate_kortingscode(code, evenement, quantities)
        prijsopbouw, subtotaal, totaal = build_ticket_prijsopbouw(
            evenement, quantities, kortingscode_obj, korting_bedrag
        )
        return JsonResponse({
            "valid": True,
            "subtotaal": str(subtotaal),
            "korting": str(korting_bedrag),
            "totaal": str(totaal),
            "code": kortingscode_obj.code,
            "regels": [
                {"omschrijving": r["omschrijving"], "bedrag": str(r["bedrag"])}
                for r in prijsopbouw
            ],
        })
    except TicketValidationError as exc:
        return JsonResponse({"valid": False, "error": str(exc)})


def evenement_success(request, slug):
    context = get_default_context()
    evenement = get_object_or_404(Evenement, slug=slug)
    context["evenement"] = evenement

    if not evenement.toon_op_site:
        return HttpResponseNotFound()

    payment_pk = request.session.get(pending_payment_session_key(evenement))
    payment = None
    if payment_pk:
        payment = Payment.objects.filter(pk=payment_pk).first()

    if payment and payment.mollie_id:
        try:
            mollie_payment = MollieClient().client.payments.get(payment.mollie_id)
            mollie_status = mollie_payment.get("status", "").lower()
            valid_statuses = [choice[0] for choice in PaymentStatus.CHOICES]
            if mollie_status in valid_statuses and mollie_status != payment.status:
                payment.status = mollie_status
                payment.save()
                verwerk_ticket_betaling(payment, mollie_status)
                payment.refresh_from_db()
        except Exception:
            pass

        context["payment_status"] = payment.status
        context["success"] = payment.status == PaymentStatus.PAID
        context["pending"] = payment.status == PaymentStatus.OPEN
        request.session.pop(pending_payment_session_key(evenement), None)
    else:
        context["success"] = True
        context["pending"] = False

    return TemplateResponse(request, 'pokemon/pages/evenement-inschrijving-response.html', context)


def _get_standhouder_evenement(slug):
    evenement = get_object_or_404(Evenement, slug=slug)
    if not evenement.toon_op_site:
        return None
    return evenement


def _require_concept_inschrijving(request, evenement):
    inschrijving = get_concept_inschrijving(request, evenement)
    if not inschrijving:
        return None
    return inschrijving


def standhouder(request, slug):
    """Stap 1: tafels kiezen (of overslaan als zaalplan uitstaat)."""
    evenement = _get_standhouder_evenement(slug)
    if not evenement:
        return HttpResponseNotFound()

    if not evenement.standhouder_inschrijving_mogelijk:
        return redirect("evenement", slug=slug)

    # Zaalplan uitgeschakeld -> tafelkeuze overslaan
    if not evenement.standhouder_zaalplan_actief:
        get_or_create_concept_inschrijving(request, evenement)
        return redirect("standhouder_gegevens", slug=slug)

    inschrijving = get_or_create_concept_inschrijving(request, evenement)
    zaalplan = get_zaalplan(evenement)
    context = standhouder_base_context(request, evenement, "tafels")
    context["zaalplan"] = zaalplan
    context["grid_json"] = json.dumps(serialize_zaalplan_grid(zaalplan, inschrijving)) if zaalplan else "null"

    if request.method == "POST":
        if not evenement.standhouder_inschrijving_mogelijk:
            context["error"] = "Standhouder inschrijvingen gesloten."
            return TemplateResponse(request, "pokemon/pages/standhouder/error.html", context)

        if not zaalplan:
            context["error"] = "Er is nog geen zaalplan geconfigureerd voor dit evenement."
            return TemplateResponse(request, "pokemon/pages/standhouder/stap1.html", context)

        tafel_ids = [t for t in request.POST.getlist("tafels") if t]
        if not tafel_ids:
            context["error"] = "Selecteer minstens één tafel."
            return TemplateResponse(request, "pokemon/pages/standhouder/stap1.html", context)
        try:
            save_tafel_keuzes(inschrijving, tafel_ids)
            return redirect("standhouder_gegevens", slug=slug)
        except ValueError as exc:
            context["error"] = str(exc)

    return TemplateResponse(request, "pokemon/pages/standhouder/stap1.html", context)


def standhouder_gegevens(request, slug):
    """Contactgegevens."""
    evenement = _get_standhouder_evenement(slug)
    if not evenement:
        return HttpResponseNotFound()

    inschrijving = _require_concept_inschrijving(request, evenement)
    if not inschrijving:
        return redirect("standhouder", slug=slug)

    # Tafelkeuze verplicht enkel als het zaalplan actief is
    if evenement.standhouder_zaalplan_actief and inschrijving.aantal_tafels == 0:
        return redirect("standhouder", slug=slug)

    context = standhouder_base_context(request, evenement, "gegevens")

    if request.method == "POST":
        if not evenement.standhouder_inschrijving_mogelijk:
            context["error"] = "Standhouder inschrijvingen gesloten."
            return TemplateResponse(request, "pokemon/pages/standhouder/error.html", context)

        form = StandhouderGegevensForm(request.POST, instance=inschrijving)
        if form.is_valid():
            form.save()
            return redirect("standhouder_vragen", slug=slug)
        context["form"] = form
    else:
        context["form"] = StandhouderGegevensForm(instance=inschrijving)

    return TemplateResponse(request, "pokemon/pages/standhouder/stap2.html", context)


def standhouder_tafels(request, slug):
    return redirect("standhouder", slug=slug)


def standhouder_vragen(request, slug):
    evenement = _get_standhouder_evenement(slug)
    if not evenement:
        return HttpResponseNotFound()

    inschrijving = _require_concept_inschrijving(request, evenement)
    if not inschrijving:
        return redirect("standhouder", slug=slug)

    if evenement.standhouder_zaalplan_actief and inschrijving.aantal_tafels == 0:
        return redirect("standhouder", slug=slug)

    if not heeft_gegevens(inschrijving):
        return redirect("standhouder_gegevens", slug=slug)

    vraag_aantal = not evenement.standhouder_zaalplan_actief

    if vraag_aantal:
        if inschrijving.aantal_tafels_manueel:
            vragen = get_applicable_vragen(evenement, inschrijving.aantal_tafels_manueel)
        else:
            vragen = []
    else:
        vragen = get_applicable_vragen(evenement, inschrijving.aantal_tafels)

    aantal_voor_filter = (
        inschrijving.aantal_tafels_manueel or 0
        if vraag_aantal
        else inschrijving.aantal_tafels
    )

    VragenForm = build_standhouder_vragen_form(
        vragen, aantal_voor_filter,
        vraag_aantal_tafels=vraag_aantal,
        max_tafels=evenement.standhouder_max_tafels,
    )

    context = standhouder_base_context(request, evenement, "vragen")

    if request.method == "POST":
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
                        return redirect("standhouder_vragen", slug=slug)
                    return redirect("standhouder_overzicht", slug=slug)
            save_vraag_antwoorden(inschrijving, form.cleaned_data, vragen)
            return redirect("standhouder_overzicht", slug=slug)
        context["form"] = form
    else:
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
    return TemplateResponse(request, "pokemon/pages/standhouder/stap3.html", context)


def standhouder_overzicht(request, slug):
    evenement = _get_standhouder_evenement(slug)
    if not evenement:
        return HttpResponseNotFound()

    inschrijving = _require_concept_inschrijving(request, evenement)
    if not inschrijving:
        return redirect("standhouder", slug=slug)

    if inschrijving.aantal_tafels == 0:
        # Terug naar de juiste eerste stap
        if evenement.standhouder_zaalplan_actief:
            return redirect("standhouder", slug=slug)
        return redirect("standhouder_vragen", slug=slug)

    if not heeft_gegevens(inschrijving):
        return redirect("standhouder_gegevens", slug=slug)

    inschrijving.bereken_totaal()
    regels, totaal = build_prijsopbouw(inschrijving)
    context = standhouder_base_context(request, evenement, "overzicht")
    context["prijsopbouw"] = regels
    context["totaal"] = totaal
    context["antwoorden"] = inschrijving.antwoorden.select_related("vraag").order_by("vraag__volgorde")
    context["online_betaling"] = evenement.standhouder_betaling_verplicht

    if request.method == "POST":
        if not evenement.standhouder_inschrijving_mogelijk:
            context["error"] = "Standhouder inschrijvingen gesloten."
            return TemplateResponse(request, "pokemon/pages/standhouder/error.html", context)

        form = StandhouderOverzichtForm(request.POST)
        if not form.is_valid():
            context["error"] = "Gelieve alle voorwaarden te aanvaarden."
            return TemplateResponse(request, "pokemon/pages/standhouder/stap4.html", context)

        if not helpers.verify_recaptcha(request.POST.get("recaptcha_token")):
            context["error"] = "reCAPTCHA gefaald. Gelieve opnieuw te proberen."
            return TemplateResponse(request, "pokemon/pages/standhouder/stap4.html", context)

        try:
            result = finalize_inschrijving(inschrijving, request)
            clear_concept_inschrijving(request, evenement)
            request.session[pending_inschrijving_session_key(evenement)] = inschrijving.pk
            if result.redirect_url:
                return redirect(result.redirect_url)
            request.session[email_sent_session_key(evenement)] = result.email_sent
            request.session[voorlopig_session_key(evenement)] = result.voorlopig
            return redirect("standhouder_success", slug=slug)
        except StandhouderValidationError as exc:
            context["error"] = str(exc)

    return TemplateResponse(request, "pokemon/pages/standhouder/stap4.html", context)


def standhouder_success(request, slug):
    evenement = _get_standhouder_evenement(slug)
    if not evenement:
        return HttpResponseNotFound()

    context = standhouder_base_context(request, evenement, "success")
    inschrijving_pk = request.session.get(pending_inschrijving_session_key(evenement))
    inschrijving = None
    if inschrijving_pk:
        inschrijving = StandhouderInschrijving.objects.filter(
            pk=inschrijving_pk,
            evenement=evenement,
        ).select_related("payment").first()

    if inschrijving and inschrijving.payment_id:
        payment = inschrijving.payment
        if payment.mollie_id:
            try:
                mollie_payment = MollieClient().client.payments.get(payment.mollie_id)
                mollie_status = mollie_payment.get("status", "").lower()
                valid_statuses = [choice[0] for choice in PaymentStatus.CHOICES]
                if mollie_status in valid_statuses and mollie_status != payment.status:
                    payment.status = mollie_status
                    payment.save()
                    verwerk_standhouder_betaling(payment, mollie_status)
                    inschrijving.refresh_from_db()
                    payment.refresh_from_db()
            except Exception:
                pass

        context["inschrijving"] = inschrijving
        context["payment_status"] = payment.status
        context["online_betaling"] = True
    else:
        context["email_sent"] = request.session.pop(email_sent_session_key(evenement), None)
        context["voorlopig"] = request.session.pop(voorlopig_session_key(evenement), False)
        context["online_betaling"] = False

    return TemplateResponse(request, "pokemon/pages/standhouder/success.html", context)


def algemene_voorwaarden(request):
    return TemplateResponse(request, 'pokemon/pages/algemene_voorwaarden.html', get_default_context())


def privacybeleid(request):
    return TemplateResponse(request, 'pokemon/pages/privacybeleid.html', get_default_context())


def disclaimer(request):
    return TemplateResponse(request, 'pokemon/pages/disclaimer.html', get_default_context())


def faq(request):
    return TemplateResponse(request, 'pokemon/pages/faq.html', get_default_context())


def huisreglement(request):
    return TemplateResponse(request, 'pokemon/pages/huisreglement.html', get_default_context())


@csrf_exempt
def mollie_webhook(request):
    if request.method == 'POST':
        if 'id' not in request.POST:
            return HttpResponseBadRequest()

        mollie_payment_id = request.POST['id']
        mollie_payment = MollieClient().client.payments.get(mollie_payment_id)
        payment = get_object_or_404(Payment, mollie_id=mollie_payment_id)

        # check if it is refund
        try:
            has_links = mollie_payment.get('_links', False)
            if has_links and has_links.get('refunds', False):
                mollie_status = 'refunded'
            else:
                mollie_status = mollie_payment.get("status", "").lower()
        except:
            mollie_status = mollie_payment.get("status", "").lower()

        # Validate status against defined choices
        valid_statuses = [choice[0] for choice in PaymentStatus.CHOICES]
        if mollie_status in valid_statuses:
            payment.status = mollie_status
            payment.save()
            verwerk_standhouder_betaling(payment, mollie_status)
            verwerk_ticket_betaling(payment, mollie_status)

        return HttpResponse(status=200)

    return HttpResponseNotFound("Invalid request method")


@staff_member_required
def scanner(request):
    return TemplateResponse(request, "pokemon/admin/scanner.html")


@csrf_exempt
@staff_member_required
def set_attendance(request):

    print(f"User: {request.user}, Authenticated: {request.user.is_authenticated}, Staff: {request.user.is_staff}")

    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'message': "Gebruiker is niet aangemeld!"}, status=403)

    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': "Onbekend verzoek."}, status=400)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': "QR-code niet herkend. Probeer opnieuw te scannen."}, status=400)

    try:
        result = check_in_participant(data.get('participant_id'), data.get('seed'))
    except AttendanceError as exc:
        return JsonResponse({'success': False, 'message': exc.message}, status=exc.status)

    return JsonResponse({'success': True, 'message': result['message']})


@csrf_exempt
def gate_check_in(request):
    """Device-API-key authenticated check-in for the Raspberry Pi gate scanner."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': "Onbekend verzoek."}, status=400)

    raw_key = request.headers.get('X-Gate-Api-Key', '')
    device = GateDevice.authenticate(raw_key)
    if device is None:
        return JsonResponse({'success': False, 'message': "API-sleutel geweigerd. Controleer de instellingen."}, status=401)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': "QR-code niet herkend. Probeer opnieuw te scannen."}, status=400)

    try:
        result = check_in_participant(
            data.get('participant_id'),
            data.get('seed'),
            event_id=data.get('event_id'),
            ticket_id=data.get('ticket_id'),
        )
    except AttendanceError as exc:
        return JsonResponse({'success': False, 'message': exc.message}, status=exc.status)

    device.touch_last_used()
    return JsonResponse(result)


###### ERROR HANDLERS #######

def error_404(request, exception=None):
    context = get_default_context()
    return TemplateResponse(request, 'pokemon/errors/404.html', context, status=404)

def error_500(request, exception=None):
    context = get_default_context()
    return TemplateResponse(request, 'pokemon/errors/500.html', context, status=500)

## HELPERS ##

def get_default_context():
    now = timezone.now()
    highlighted_event = Evenement.objects.filter(toon_op_site=True, highlight_event=True).first()
    if not highlighted_event:
        highlighted_event = Evenement.objects.filter(toon_op_site=True, start_datum__gt=now).order_by('start_datum').first()
    if not highlighted_event:
        highlighted_event = Evenement.objects.filter(toon_op_site=True).first()

    return {
        'sponsors': Sponsor.objects.all().order_by('-volgorde_footer') or [],
        "evenement": highlighted_event
    }

