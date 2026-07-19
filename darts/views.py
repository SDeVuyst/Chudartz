import json
from decimal import Decimal
from email.utils import formataddr

from django.conf import settings
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.forms import ValidationError
from django.db.models import Case, IntegerField, Prefetch, Q, Value, When
from django.http import (BadHeaderError, HttpResponse, HttpResponseBadRequest,
                         HttpResponseNotFound, JsonResponse)
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_exempt

from darts.kamp_wizard import (
    clear_wizard_data,
    get_wizard_data,
    heeft_kindgegevens,
    kamp_base_context,
    pending_payment_session_key,
    set_wizard_data,
)
from darts.payment import MollieClient
from darts.services.kamp_inschrijving import KampValidationError, finalize_checkout

from .forms import BeurtkaartForm, CodeForm, ContactForm, DartskampBetalenForm, DartskampForm
from .models import *
from .utils import helpers


def index(request):
    context = get_default_context()
    context['form'] = ContactForm()
    context['nieuws'] = Nieuws.objects.all()
    # kies random 8 fotos uit de database
    context['fotos_selectie'] = IndexFoto.objects.filter(active=True).order_by('?')[:8]
    context['fotos_dartschool'] = IndexFoto.objects.filter(active=True, category=IndexFotoCategory.DARTSCHOOL).order_by('?')[:8]
    context['fotos_dartskamp'] = IndexFoto.objects.filter(active=True, category=IndexFotoCategory.DARTSKAMP).order_by('?')[:8]
    context['fotos_andere'] = IndexFoto.objects.filter(active=True, category=IndexFotoCategory.ANDERE).order_by('?')[:8]
    return TemplateResponse(request, 'pages/index.html', context)


def trainers(request):
    context = get_default_context()
    context["trainers"] = Trainer.objects.filter(active=True).order_by('-volgorde')
    
    return TemplateResponse(request, 'pages/trainers.html', context)

def locaties(request):
    context = get_default_context()
    context['locaties'] = Locatie.objects.filter(active=True).order_by('-volgorde')
    
    return TemplateResponse(request, 'pages/locaties.html', context)

def locatie_detail(request, slug):
    context = get_default_context()
    locatie = get_object_or_404(Locatie, slug=slug)
    if locatie.active == False: return HttpResponseNotFound()

    context['locatie'] = locatie
    locatie_leagues = League.objects.filter(
        locatie=locatie,
        active=True,
    ).order_by('-jaar', '-volgorde')
    context['actuele_leagues'] = locatie_leagues.filter(historisch=False)
    context['historische_leagues'] = locatie_leagues.filter(historisch=True)
    
    return TemplateResponse(request, 'pages/locatie.html', context)


def leagues(request):
    context = get_default_context()
    actuele_leagues = League.objects.filter(
        active=True,
        historisch=False,
    ).select_related('locatie').order_by('-jaar', '-volgorde')
    historische_leagues = League.objects.filter(
        active=True,
        historisch=True,
    ).select_related('locatie').order_by('-jaar', '-volgorde')
    context['superleagues'] = actuele_leagues.filter(locatie__isnull=True)
    context['vestiging_leagues'] = actuele_leagues.filter(locatie__isnull=False)
    context['historische_superleagues'] = historische_leagues.filter(locatie__isnull=True)
    context['historische_vestiging_leagues'] = historische_leagues.filter(locatie__isnull=False)

    return TemplateResponse(request, 'pages/leagues.html', context)


def league_detail(request, slug):
    league = get_object_or_404(
        League.objects.select_related('locatie').prefetch_related(
            Prefetch('divisies', queryset=LeagueDivisie.objects.order_by('volgorde', 'id'))
        ),
        slug=slug,
        active=True,
    )
    context = get_default_context()
    context['league'] = league
    return TemplateResponse(request, 'pages/league.html', context)


def dartschool(request):
    context = get_default_context()
    context['beurtkaarten'] = Beurtkaart.objects.all()
    
    return TemplateResponse(request, 'pages/dartschool.html', context)

