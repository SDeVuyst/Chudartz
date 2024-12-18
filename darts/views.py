from decimal import Decimal
from email.utils import formataddr
import json
import os
from django.conf import settings
from django.http import BadHeaderError, HttpResponse, HttpResponseBadRequest, HttpResponseNotFound, JsonResponse
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse

from darts.payment import MollieClient
from .forms import ContactForm, ToernooiForm, BeurtkaartForm, CodeForm
from .models import *
from .utils import helpers


def index(request):
    context = get_default_context()
    context['form'] = ContactForm()
    context['nieuws'] = Nieuws.objects.all()
    
    return TemplateResponse(request, 'pages/index.html', context)


def dartschool(request):
    context = get_default_context()
    context['beurtkaarten'] = Beurtkaart.objects.all()
    
    return TemplateResponse(request, 'pages/dartschool.html', context)

def dartschool_meer_info(request):
    return TemplateResponse(request, 'pages/dartschool-meer-info.html', get_default_context())

def dartschool_werkwijze(request):
    return TemplateResponse(request, 'pages/dartschool-werkwijze.html', get_default_context())

def gratis_proefles(request):
    context = get_default_context()
    context["vereisten"] = [
        "Vanaf 10 jaar", 
        "Jonger dan 10 jaar kan, mits aanleg voor darts",
        "Maximum 20 jaar oud", 
        "Actieve interesse in darts"
    ]
        
    return TemplateResponse(request, 'pages/dartschool-gratis-proefles.html', context)


def reserveren_dartschool(request):
    context = get_default_context()
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

    price = Decimal(50)

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


def toernooien(request):
    evenementen = Toernooi.objects.filter(toon_op_site=True).order_by('start_datum')
    paginator = Paginator(evenementen, 12)

    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = get_default_context()
    context["toernooien"] = page_obj
    context["enable_pagination"] = paginator.num_pages > 1

    return TemplateResponse(request, 'pages/toernooien.html', context)


def toernooi(request, slug):
    evenement = get_object_or_404(Toernooi, slug=slug)

    # event must be public 
    if not evenement.toon_op_site: return HttpResponseNotFound()

    context = get_default_context()
    context["toernooi"] = evenement

    return TemplateResponse(request, 'pages/toernooi.html', context)


def inschrijven_toernooi(request, slug):
    evenement = get_object_or_404(Toernooi, slug=slug)

    if request.method == 'POST':
        form = ToernooiForm(request.POST)
        
        if not form.is_valid():
            print(form.errors)

            # form was not valid, send to error page
            context = get_default_context()
            context["success"] = False
            context["toernooi"] = get_object_or_404(Toernooi, slug=slug)

            return TemplateResponse(request, 'pages/toernooi-inschrijving-response.html', context)
        
        voornaam = form.cleaned_data['voornaam']
        achternaam = form.cleaned_data['achternaam']
        geboortejaar = form.cleaned_data['geboortejaar']
        email = form.cleaned_data['email']
        straatnaam = form.cleaned_data['straatnaam']
        nummer = form.cleaned_data['nummer']
        postcode = form.cleaned_data['postcode']
        stad = form.cleaned_data['stad']
        gsm = form.cleaned_data['gsm']
        ticket_id = form.cleaned_data['ticket']

        price = Decimal(get_object_or_404(Ticket, pk=ticket_id).price.amount)

        payment = Payment.objects.create(
            first_name=voornaam,
            last_name=achternaam,
            mail=email,
            amount=price
        )

        Participant.objects.create(
            voornaam=voornaam,
            achternaam=achternaam,
            geboortejaar=geboortejaar,
            email=email,
            straatnaam=straatnaam,
            nummer=nummer,
            postcode=postcode,
            stad=stad,
            gsm=gsm,

            payment_id = payment.pk,
            ticket=get_object_or_404(Ticket, pk=ticket_id),
        )

        # create the mollie payment
        mollie_payment = MollieClient().create_mollie_payment(
            amount=price,
            description="Toernooi ChudartZ",
            redirect_url=f'https://chudartz.com/nl/toernooien/{slug}/inschrijven/success',
        )

        payment.mollie_id = mollie_payment.id
        payment.save()
        
        return redirect(mollie_payment.checkout_url)
        
    
    # GET request
    if not evenement.toon_op_site: return HttpResponseNotFound()
    tickets = Ticket.objects.filter(event=evenement)
    

    context = get_default_context()
    context["toernooi"] = evenement
    context["tickets"] = tickets
    context['skill_level_choices'] = SkillLevel.CHOICES
    context['form'] = ToernooiForm()

    return TemplateResponse(request, 'pages/toernooi-inschrijving.html', context)


