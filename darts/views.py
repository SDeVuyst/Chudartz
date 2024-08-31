from decimal import Decimal
from email.utils import formataddr
import json
from django.conf import settings
from django.http import BadHeaderError, HttpResponse, HttpResponseBadRequest, HttpResponseNotFound, JsonResponse
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse

from darts.payment import MollieClient
from .forms import ContactForm, TornooiForm, BeurtkaartForm
from .models import *
from .utils import helpers


def index(request):
    context = {
        'form': ContactForm(),
        'sponsors': Sponsor.objects.all()
    }
    return TemplateResponse(request, 'pages/index.html', context)


def dartschool(request):
    context = {
        'sponsors': Sponsor.objects.all(),
        'beurtkaarten': Beurtkaart.objects.all()
    }
    return TemplateResponse(request, 'pages/dartschool.html', context)


def gratis_proefles(request):
    context = {
        "vereisten": ["10 jaar oud", "blabla", "etc"],
        'sponsors': Sponsor.objects.all()
    }
    return TemplateResponse(request, 'pages/dartschool-gratis-proefles.html', context)


def reserveren_dartschool(request):
    context = {
        "vereisten": ["10 jaar oud", "blabla", "etc"],
        'sponsors': Sponsor.objects.all()
    }
    return TemplateResponse(request, 'pages/dartschool-reserveren.html', context)


def beurtkaart_kopen(request):
    if request.method == 'POST':
        form = BeurtkaartForm(request.POST)
        
        if form.is_valid():
            beurtkaart = form.cleaned_data['beurtkaart']
            code = form.cleaned_data['code']

            print(code)

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
                redirect_url=f'https://g0tgths4-80.euw.devtunnels.ms/nl/dartschool/beurtkaart-kopen/success/', # TODO
            )

            payment.mollie_id = mollie_payment.id
            payment.save()
            
            return redirect(mollie_payment.checkout_url)
        

        # form was not valid, send to error page
        context = {
            "success": False,
        }
        return TemplateResponse(request, 'pages/dartschool-beurtkaart-response.html', context)
       
    # GET request
    context = {
        'beurtkaarten': Beurtkaart.objects.all(),
        'sponsors': Sponsor.objects.all()
    }
    return TemplateResponse(request, 'pages/dartschool-beurtkaart.html', context)


def beurtkaart_kopen_success(request):
    context = {
        "success": True,
        'sponsors': Sponsor.objects.all()
    }
    return TemplateResponse(request, 'pages/dartschool-beurtkaart-response.html', context)


def tornooien(request):
    evenementen = Tornooi.objects.all()
    paginator = Paginator(evenementen, 6)

    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "tornooien": page_obj,
        "enable_pagination": paginator.num_pages > 1,
        'sponsors': Sponsor.objects.all()
    }
    return TemplateResponse(request, 'pages/tornooien.html', context)


def tornooi(request, slug):
    evenement = Tornooi.objects.get(slug=slug)
    context = {
        "tornooi": evenement,
        'sponsors': Sponsor.objects.all()
    }
    return TemplateResponse(request, 'pages/tornooi.html', context)