def dartschool_meer_info(request):
    return TemplateResponse(request, 'pages/dartschool-meer-info.html', get_default_context())

def dartschool_aanbod(request):
    return TemplateResponse(request, 'pages/dartschool-aanbod.html', get_default_context())

def dartschool_werkwijze(request):
    return TemplateResponse(request, 'pages/dartschool-werkwijze.html', get_default_context())

def gratis_proefles(request):
    context = get_default_context()
    context["vereisten"] = [
        "Vanaf 8 jaar", 
        "T.e.m. 23 jaar",
        "Actieve interesse in darts"
    ]
    context["locaties"] = Locatie.objects.filter(active=True).order_by('-volgorde')
        
    return TemplateResponse(request, 'pages/dartschool-gratis-proefles.html', context)


def reserveren_dartschool(request):
    context = get_default_context()
    context["locaties"] = Locatie.objects.filter(active=True).order_by('-volgorde')
    context["vereisten"] = "Lid zijn van de dartschool",

    return TemplateResponse(request, 'pages/dartschool-reserveren.html', context)


def beurtkaart_kopen(request):
    if request.method == 'POST':
        form = BeurtkaartForm(request.POST)
        
        if form.is_valid():
            beurtkaart = form.cleaned_data['beurtkaart']
            code = form.cleaned_data['code']

            leerling = get_object_or_404(Leerling, code=str(code))

            price = Decimal(beurtkaart.prijs.amount)

            payment = Payment.objects.create(
                first_name=leerling.voornaam,
                last_name=leerling.achternaam,
                amount=price,
                description=beurtkaart.naam
            )

            BeurtkaartBetaling.objects.create(
                beurtkaart=beurtkaart,
                betaling=payment,
                leerling=leerling
            )

            # create the mollie payment
            mollie_payment = MollieClient().create_mollie_payment(
                amount=price,
                description=beurtkaart.naam,
                redirect_url=f'https://chudartz.com/nl/dartschool/beurtenkaart-kopen/success/',
            )

            payment.mollie_id = mollie_payment.id
            payment.save()
            
            return redirect(mollie_payment.checkout_url)
        

        # form was not valid, send to error page
        context = get_default_context()
        context["success"] = False

        return TemplateResponse(request, 'pages/dartschool-beurtkaart-response.html', context)
       
    # GET request
    context = get_default_context()
    context['beurtkaarten'] = Beurtkaart.objects.all()

    return TemplateResponse(request, 'pages/dartschool-beurtkaart.html', context)


def beurtkaart_kopen_success(request):
    context = get_default_context()
    context["success"] = True

    return TemplateResponse(request, 'pages/dartschool-beurtkaart-response.html', context)


def dartschool_lidgeld(request):
     # request must always be post
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method.'})
    
    form = CodeForm(request.POST)
        
    if not form.is_valid():
        #form was not valid, send to error page
        context = get_default_context()
        context["success"] = False

        return TemplateResponse(request, 'pages/dartschool-inschrijving-response.html', context)
    
    voornaam = form.cleaned_data['voornaam']
    achternaam = form.cleaned_data['achternaam']
    email = form.cleaned_data['email']

    price = Decimal(60)

    payment = Payment.objects.create(
        first_name=voornaam,
        last_name=achternaam,
        mail=email,
        amount=price
    )

    leerling = Leerling.objects.create(
        voornaam=voornaam,
        achternaam=achternaam,
        email=email,
        payment_id = payment.pk,
    )

    # create the mollie payment
    mollie_payment = MollieClient().create_mollie_payment(
        amount=price,
        description="Lidgeld",
        redirect_url=f'https://chudartz.com/nl/dartschool/lidgeld/success',
    )

    payment.mollie_id = mollie_payment.id
    payment.save()
    
    return redirect(mollie_payment.checkout_url)


