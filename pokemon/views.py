import json
import logging
import random
from decimal import Decimal
from email.utils import formataddr

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.db.models import Case, DateTimeField, F, IntegerField, Value, When
from django.http import (BadHeaderError, HttpResponse, HttpResponseBadRequest,
                         HttpResponseNotFound, JsonResponse)
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.template.response import TemplateResponse
from django.utils import timezone
from django.utils.text import capfirst
from django.views.decorators.csrf import csrf_exempt

from darts.templatetags.dutch_date import dutch_datetime, dutch_time
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
    IndexFoto,
    IndexFotoCategory,
    Participant,
    Partner,
    Payment,
    PaymentStatus,
    Sponsor,
    Ticket,
    StandhouderInschrijving,
)
from pokemon.team import groepen_voor_site
from pokemon.services.attendance import (
    AttendanceError,
    check_in_participant,
    check_in_raw_qr,
    lookup_raw_qr,
)
from pokemon.services import wallet
from pokemon.services import wallet_apple as wallet_apple_passes
from pokemon.services.calendar import build_ics, google_calendar_url
from pokemon.services.evenement_seo import build_event_jsonld
from pokemon.services.gate import log_gate_scan
from pokemon.payment import MollieClient
from pokemon.services.standhouder import (
    StandhouderValidationError,
    finalize_inschrijving,
    validate_standhouder_kortingscode,
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
    clear_standhouder_kortingscode,
    email_sent_session_key,
    get_applicable_vragen,
    get_concept_inschrijving,
    get_or_create_concept_inschrijving,
    get_standhouder_kortingscode,
    get_zaalplan,
    heeft_gegevens,
    pending_inschrijving_session_key,
    save_tafel_keuzes,
    save_vraag_antwoorden,
    serialize_zaalplan_grid,
    set_standhouder_kortingscode,
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
logger = logging.getLogger(__name__)


def homepage_evenement_selectie(now=None, exclude=None):
    """Last finished visible event, plus the next two that have not ended yet.

    `exclude` is the spotlight event, so the cards do not repeat it.
    """
    if now is None:
        now = timezone.now()
    zichtbaar = Evenement.objects.filter(toon_op_site=True)
    if exclude is not None:
        zichtbaar = zichtbaar.exclude(pk=exclude.pk)
    voorbij = (
        zichtbaar.filter(einde_datum__lt=now)
        .order_by("-einde_datum", "-pk")
        .first()
    )
    aankomend = list(
        zichtbaar.filter(einde_datum__gte=now).order_by("start_datum", "pk")[:2]
    )
    return voorbij, aankomend


def index(request):
    context = get_default_context()
    context.update(get_index_foto_context())
    voorbij, aankomend = homepage_evenement_selectie(exclude=context.get("evenement"))
    context["homepage_voorbij_evenement"] = voorbij
    context["homepage_aankomende_evenementen"] = aankomend
    return TemplateResponse(request, 'pokemon/pages/index.html', context)

def over_ons(request):
    return TemplateResponse(request, 'pokemon/pages/about.html', get_default_context())


def ons_team(request):
    groepen = groepen_voor_site()
    context = get_default_context()
    context["groepen"] = groepen
    context["team_totaal"] = f"{sum(len(groep['leden']) for groep in groepen):03d}"
    return TemplateResponse(request, 'pokemon/pages/team.html', context)


def sponsors(request):
    context = get_default_context()
    context['sponsors_pagina'] = Sponsor.objects.all().order_by('-volgorde_pagina')
    return TemplateResponse(request, 'pokemon/pages/sponsors.html', context)


def partners(request):
    context = get_default_context()
    context['partners'] = Partner.objects.filter(toon_op_pagina=True).order_by('volgorde', 'name')
    return TemplateResponse(request, 'pokemon/pages/partners.html', context)


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


def _evenement_datum_label(evenement):
    """Same date line as the event card."""
    start = capfirst(str(dutch_datetime(evenement.start_datum)))
    if evenement.is_same_day:
        return f"{start} - {dutch_time(evenement.einde_datum)}"
    einde = capfirst(str(dutch_datetime(evenement.einde_datum)))
    return f"{start} - {einde}"


def _evenement_kaart_pins():
    """Pins for published events that have not ended yet."""
    pins = []
    evenementen = Evenement.objects.filter(
        toon_op_site=True,
        latitude__isnull=False,
        longitude__isnull=False,
        einde_datum__gte=timezone.now(),
    ).order_by("start_datum")
    for evenement in evenementen:
        pins.append({
            "titel": evenement.titel,
            "locatie": evenement.locatie_kort,
            "datum": _evenement_datum_label(evenement),
            "lat": float(evenement.latitude),
            "lng": float(evenement.longitude),
            "url": reverse("evenement", kwargs={"slug": evenement.slug}),
        })
    return pins


def evenementen(request):
    now = timezone.now()
    # Eerst de aankomende en lopende evenementen (dichtste startdatum eerst),
    # daarna de voorbije (recentste eerst). De sortering gebeurt in de database
    # zodat de volgorde ook over meerdere paginas correct blijft.
    evenementen_qs = Evenement.objects.filter(toon_op_site=True).annotate(
        is_voorbij=Case(
            When(einde_datum__lt=now, then=Value(1)),
            default=Value(0),
            output_field=IntegerField(),
        ),
        aankomend_datum=Case(
            When(einde_datum__gte=now, then=F("start_datum")),
            output_field=DateTimeField(),
        ),
        voorbij_datum=Case(
            When(einde_datum__lt=now, then=F("start_datum")),
            output_field=DateTimeField(),
        ),
    ).order_by(
        "is_voorbij",
        "aankomend_datum",
        F("voorbij_datum").desc(nulls_last=True),
        "volgorde",
        "pk",
    )

    paginator = Paginator(evenementen_qs, 12)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)
    page_events = list(page_obj)

    context = get_default_context()
    context["evenementen"] = page_obj
    context["aankomende_evenementen"] = [e for e in page_events if not e.is_voorbij]
    context["voorbije_evenementen"] = [e for e in page_events if e.is_voorbij]
    context["enable_pagination"] = paginator.num_pages > 1
    context["map_pins"] = _evenement_kaart_pins()

    return TemplateResponse(request, "pokemon/pages/evenementen.html", context)


