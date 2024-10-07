from email.utils import formataddr
from django.conf import settings
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.http import BadHeaderError, JsonResponse
from django.template.response import TemplateResponse
from django.utils import timezone
from django.shortcuts import get_object_or_404

from pokemon.forms import ContactForm, StandhouderForm
from pokemon.models import Evenement, Ticket


def index(request):
    return TemplateResponse(request, 'pokemon/pages/index.html', get_default_context())

def over_ons(request):
    return TemplateResponse(request, 'pokemon/pages/about.html', get_default_context())


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
    context = {
        "evenement": evenement,
        "tickets": Ticket.objects.filter(event=evenement) # TODO fix uitverkochte tickets
    }
    return TemplateResponse(request, 'pokemon/pages/evenement.html', context)


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
                f'Evenement: {evenement.titel}\nBedrijfsnaam: {data['bedrijfsnaam']}\nNaam: {data['naam']}\nEmail: {data['email']}\nTelefoon: {data['telefoon']}\nAantal Tafels: {data['aantal_tafels']}\nFactuur: {data['factuur']}\nElectriciteit: {data['electriciteit']}\nOpmerkingen: {data['opmerkingen']}',
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



def get_default_context():
    now = timezone.now()
    return {
        "evenement": Evenement.objects.filter(start_datum__gt=now).order_by('start_datum').first()
    }