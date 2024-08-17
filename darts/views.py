from email.utils import formataddr
from django.conf import settings
from django.http import BadHeaderError, HttpResponse, JsonResponse
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.template.response import TemplateResponse
from .forms import ContactForm, TornooiForm
from .models import Evenement, SkillLevel

def index(request):
    context = {
        'form': ContactForm()
    }
    return TemplateResponse(request, 'index.html', context)


def dartschool(request):
    context = {}
    return TemplateResponse(request, 'dartschool.html', context)


def tornooien(request):
    evenementen = Evenement.objects.all()
    paginator = Paginator(evenementen, 6)

    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "tornooien": page_obj,
        "enable_pagination": paginator.num_pages > 1
    }
    return TemplateResponse(request, 'tornooien.html', context)


def tornooi(request, slug):
    evenement = Evenement.objects.get(slug=slug)
    context = {
        "tornooi": evenement
    }
    return TemplateResponse(request, 'tornooi.html', context)


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

            # TODO
            return HttpResponse(status=200)

        else:
            return JsonResponse({'error':'Invalid form.'},status=400)
    
    # GET request
    evenement = Evenement.objects.get(slug=slug)
    context = {
        "tornooi": evenement,
        'skill_level_choices': SkillLevel.CHOICES,
    }
    return TemplateResponse(request, 'tornooi-inschrijving.html', context)


def about(request):
    context = {}
    return TemplateResponse(request, 'about.html', context)


def terms_of_service(request):
    context = {}
    return TemplateResponse(request, 'terms-of-service.html', context)


def privacy_policy(request):
    context = {}
    return TemplateResponse(request, 'privacy-policy.html', context)


def contact(request):
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            name = form.cleaned_data['name']
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
        else:
            return JsonResponse({'success': False, 'error': 'Form is not valid.'})

    return JsonResponse({'success': False, 'error': 'Invalid request method.'})