def _get_gerelateerde_evenementen(evenement, limit=3):
    today = timezone.now().date()
    return Evenement.objects.filter(toon_op_site=True).exclude(pk=evenement.pk).annotate(
        is_past=Case(
            When(start_datum__date__lt=today, then=Value(1)),
            default=Value(0),
            output_field=IntegerField(),
        ),
    ).order_by(
        'is_past',
        'volgorde',
        Case(
            When(start_datum__date__gte=today, then=F('start_datum')),
            output_field=DateTimeField(),
        ),
        F('start_datum').desc(),
    )[:limit]


def evenement(request, slug):
    evenement = get_object_or_404(Evenement, slug=slug)

    if not evenement.toon_op_site:
        return HttpResponseNotFound()

    aanbod = list(
        evenement.aanbod_links
        .select_related("item")
        .filter(item__actief=True)
        .order_by("volgorde", "pk")
    )

    tickets = list(Ticket.objects.filter(event=evenement).order_by("pk"))
    vanaf_gratis, prijs_vanaf = _ticket_prijs_vanaf(tickets)
    share_url = request.build_absolute_uri(reverse("evenement", kwargs={"slug": evenement.slug}))
    og_image_url = request.build_absolute_uri(evenement.afbeelding.url) if evenement.afbeelding else None
    deur_tickets = [ticket for ticket in tickets if ticket.enkel_inkom]
    fotos = list(EvenementFoto.objects.filter(evenement=evenement).order_by("-volgorde"))
    partners = list(evenement.partners.all())
    gerelateerde_evenementen = _get_gerelateerde_evenementen(evenement)

    context = {
        "evenement": evenement,
        "fotos": fotos,
        "tickets": tickets,
        "online_tickets": [ticket for ticket in tickets if not ticket.enkel_inkom],
        "deur_tickets": deur_tickets,
        "deur_tickets_gratis": all(ticket.is_gratis for ticket in deur_tickets),
        "partners": partners,
        'sponsors': Sponsor.objects.all().order_by('-volgorde_footer') or [],
        "gerelateerde_evenementen": gerelateerde_evenementen,
        "achtergrond": _sectie_achtergronden(
            standhouder=evenement.standhouder_inschrijving_mogelijk,
            fotos=bool(fotos),
            partners=bool(partners),
            andere_evenementen=bool(gerelateerde_evenementen),
        ),
        "tickets_kopen_mogelijk": evenement.tickets_kopen_mogelijk,
        "standhouder_uitverkocht": (
            evenement.standhouder_inschrijving_mogelijk and evenement.standhouder_tafels_uitverkocht
        ),
        "aanbod": aanbod,
        "vanaf_gratis": vanaf_gratis,
        "prijs_vanaf": prijs_vanaf,
        "share_url": share_url,
        "og_image_url": og_image_url,
        "agenda_google_url": google_calendar_url(evenement),
        "event_jsonld": build_event_jsonld(evenement, tickets, request),
    }
    return TemplateResponse(request, 'pokemon/pages/evenement.html', context)