def dartschool_lidgeld_success(request):
    context = get_default_context()
    context["success"] = True

    return TemplateResponse(request, 'pages/dartschool-inschrijving-response.html', context)


def doelen(request):
    context = get_default_context()
    return TemplateResponse(request, 'pages/doelen.html', context)


def dartskampen(request):
    today = timezone.now().date()
    evenementen = Dartskamp.objects.filter(toon_op_site=True).annotate(
        is_future=Case(
            When(start_datum__gte=today, then=Value(0)),
            default=Value(1),
            output_field=IntegerField(),
        )
    ).order_by('is_future', 'start_datum')

    paginator = Paginator(evenementen, 12)

    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = get_default_context()
    context["dartskampen"] = page_obj
    context["has_future_camps"] = evenementen.filter(is_future=0).exists()
    context["has_past_camps"] = evenementen.filter(is_future=1).exists()
    context["enable_pagination"] = paginator.num_pages > 1

    return TemplateResponse(request, 'pages/dartskampen.html', context)


def dartskamp(request, slug):
    kamp = get_object_or_404(Dartskamp, slug=slug)

    if not kamp.toon_op_site:
        return HttpResponseNotFound()

    context = get_default_context()
    context["kamp"] = kamp
    context["fotos"] = kamp.fotos.all().order_by('-volgorde')

    return TemplateResponse(request, 'pages/dartskamp.html', context)


def inschrijven_dartskamp(request, slug):
    """Stap 1: kindgegevens."""
    kamp = get_object_or_404(Dartskamp, slug=slug)
    if not kamp.toon_op_site:
        return HttpResponseNotFound()

    if not kamp.enable_inschrijvingen or kamp.is_sold_out:
        return redirect('dartskamp', slug=slug)

    wizard_data = get_wizard_data(request, kamp)
    context = get_default_context()
    context.update(kamp_base_context(request, kamp, "gegevens"))

    if request.method == 'POST':
        form = DartskampForm(request.POST)
        if form.is_valid():
            wizard_data.update(form.cleaned_data)
            # PhoneNumberField returns a PhoneNumber object
            wizard_data["gsm"] = str(form.cleaned_data["gsm"])
            set_wizard_data(request, kamp, wizard_data)
            return redirect('inschrijven_dartskamp_overzicht', slug=slug)
        context["error"] = _("Controleer de ingevulde gegevens.")
    else:
        form = DartskampForm(initial=wizard_data)

    context["form"] = form
    return TemplateResponse(request, 'pages/kampen/stap1.html', context)


def inschrijven_dartskamp_overzicht(request, slug):
    """Stap 2: overzicht (nog niet betalen)."""
    kamp = get_object_or_404(Dartskamp, slug=slug)
    if not kamp.toon_op_site:
        return HttpResponseNotFound()

    wizard_data = get_wizard_data(request, kamp)
    if not heeft_kindgegevens(wizard_data):
        return redirect('inschrijven_dartskamp', slug=slug)

    if request.method == 'POST':
        return redirect('inschrijven_dartskamp_betalen', slug=slug)

    context = get_default_context()
    context.update(kamp_base_context(request, kamp, "overzicht"))
    return TemplateResponse(request, 'pages/kampen/stap2.html', context)


def inschrijven_dartskamp_betalen(request, slug):
    """Stap 3: voorwaarden + Mollie."""
    kamp = get_object_or_404(Dartskamp, slug=slug)
    if not kamp.toon_op_site:
        return HttpResponseNotFound()

    wizard_data = get_wizard_data(request, kamp)
    if not heeft_kindgegevens(wizard_data):
        return redirect('inschrijven_dartskamp', slug=slug)

    context = get_default_context()
    context.update(kamp_base_context(request, kamp, "betalen"))
    context["form"] = DartskampBetalenForm()

    if request.method == 'POST':
        form = DartskampBetalenForm(request.POST)
        context["form"] = form
        if form.is_valid():
            try:
                payment, checkout_url = finalize_checkout(request, kamp, wizard_data)
                clear_wizard_data(request, kamp)
                request.session[pending_payment_session_key(kamp)] = payment.pk
                return redirect(checkout_url)
            except KampValidationError as exc:
                context["error"] = str(exc)
        else:
            context["error"] = _("Gelieve alle voorwaarden te aanvaarden.")

    return TemplateResponse(request, 'pages/kampen/stap3.html', context)


