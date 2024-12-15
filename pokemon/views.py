from decimal import Decimal
from email.utils import formataddr
import json
from django.contrib.admin.views.decorators import staff_member_required
from django.conf import settings
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.http import BadHeaderError, HttpResponse, HttpResponseBadRequest, HttpResponseNotFound, JsonResponse
from django.template.response import TemplateResponse
from django.utils import timezone
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.csrf import csrf_exempt

from darts.utils import helpers
from pokemon.forms import ContactForm, StandhouderForm
from pokemon.models import Evenement, Participant, Payment, PaymentStatus, Ticket
from pokemon.payment import MollieClient


def index(request):
    return TemplateResponse(request, 'pokemon/pages/index.html', get_default_context())

def over_ons(request):
    return TemplateResponse(request, 'pokemon/pages/about.html', get_default_context())


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
            formataddr(('Contact | ChudartZ Collectibles', settings.EMAIL_HOST_USER)),
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


def evenementen(request):
    evenementen = Evenement.objects.all()
    paginator = Paginator(evenementen, 6)

    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = get_default_context()
    context["evenementen"] = page_obj
    context["enable_pagination"] = paginator.num_pages > 1

    return TemplateResponse(request, 'pokemon/pages/evenementen.html', context)


def evenement(request, slug):
    evenement = get_object_or_404(Evenement, slug=slug)

    if request.POST:

        if not evenement.enable_inschrijvingen: return HttpResponseBadRequest("Inschrijvingen gesloten.")

        tickets = Ticket.objects.filter(event=evenement)
        ticket_quantities = {}

        # get selected ticket quantities
        for possible_ticket in tickets:
           
            ticket_quantity_key = f'ticket-form-number-{possible_ticket.id}'
            quantity = request.POST.get(ticket_quantity_key)

            try:
                ticket_quantities[possible_ticket.id] = int(quantity)
            except (ValueError, TypeError):
                ticket_quantities[possible_ticket.id] = 0  # Handle empty or invalid input


        # check if at least 1 ticket has valid quantity
        is_valid_quantitites = False
        for ticket_id, quantity in ticket_quantities.items():
            chosen_ticket = get_object_or_404(Ticket, pk=ticket_id)

            # check if ticket possible to buy
            if chosen_ticket.disable_ticket or chosen_ticket.is_sold_out:
                return HttpResponseBadRequest("Invalid ticket")
            
            # check if there are still enough tickets to buy
            if quantity > chosen_ticket.remaining_tickets:
                return HttpResponseBadRequest("Not enough remaining tickets")
            
            # quantity must be at least 0
            if quantity < 0:
                return HttpResponseBadRequest("Ticket count must be at least 0")
            
            # valid
            if quantity > 0:
                is_valid_quantitites = True
                break

        if not is_valid_quantitites: return HttpResponseBadRequest("There should be at least 1 ticket ordered")

        # get total price of transaction
        total_cost = 0
        for ticket_id, quantity in ticket_quantities.items():
            total_cost +=  quantity * Decimal(get_object_or_404(Ticket, pk=ticket_id).price.amount)


        payment = Payment.objects.create(
            mail = request.POST.get('email'),
            amount=total_cost
        )

        for ticket_id, quantity in ticket_quantities.items():
            for _ in range(quantity):
                Participant.objects.create(
                    mail = request.POST.get('email'),
                    payment_id = payment.pk,
                    ticket = get_object_or_404(Ticket, pk=ticket_id),
                )

        # create the mollie payment
        mollie_payment = MollieClient().create_mollie_payment(
            amount=total_cost,
            description="ChudartZ Collectibles",
            redirect_url=f'https://chudartz-collectibles.com/nl/evenement/{slug}/success',
        )

        payment.mollie_id = mollie_payment.id
        payment.save()
        
        return redirect(mollie_payment.checkout_url)


    # GET request
    context = {
        "evenement": evenement,
        "tickets": Ticket.objects.filter(event=evenement),
        "partners": evenement.partners.all()
    }
    return TemplateResponse(request, 'pokemon/pages/evenement.html', context)