def _sectie_achtergronden(**secties):
    """Wissel wit en licht af over de zichtbare secties na de (donkere) CTA, zoals op de homepage."""
    achtergronden = {}
    licht = False
    for naam, zichtbaar in secties.items():
        if zichtbaar:
            achtergronden[naam] = "light-background" if licht else ""
            licht = not licht
    return achtergronden


def _ticket_prijs_vanaf(tickets):
    """Return (vanaf_gratis, laagste prijs) over de tickets die bezoekers kunnen krijgen."""
    beschikbaar = [ticket for ticket in tickets if not ticket.disable_ticket]
    if not beschikbaar:
        return False, None
    if any(ticket.is_gratis for ticket in beschikbaar):
        return True, None
    return False, min(ticket.price for ticket in beschikbaar)


def evenement_agenda(request, slug):
    evenement = get_object_or_404(Evenement, slug=slug)
    if not evenement.toon_op_site:
        return HttpResponseNotFound()

    response = HttpResponse(build_ics(evenement), content_type="text/calendar; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{evenement.slug}.ics"'
    return response


def wallet_apple(request, token):
    config = wallet.apple_config()
    participants = wallet.participants_for_apple_token(token)
    if config is None or not participants:
        return HttpResponseNotFound()

    if len(participants) == 1:
        content = wallet_apple_passes.build_pkpass(participants[0], config)
        content_type = wallet_apple_passes.PKPASS_CONTENT_TYPE
        filename = f"ticket-{participants[0].pk}.pkpass"
    else:
        content = wallet_apple_passes.build_pkpasses(participants, config)
        content_type = wallet_apple_passes.PKPASSES_CONTENT_TYPE
        filename = "tickets.pkpasses"

    response = HttpResponse(content, content_type=content_type)
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["Cache-Control"] = "no-store"
    return response


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

    if not evenement.tickets_kopen_mogelijk:
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

    if not evenement.standhouder_inschrijving_mogelijk:
        return redirect("evenement", slug=slug)

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

    if not evenement.standhouder_inschrijving_mogelijk:
        return redirect("evenement", slug=slug)

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
        from pokemon.forms import deserialize_vraag_antwoord_initial
        for antwoord in inschrijving.antwoorden.select_related("vraag"):
            field_name = f"vraag_{antwoord.vraag_id}"
            initial[field_name] = deserialize_vraag_antwoord_initial(
                antwoord.vraag, antwoord.antwoord
            )
        context["form"] = VragenForm(initial=initial)

    context["vragen"] = vragen
    return TemplateResponse(request, "pokemon/pages/standhouder/stap3.html", context)


def standhouder_overzicht(request, slug):
    evenement = _get_standhouder_evenement(slug)
    if not evenement:
        return HttpResponseNotFound()

    if not evenement.standhouder_inschrijving_mogelijk:
        return redirect("evenement", slug=slug)

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

    try:
        subtotaal = inschrijving.bereken_totaal()
    except Exception:
        logger.exception(
            "Standhouder overzicht prijsberekening mislukt (inschrijving=%s, evenement=%s)",
            inschrijving.pk,
            evenement.slug,
        )
        raise

    kortingscode_obj = None
    korting_bedrag = Decimal("0")
    code = get_standhouder_kortingscode(request, evenement)
    if code:
        try:
            kortingscode_obj, korting_bedrag = validate_standhouder_kortingscode(
                code, evenement, subtotaal
            )
        except StandhouderValidationError:
            clear_standhouder_kortingscode(request, evenement)
            code = ""

    try:
        regels, totaal = build_prijsopbouw(
            inschrijving, kortingscode_obj, korting_bedrag
        )
    except Exception:
        logger.exception(
            "Standhouder overzicht prijsopbouw mislukt (inschrijving=%s, evenement=%s)",
            inschrijving.pk,
            evenement.slug,
        )
        raise

    context = standhouder_base_context(request, evenement, "overzicht")
    context["prijsopbouw"] = regels
    context["totaal"] = totaal
    context["kortingscode"] = code
    context["korting_bedrag"] = korting_bedrag
    context["antwoorden"] = inschrijving.antwoorden.select_related("vraag").order_by("vraag__volgorde")
    context["online_betaling"] = evenement.standhouder_betaling_verplicht

    if request.method == "POST":
        if not evenement.standhouder_inschrijving_mogelijk:
            context["error"] = "Standhouder inschrijvingen gesloten."
            return TemplateResponse(request, "pokemon/pages/standhouder/error.html", context)

        if "apply_kortingscode" in request.POST:
            code_input = request.POST.get("kortingscode", "").strip()
            if code_input:
                try:
                    validate_standhouder_kortingscode(code_input, evenement, subtotaal)
                    set_standhouder_kortingscode(request, evenement, code_input)
                except StandhouderValidationError as exc:
                    context["error"] = str(exc)
                    context["kortingscode"] = code_input
                    return TemplateResponse(
                        request, "pokemon/pages/standhouder/stap4.html", context
                    )
            else:
                clear_standhouder_kortingscode(request, evenement)
            return redirect("standhouder_overzicht", slug=slug)

        form = StandhouderOverzichtForm(request.POST)
        if not form.is_valid():
            context["error"] = "Gelieve alle voorwaarden te aanvaarden."
            return TemplateResponse(request, "pokemon/pages/standhouder/stap4.html", context)

        if not helpers.verify_recaptcha(request.POST.get("recaptcha_token")):
            context["error"] = "reCAPTCHA gefaald. Gelieve opnieuw te proberen."
            return TemplateResponse(request, "pokemon/pages/standhouder/stap4.html", context)

        try:
            result = finalize_inschrijving(
                inschrijving, request, kortingscode_str=code
            )
            clear_concept_inschrijving(request, evenement)
            clear_standhouder_kortingscode(request, evenement)
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


@staff_member_required
def manual_check(request):
    """Staff QR lookup: resolve participant without marking attendance."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': "Onbekend verzoek."}, status=400)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse(
            {'success': False, 'message': "QR-code niet herkend. Probeer opnieuw te scannen."},
            status=400,
        )

    raw = data.get('raw')
    if raw is None or str(raw).strip() == '':
        return JsonResponse(
            {'success': False, 'message': "QR-code niet herkend. Probeer opnieuw te scannen."},
            status=400,
        )

    try:
        result = lookup_raw_qr(str(raw))
    except AttendanceError as exc:
        return JsonResponse({'success': False, 'message': exc.message}, status=exc.status)

    for warning in result['warnings']:
        messages.warning(request, warning)

    return JsonResponse({
        'success': True,
        'redirect_url': result['admin_url'],
        'warnings': result['warnings'],
    })


@staff_member_required
def scan_ticket(request):
    """Staff USB-wedge check-in: mark attendance like the gate, without redirecting."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': "Onbekend verzoek."}, status=400)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse(
            {'success': False, 'message': "QR-code niet herkend. Probeer opnieuw te scannen."},
            status=400,
        )

    raw = data.get('raw')
    if raw is None or str(raw).strip() == '':
        return JsonResponse(
            {'success': False, 'message': "QR-code niet herkend. Probeer opnieuw te scannen."},
            status=400,
        )

    try:
        result = check_in_raw_qr(str(raw))
    except AttendanceError as exc:
        payload = {'success': False, 'message': exc.message}
        if exc.admin_url:
            payload['admin_url'] = exc.admin_url
            payload['participant_id'] = exc.participant_id
        return JsonResponse(payload, status=exc.status)

    return JsonResponse(result)


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

    participant_id = data.get('participant_id')
    try:
        result = check_in_participant(
            participant_id,
            data.get('seed'),
            event_id=data.get('event_id'),
            ticket_id=data.get('ticket_id'),
        )
    except AttendanceError as exc:
        log_gate_scan(device, participant_id, False, exc.message)
        return JsonResponse({'success': False, 'message': exc.message}, status=exc.status)

    log_gate_scan(device, participant_id, True, result['message'])
    device.touch_last_used()
    return JsonResponse(result)


