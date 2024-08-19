from decimal import Decimal
from email.utils import formataddr
from django.conf import settings
from django.http import BadHeaderError, HttpResponse, HttpResponseNotFound, JsonResponse
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse

from darts.payment import MollieClient
from .forms import ContactForm, TornooiForm
from .models import Evenement, Participant, Payment, SkillLevel, Ticket

def index(request):
    context = {
        'form': ContactForm()
    }
    return TemplateResponse(request, 'pages/index.html', context)


def dartschool(request):
    context = {}
    return TemplateResponse(request, 'pages/dartschool.html', context)


def inschrijven_dartschool(request):
    context = {
        "vereisten": ["10 jaar oud", "blabla", "etc"]
    }
    return TemplateResponse(request, 'pages/dartschool-inschrijving.html', context)


def tornooien(request):
    evenementen = Evenement.objects.all()
    paginator = Paginator(evenementen, 6)

    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "tornooien": page_obj,
        "enable_pagination": paginator.num_pages > 1
    }
    return TemplateResponse(request, 'pages/tornooien.html', context)


def tornooi(request, slug):
    evenement = Evenement.objects.get(slug=slug)
    context = {
        "tornooi": evenement
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
                slug=slug
            )

            payment.mollie_id = mollie_payment.id
            payment.save()
            
            return redirect(mollie_payment.checkout_url)
        

        # form was not valid, send to error page
        context = {
            "success": False,
            "tornooi": Evenement.objects.get(slug=slug)
        }
        return TemplateResponse(request, 'pages/tornooi-inschrijving-response.html', context)
        
    
    # GET request
    evenement = Evenement.objects.get(slug=slug)
    tickets = Ticket.objects.filter(event=evenement)
    
    context = {
        "tornooi": evenement,
        "tickets": tickets,
        'skill_level_choices': SkillLevel.CHOICES,
    }
    return TemplateResponse(request, 'pages/tornooi-inschrijving.html', context)


def inschrijven_tornooi_success(request, slug):
    context = {
        "success": True,
        "tornooi": Evenement.objects.get(slug=slug)
    }
    return TemplateResponse(request, 'pages/tornooi-inschrijving-response.html', context)


def over_ons(request):
    context = {}
    return TemplateResponse(request, 'pages/about.html', context)


def terms_of_service(request):
    context = {}
    return TemplateResponse(request, 'pages/terms-of-service.html', context)


def privacy_policy(request):
    context = {}
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
        send_mail(
            f'Contact Form - {subject}',
            f'Name: {name}\nEmail: {email}\nMessage: {message}',
            formataddr(('Contact | ChuDartz', settings.EMAIL_HOST_USER)),
                ['silasdevuyst@hotmail.com'], # TODO wie krijgt bericht?
                fail_silently=False,
        )
        return JsonResponse({'success': True})
    
    except BadHeaderError:
        return JsonResponse({'success': False, 'error': 'Invalid header found.'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
            
              
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