def inschrijven_toernooi_success(request, slug):
    context = get_default_context()
    context["success"] = True
    context["toernooi"] = get_object_or_404(Toernooi, slug=slug)

    return TemplateResponse(request, 'pages/toernooi-inschrijving-response.html', context)


def resultaten(request):
    evenementen = Toernooi.objects.filter(toon_op_site=True).exclude(Q(resultaten__isnull=True) | Q(resultaten__exact=''))
    paginator = Paginator(evenementen, 12)

    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = get_default_context()
    context["toernooien"] = page_obj
    context["enable_pagination"] = paginator.num_pages > 1

    return TemplateResponse(request, 'pages/resultaten.html', context)


def toernooi_resultaat(request, slug):
    evenement = get_object_or_404(Toernooi, slug=slug)
    if not evenement.toon_op_site: return HttpResponseNotFound()
    if not evenement.resultaten: return HttpResponseNotFound()

    context = get_default_context()
    context["toernooi"] = evenement

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


def reglement_toernooien(request):
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
    subject = form.cleaned_data['subject']
    message = form.cleaned_data['message']

    try:
        # Send mail to admins
        send_mail(
            f'Contact Form - {subject}',
            f'Name: {name}\nEmail: {email}\nMessage: {message}',
            formataddr(('Contact | ChudartZ', settings.EMAIL_HOST_USER)),
            [settings.EMAIL_HOST_USER],
            fail_silently=False,
        )

        # Send confirmation mail to user
        send_mail(
            'Chudartz | Bericht Ontvangen',
            "Beste\n\nBedankt voor het invullen van het contactformulier. Wij hebben uw bericht in goede orde ontvangen en zullen zo snel mogelijk contact met u opnemen.\n\nMet vriendelijke groeten\n\nTeam ChudartZ",
            formataddr(('Contact | ChudartZ', settings.EMAIL_HOST_USER)),
            [email],
            fail_silently=False
        )

        return JsonResponse({'success': True})
    
    except BadHeaderError:
        return JsonResponse({'success': False, 'error': 'Invalid header found.'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


def sponsors(request):
    return TemplateResponse(request, 'pages/sponsors.html', get_default_context())

def faq(request):
    return TemplateResponse(request, 'pages/faq.html', get_default_context())

              
@staff_member_required
def scanner(request):
    return TemplateResponse(request, "admin/scanner.html")


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
            if mollie_payment.refunds.get("count", 0) > 0:
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


@csrf_exempt
@staff_member_required
def set_attendance(request):

    if request.method == 'POST':

        # get data from request
        data = json.loads(request.body)
        participant_id = data.get('participant_id')
        seed = data.get('seed')

        # validation
        if participant_id is None or seed is None:
            return JsonResponse({'success': False, 'message': "QR code not recognised!"}, status=400)
        
        participant = get_object_or_404(Participant, pk=participant_id)

        # participant hasnt paid
        if participant.payment.status != PaymentStatus.PAID:
            return JsonResponse({'success': False, 'message': "Fraud Detected!"}, status=400)

        # check if seed is correct
        if seed != participant.random_seed:
            return JsonResponse({'success': False, 'message': "Fraud Detected!"}, status=400)
        
        # validation
        if participant.attended:
            return JsonResponse({'success': False, 'message': "Participant already attended!"}, status=400)
        

        participant.attended = True
        participant.save()

        return JsonResponse({'success': True, 'message': str(participant.ticket)})
    
    return JsonResponse({'success': False, 'message': "unknown request."}, status=400)


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


# HELPER
def get_default_context():
    return {
        'sponsors': Sponsor.objects.all(),
        'toernooi_groepen': ToernooiHeaderGroep.objects.filter(active=True).order_by('-volgorde'),
    }