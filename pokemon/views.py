from email.utils import formataddr
from django.conf import settings
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.http import BadHeaderError, JsonResponse
from django.template.response import TemplateResponse

from pokemon.forms import ContactForm
from pokemon.models import Evenement


def index(request):
    context = {}
    return TemplateResponse(request, 'pokemon/pages/index.html', context)

def over_ons(request):
    context = {}
    return TemplateResponse(request, 'pokemon/pages/about.html', context)


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

    context = {
        "evenementen": page_obj,
        "enable_pagination": paginator.num_pages > 1,
    }
    return TemplateResponse(request, 'pokemon/pages/evenementen.html', context)


def evenement(request, slug):
    evenement = Evenement.objects.get(slug=slug)
    context = {
        "evenement": evenement,
    }
    return TemplateResponse(request, 'pokemon/pages/evenement.html', context)


def algemene_voorwaarden(request):
    context = {}
    return TemplateResponse(request, 'pokemon/pages/algemene_voorwaarden.html', context)


def privacybeleid(request):
    context = {}
    return TemplateResponse(request, 'pokemon/pages/privacybeleid.html', context)


def disclaimer(request):
    context = {}
    return TemplateResponse(request, 'pokemon/pages/disclaimer.html', context)


def faq(request):
    context = {}
    return TemplateResponse(request, 'pokemon/pages/faq.html', context)