@csrf_exempt
def gate_heartbeat(request):
    """Periodic status ping from a gate scanner, used for live admin monitoring."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': "Onbekend verzoek."}, status=400)

    raw_key = request.headers.get('X-Gate-Api-Key', '')
    device = GateDevice.authenticate(raw_key)
    if device is None:
        return JsonResponse({'success': False, 'message': "API-sleutel geweigerd. Controleer de instellingen."}, status=401)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        data = {}

    config = data.get('config')
    device.register_heartbeat(
        data.get('status', ''),
        config if isinstance(config, dict) else None,
    )
    payload = {'success': True}
    if update := device.config_update_payload():
        payload['config_update'] = update
    return JsonResponse(payload)


###### ERROR HANDLERS #######

ERROR_GIFS_404_500 = [
    "https://media.tenor.com/YrirqcgMBiUAAAAC/one-piece.gif",  # Log Pose
    "https://media1.tenor.com/m/jJDPprSAqEUAAAAC/pout.gif", # Pikachu
    "https://media1.tenor.com/m/o97_jXyjLV4AAAAC/guts-berserk-guts.gif", # Guts
    "https://gifdb.com/images/high/thorfinn-wind-blows-hair-lmgpj4ls860638wa.gif", # thorfinn
    "https://media4.giphy.com/media/v1.Y2lkPTc5MGI3NjExeDR5NXI2dGc3MG85ZjVtNXJ3OWI4ZHRraGRuMjU2ZHV6MjBwaHNqayZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/40z9hF4Yerwh0O2pb1/giphy.gif", # gol d roger
    "https://media2.giphy.com/media/v1.Y2lkPTc5MGI3NjExaHZpbTJ1cnVpbHExeXI3aGgwN213dm1qYTM1Zmx0MWhyY2tud2U4OSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/a6XLRYrDJvIhk4lSyd/giphy.gif", # luffy question
    "https://media.tenor.com/oGQ5QYfUW94AAAAC/one-piece-luffy.gif",  # Luffy stare / point
    
]

ERROR_GIFS_401_403 = [
    "https://media.tenor.com/3odQw0NS2ZIAAAAC/one-piece-op.gif",  # Luffy stare / point
    "https://media1.tenor.com/m/uIN4bqO3iTYAAAAd/charmander-mad-mander.gif", # Charmander mad

]

ERROR_COPY = {
    401: {
        "error_title": "Niet geautoriseerd",
        "error_message": "Je bent niet gemachtigd om deze pagina te bekijken.",
    },
    403: {
        "error_title": "Geen toegang",
        "error_message": "Je hebt geen toegang tot deze pagina.",
    },
    404: {
        "error_title": "Pagina niet gevonden",
        "error_message": "De pagina die je zoekt bestaat niet of is verplaatst.",
    },
    500: {
        "error_title": "Er is iets misgegaan",
        "error_message": "Er ging iets mis aan onze kant. Probeer het later opnieuw.",
    },
}


def _error_context(status, gif_list):
    try:
        context = get_default_context()
    except Exception:
        context = {}
    context["error_code"] = status
    context["error_gif"] = random.choice(gif_list)
    context.update(ERROR_COPY[status])
    return context


def _render_error(request, status, gif_list):
    return TemplateResponse(
        request,
        "pokemon/errors/error.html",
        _error_context(status, gif_list),
        status=status,
    )


def error_401(request, exception=None):
    return _render_error(request, 401, ERROR_GIFS_401_403)


def error_403(request, exception=None):
    return _render_error(request, 403, ERROR_GIFS_401_403)


def error_404(request, exception=None):
    return _render_error(request, 404, ERROR_GIFS_404_500)


def error_500(request, exception=None):
    return _render_error(request, 500, ERROR_GIFS_404_500)

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
        "evenement": highlighted_event,
    }


def get_index_foto_context():
    return {
        "fotos_selectie": IndexFoto.objects.filter(active=True).order_by("?")[:8],
        "fotos_beurzen": IndexFoto.objects.filter(
            active=True, category=IndexFotoCategory.BEURZEN
        ).order_by("?")[:10],
        "fotos_community": IndexFoto.objects.filter(
            active=True, category=IndexFotoCategory.COMMUNITY
        ).order_by("?")[:10],
        "fotos_collectibles": IndexFoto.objects.filter(
            active=True, category=IndexFotoCategory.COLLECTIBLES
        ).order_by("?")[:10],
    }