def inschrijven_dartskamp_success(request, slug):
    kamp = get_object_or_404(Dartskamp, slug=slug)
    context = get_default_context()
    context["success"] = True
    context["kamp"] = kamp

    payment_pk = request.session.get(pending_payment_session_key(kamp))
    if payment_pk:
        payment = Payment.objects.filter(pk=payment_pk).first()
        if payment and payment.mollie_id and payment.status == PaymentStatus.OPEN:
            try:
                mollie_payment = MollieClient().client.payments.get(payment.mollie_id)
                status = mollie_payment.get("status", "").lower()
                valid_statuses = [choice[0] for choice in PaymentStatus.CHOICES]
                if status in valid_statuses and status != payment.status:
                    payment.status = status
                    payment.save()
            except Exception:
                pass
        context["payment"] = payment

    return TemplateResponse(request, 'pages/dartskamp-inschrijving-response.html', context)


def resultaten(request):
    evenementen = Dartskamp.objects.filter(toon_op_site=True).exclude(Q(resultaten__isnull=True) | Q(resultaten__exact=''))
    paginator = Paginator(evenementen, 12)

    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = get_default_context()
    context["dartskampen"] = page_obj
    context["enable_pagination"] = paginator.num_pages > 1

    return TemplateResponse(request, 'pages/resultaten.html', context)


def dartskamp_resultaat(request, slug):
    kamp = get_object_or_404(Dartskamp, slug=slug)
    if not kamp.toon_op_site:
        return HttpResponseNotFound()
    if not kamp.resultaten:
        return HttpResponseNotFound()

    context = get_default_context()
    context["kamp"] = kamp

    return TemplateResponse(request, 'pages/resultaat.html', context)


def priveles(request):
    return TemplateResponse(request, 'pages/priveles.html', get_default_context())


def workshops(request):
    return TemplateResponse(request, 'pages/teambuildings-en-workshops.html', get_default_context())


def over_ons(request):
    return TemplateResponse(request, 'pages/about.html', get_default_context())


def algemene_voorwaarden(request):
    return TemplateResponse(request, 'pages/algemene-voorwaarden.html', get_default_context())


def privacybeleid(request):
    return TemplateResponse(request, 'pages/privacybeleid.html', get_default_context())


def reglement_dartskampen(request):
    return TemplateResponse(request, 'pages/algemeen-reglement.html', get_default_context())


def disclaimer(request):
    return TemplateResponse(request, 'pages/disclaimer.html', get_default_context())


def terms_of_service(request):
    return TemplateResponse(request, 'pages/terms-of-service.html', get_default_context())


def privacy_policy(request):
    return TemplateResponse(request, 'pages/privacy-policy.html', get_default_context())


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
            formataddr(('Contact | ChudartZ', settings.EMAIL_HOST_USER)),
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

def sponsor_worden(request):
    return TemplateResponse(request, 'pages/sponsor-worden.html', get_default_context())

def sponsors(request):
    context = get_default_context()
    context['sponsors_pagina'] = Sponsor.objects.all().order_by('-volgorde_pagina')
    return TemplateResponse(request, 'pages/sponsors.html', context)

def faq(request):
    return TemplateResponse(request, 'pages/faq.html', get_default_context())

              
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

        return HttpResponse(status=200)

    return HttpResponseNotFound("Invalid request method")