def evenement_success(request, slug):
    context = get_default_context()
    context["success"] = True
    context["evenement"] = get_object_or_404(Evenement, slug=slug)

    return TemplateResponse(request, 'pokemon/pages/evenement-inschrijving-response.html', context)


def standhouder(request, slug):

    evenement = get_object_or_404(Evenement, slug=slug)
    context = {
        "evenement": evenement
    }

    if request.POST:
        if not evenement.enable_standhouder: return JsonResponse({'success': False, 'error': 'Standhouder inschrijvingen gesloten.'})
        form = StandhouderForm(request.POST)
        
        if not form.is_valid():
            print(form.errors)

            # form was not valid, send to error page
            context["success"] = False

            return TemplateResponse(request, 'pokemon/pages/standhouder-response.html', context)
        
        # send mails
        try:
            data = form.cleaned_data
            # Send mail to admins
            send_mail(
                f'Standhouder Aanvraag',
                f'Evenement: {evenement.titel}\nBedrijfsnaam: {data['bedrijfsnaam']}\nNaam: {data['naam']}\nEmail: {data['email']}\nTelefoon: {data['telefoon']}\nAantal Tafels: {data['aantal_tafels']}\nFactuur: {'ja' if data['factuur'] else 'nee'}\nElectriciteit: {'ja' if data['electriciteit'] else 'nee'}\Tafel/Stoel: {'ja' if data['tafel'] else 'nee'}Opmerkingen: {data['opmerkingen']}',
                formataddr(('Contact | ChudartZ', settings.EMAIL_HOST_USER)),
                [settings.EMAIL_HOST_USER],
                fail_silently=False,
            )

            # Send confirmation mail to user
            send_mail(
                'Chudartz Collectibles | Standhouder Aanvraag Ontvangen',
                "Beste\n\nBedankt voor het invullen van het contactformulier. Wij hebben uw bericht in goede orde ontvangen en zullen zo snel mogelijk contact met u opnemen.\n\nMet vriendelijke groeten\n\nTeam ChudartZ Collectibles",
                formataddr(('Contact | ChudartZ', settings.EMAIL_HOST_USER)),
                [data['email']],
                fail_silently=False
            )

            context["success"] = True
            
            return TemplateResponse(request, 'pokemon/pages/standhouder-response.html', context)
        
        except Exception as e:
            print(e)
            context["success"] = False
            return TemplateResponse(request, 'pokemon/pages/standhouder-response.html', context)
        

    # GET request
    context = {
        "evenement": evenement,
        "form": StandhouderForm(),
    }
    return TemplateResponse(request, 'pokemon/pages/standhouder.html', context)


def algemene_voorwaarden(request):
    return TemplateResponse(request, 'pokemon/pages/algemene_voorwaarden.html', get_default_context())


def privacybeleid(request):
    return TemplateResponse(request, 'pokemon/pages/privacybeleid.html', get_default_context())


def disclaimer(request):
    return TemplateResponse(request, 'pokemon/pages/disclaimer.html', get_default_context())


def faq(request):
    return TemplateResponse(request, 'pokemon/pages/faq.html', get_default_context())


@csrf_exempt
def mollie_webhook(request):
    if request.method == 'POST':
        if 'id' not in request.POST:
            return HttpResponseBadRequest()

        mollie_payment_id = request.POST['id']
        mollie_payment = MollieClient().client.payments.get(mollie_payment_id)
        payment = get_object_or_404(Payment, mollie_id=mollie_payment_id)

        mollie_status = mollie_payment.get("status", "").lower()

        # Validate status against defined choices
        valid_statuses = [choice[0] for choice in PaymentStatus.CHOICES]
        if mollie_status in valid_statuses:
            payment.status = mollie_status
            payment.save()

        return HttpResponse(status=200)

    return HttpResponseNotFound("Invalid request method")


@staff_member_required
def scanner(request):
    return TemplateResponse(request, "pokemon/admin/scanner.html")


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


def get_default_context():
    now = timezone.now()
    return {
        "evenement": Evenement.objects.filter(start_datum__gt=now).order_by('start_datum').first()
    }