def inschrijven_tornooi(request, slug):
    if request.method == 'POST':
        form = TornooiForm(request.POST)
        
        if form.is_valid():
            voornaam = form.cleaned_data['voornaam']
            achternaam = form.cleaned_data['achternaam']
            email = form.cleaned_data['email']
            straatnaam = form.cleaned_data['straatnaam']
            nummer = form.cleaned_data['nummer']
            postcode = form.cleaned_data['postcode']
            stad = form.cleaned_data['stad']
            niveau = form.cleaned_data['niveau']
            ticket_id = form.cleaned_data['ticket']

            price = Decimal(Ticket.objects.get(pk=ticket_id).price.amount)

            payment = Payment.objects.create(
                first_name=voornaam,
                last_name=achternaam,
                mail=email,
                amount=price
            )

            Participant.objects.create(
                voornaam=voornaam,
                achternaam=achternaam,
                email=email,
                straatnaam=straatnaam,
                nummer=nummer,
                postcode=postcode,
                stad=stad,
                niveau=niveau,

                payment_id = payment.pk,
                ticket=Ticket.objects.get(pk=ticket_id),
            )

            # create the mollie payment
            mollie_payment = MollieClient().create_mollie_payment(
                amount=price,
                description="TESTING", # TODO
                redirect_url=f'https://g0tgths4-80.euw.devtunnels.ms/nl/tornooien/{slug}/inschrijven/success', #TODO
            )

            payment.mollie_id = mollie_payment.id
            payment.save()
            
            return redirect(mollie_payment.checkout_url)
        

        # form was not valid, send to error page
        context = {
            "success": False,
            "tornooi": Tornooi.objects.get(slug=slug),
            'sponsors': Sponsor.objects.all()
        }
        return TemplateResponse(request, 'pages/tornooi-inschrijving-response.html', context)
        
    
    # GET request
    evenement = Tornooi.objects.get(slug=slug)
    tickets = Ticket.objects.filter(event=evenement)
    
    context = {
        "tornooi": evenement,
        "tickets": tickets,
        'skill_level_choices': SkillLevel.CHOICES,
        'sponsors': Sponsor.objects.all()
    }
    return TemplateResponse(request, 'pages/tornooi-inschrijving.html', context)


def inschrijven_tornooi_success(request, slug):
    context = {
        "success": True,
        "tornooi": Tornooi.objects.get(slug=slug),
        'sponsors': Sponsor.objects.all()
    }
    return TemplateResponse(request, 'pages/tornooi-inschrijving-response.html', context)


def teambuildings_en_workshops(request):
    context = {
        'sponsors': Sponsor.objects.all()
    }
    return TemplateResponse(request, 'pages/teambuildings-en-workshops.html', context)


def over_ons(request):
    context = {
        'sponsors': Sponsor.objects.all()
    }
    return TemplateResponse(request, 'pages/about.html', context)


def algemene_voorwaarden(request):
    context = {
        'sponsors': Sponsor.objects.all()
    }
    return TemplateResponse(request, 'pages/algemene-voorwaarden.html', context)


def reglement_tornooien(request):
    context = {
        'sponsors': Sponsor.objects.all()
    }
    return TemplateResponse(request, 'pages/algemeen-reglement.html', context)


def disclaimer(request):
    context = {
        'sponsors': Sponsor.objects.all()
    }
    return TemplateResponse(request, 'pages/disclaimer.html', context)


def terms_of_service(request):
    context = {
        'sponsors': Sponsor.objects.all()
    }
    return TemplateResponse(request, 'pages/terms-of-service.html', context)


def privacy_policy(request):
    context = {
        'sponsors': Sponsor.objects.all()
    }
    return TemplateResponse(request, 'pages/privacy-policy.html', context)


def contact(request):
    # request must always be post
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method.'})

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
    context = {
        'sponsors': Sponsor.objects.all()
    }
    return TemplateResponse(request, 'pages/sponsors.html', context)

              
@staff_member_required
def scanner(request):
    return TemplateResponse(request, "admin/scanner.html")


@csrf_exempt
def mollie_webhook(request):
    if request.method == 'POST':
        if 'id' not in request.POST:
            return HttpResponse(status=400)

        mollie_payment_id = request.POST['id']
        mollie_payment = MollieClient().client.payments.get(mollie_payment_id)
        payment = get_object_or_404(Payment, mollie_id=mollie_payment_id)

        payment.status = mollie_payment.get("status").lower()
        payment.save()

        return HttpResponse(status=200)

    return HttpResponseNotFound("Invalid request method")


@csrf_exempt #TODO verander webhook url in cal.com
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
    l = Leerling.objects.get(code=code)
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