@csrf_exempt
def cal_webhook(request):

    if request.method != "POST": return HttpResponseNotFound("Invalid request method")

    # check if request is authentic
    received_signature = request.headers.get('X-Cal-Signature-256')
    if not received_signature:
        return HttpResponseBadRequest("Missing signature header")
    
    payload_body = request.body.decode('utf-8')

    is_valid = helpers.verify_webhook_signature(payload_body, received_signature)

    if not is_valid: return HttpResponseBadRequest("Invalid signature. The payload is not authentic.")

    data = json.loads(request.body)

    trigger = data.get('triggerEvent')
    if trigger == "PING": return HttpResponse(status=200)
    if trigger != "BOOKING_CREATED": return HttpResponseNotFound("Invalid event trigger.")

    code: str = data.get('payload').get('responses').get('code').get('value')

    # PROEFLES code, everthing ok
    if code == "PROEFLES":
        return HttpResponse(status=200)

    # unknown code, cancel booking
    if not Leerling.objects.filter(code=code).exists():
        # stuur fraude-detectie mail
        naam = data.get('payload').get('attendees').get('name')
        send_mail(
            f'Mogelijkse fraude!',
            f"{naam} heeft geboekt met een ongeldige code.\nGelieve deze boeking zo snel mogelijk te annuleren.",
            formataddr(('Fraudedetectie | ChudartZ', settings.EMAIL_HOST_USER)),
            [settings.EMAIL_HOST_USER],
            fail_silently=False,
        )
        return HttpResponse(status=406)
    
    # custom code, decrement remaining uses
    l = get_object_or_404(Leerling, code=code)
    try:
        l.decrement_beurten()
    
    # user has no uses left
    except ValidationError as e:
        naam = data.get('payload').get('attendees').get('name')
        send_mail(
            f'Mogelijkse fraude!',
            f'{naam} heeft geboekt met een lege beurtkaart.\nDit is enkel mogelijk door niet via de site te boeken.\nGelieve zo snel mogelijk contact op te nemen met deze persoon en deze afspraak af te zeggen.',
            formataddr(('Fraudedetectie | ChudartZ', settings.EMAIL_HOST_USER)),
            [settings.EMAIL_HOST_USER],
            fail_silently=False,
        )

        return HttpResponse(status=406)

    return HttpResponse(status=200)


def leerling(request, code):
    if request.method != 'GET': return HttpResponseNotFound("Invalid request method")

    # recaptcha check
    if not helpers.verify_recaptcha(request.GET.get('recaptcha_token')):
        return JsonResponse({
            'success': False,
            'error': "reCAPTCHA gefaald. Gelieve opnieuw te proberen."
        })

    
    l = get_object_or_404(Leerling, code=str(code))

    if l.resterende_beurten < 1:
        return JsonResponse({
            'success': False,
            'error': "U heeft geen resterernde beurten meer. Gelieve een nieuwe beurtkaart te kopen."
        })

    return JsonResponse({
        'success': True,
        'voornaam': l.voornaam,
        'achternaam': l.achternaam,
        'email': l.email,
        'resterende_beurten': l.resterende_beurten,
    })


def code_bestaat(request, code):
    if request.method != 'GET': return HttpResponseNotFound("Invalid request method")

    # recaptcha check
    if not helpers.verify_recaptcha(request.GET.get('recaptcha_token')):
        return JsonResponse({
            'success': False,
            'error': "reCAPTCHA gefaald. Gelieve opnieuw te proberen."
        })

    return JsonResponse({
        'success': Leerling.objects.filter(code=code).exists(),
        'error': "Foutieve code."
    })


###### ERROR HANDLERS #######

def error_404(request, exception=None):
    context = get_default_context()
    return TemplateResponse(request, 'errors/404.html', context, status=404)

def error_500(request, exception=None):
    context = get_default_context()
    return TemplateResponse(request, 'errors/500.html', context, status=500)


# HELPER
def get_default_context():
    return {
        'sponsors': Sponsor.objects.all().order_by('-volgorde_footer') or [],
        'dartskamp_groepen': DartskampHeaderGroep.objects.filter(active=True).order_by('-volgorde'),
    }