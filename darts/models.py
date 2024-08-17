import secrets
import string
from email.utils import formataddr
from io import BytesIO

from django.urls import reverse
import pytz
import qrcode
from ckeditor.fields import RichTextField
from django.conf import settings
from django.utils.translation import pgettext_lazy
from django.contrib.staticfiles import finders
from django.core.mail import EmailMessage
from django.db import models
from django.db.models import Q
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.html import strip_tags
from django.utils.translation import gettext_lazy as _
from djmoney.models.fields import MoneyField
from PIL import Image
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from simple_history.models import HistoricalRecords

from .templatetags import dutch_date
from .utils import helpers


class Evenement(models.Model):

    def __str__(self) -> str:
        return self.titel
    
    class Meta:
        get_latest_by = "start_datum"
    
    titel = models.CharField(max_length=100, verbose_name=_("Titel"))
    slug = models.SlugField(unique=True)
    beschrijving = RichTextField(verbose_name=_("Beschrijving"))
    vereisten = models.TextField(verbose_name=_("Vereisten (Elk op een nieuwe lijn)"))
    start_datum = models.DateTimeField(verbose_name=_("Start Datum"))
    einde_datum = models.DateTimeField(verbose_name=_("Eind Datum"))
    max_deelnemers = models.IntegerField(verbose_name=_("Max Deelnemers"))
    locatie_kort = models.CharField(max_length=25, verbose_name=_("Locatie (kort)"))
    locatie_lang = models.TextField(verbose_name=_("Locatie (lang)"))
    afbeelding = models.ImageField(verbose_name=_("afbeelding"), upload_to="darts")
    afbeeldingen_download_url = models.URLField(verbose_name=_("Download afbeeldingen URL"), blank=True, null=True)

    enable_inschrijvingen = models.BooleanField(verbose_name=_("Inschrijvingen Inschakelen"), default=False)

    history = HistoricalRecords(verbose_name=_("Geschiedenis"))

    @property
    def is_in_future(self):
        brussels_tz = pytz.timezone('Europe/Brussels')
        now = timezone.now().astimezone(brussels_tz)
        start_datum_brussels = self.start_datum.astimezone(brussels_tz)
        return now < start_datum_brussels
    
    @property
    def is_bezig(self):
        brussels_tz = pytz.timezone('Europe/Brussels')
        now = timezone.now().astimezone(brussels_tz)
        einde_datum_brussels = self.einde_datum.astimezone(brussels_tz)
        return (not self.is_in_future) and (now < einde_datum_brussels)
    
    @property
    def is_same_day(self):
        return self.start_datum.strftime("%d/%m/%Y") == self.einde_datum.strftime("%d/%m/%Y")
    
    @property
    def is_sold_out(self):
        # Total participants limit exceeded
        event_sold_out = self.participants_count >= self.max_deelnemers

        # All tickets have their max participants limit exceeded
        tickets_are_sold_out = all(ticket.is_sold_out for ticket in self.ticket_set.all())

        return tickets_are_sold_out or event_sold_out

    @property
    def remaining_tickets(self):
        return self.max_deelnemers - self.participants_count
    
    @property
    def participants_count(self):
        return sum(ticket.participants_count for ticket in self.ticket_set.all())
    
    def get_absolute_url(self):
        return reverse('tornooi', args=[str(self.slug)])
    
    @property
    def vereisten_lijst(self):
        return self.vereisten.split('\n')


class Ticket(models.Model):

    def __str__(self) -> str:
        return self.titel
    
    titel = models.CharField(max_length=100, verbose_name=_("titel"))
    price = MoneyField(verbose_name="Price", default_currency="EUR", max_digits=10, decimal_places=2)
    max_deelnemers = models.IntegerField(verbose_name=_("Max Deelnemers"))
    event = models.ForeignKey(Evenement, verbose_name=_("Evenement"), on_delete=models.RESTRICT)

    history = HistoricalRecords(verbose_name=_("Geschiedenis"))

    @property 
    def is_sold_out(self):
        amount_of_participants_with_this_as_ticket = Participant.objects.filter(ticket_id=self.pk).filter(
            Q(payment__status=PaymentStatus.PAID) | 
            Q(payment__status=PaymentStatus.OPEN)
        ).count()
        return amount_of_participants_with_this_as_ticket >= self.max_deelnemers
    
    @property
    def remaining_tickets(self):
        amount_of_participants_with_this_as_ticket = Participant.objects.filter(ticket_id=self.pk).count()
        return self.max_deelnemers - amount_of_participants_with_this_as_ticket
    
    @property
    def participants_count(self):
        return Participant.objects.filter(ticket_id=self.pk).filter(
            Q(payment__status=PaymentStatus.PAID) | 
            Q(payment__status=PaymentStatus.OPEN)
        ).count()



class PaymentStatus:
    PAID = "paid"
    AUTHORIZED = "authorized"
    OPEN = "open"
    CANCELED = "canceled"
    EXPIRED = "expired"
    FAILED = "failed"


    CHOICES = [
        (PAID, pgettext_lazy("payment status", "Betaald")),
        (OPEN, pgettext_lazy("payment status", "Open")),
        (CANCELED, pgettext_lazy("payment status", "Geannuleerd")),
        (EXPIRED, pgettext_lazy("payment status", "Verlopen")),
        (FAILED, pgettext_lazy("payment status", "Gefaald"))
    ]


class Payment(models.Model):
    
    def save(self, *args, **kwargs):
        # Check if payment is received
        if self.status == PaymentStatus.PAID:
            self.send_mail()

        super().save(*args, **kwargs)


    mollie_id = models.CharField(verbose_name=_("Mollie id"), blank=True, null=True)
    first_name = models.CharField(max_length=50, verbose_name=_("Voornaam"), blank=True, null=True)
    last_name = models.CharField(max_length=50, verbose_name=_("Achternaam"), blank=True, null=True)
    mail = models.EmailField(verbose_name=_("Email"), max_length=254, blank=True, null=True)
    status = models.CharField(max_length=10, choices=PaymentStatus.CHOICES, default=PaymentStatus.OPEN)
    amount = MoneyField(verbose_name="Prijs", default_currency="EUR", max_digits=10, decimal_places=2, blank=True, null=True)

    history = HistoricalRecords(verbose_name=_("Geschiedenis"))

    @property
    def success_url(self) -> str:
        # Return a URL where users are redirected after
        # they successfully complete a payment:
        return f"http://vanakaam.be/events/ticket/{self.pk}/success"


    def generate_ticket(self, for_email=False):
        participants = Participant.objects.filter(payment=self)
        tickets = []
        for p in participants:
            ticket = p.generate_ticket(return_as_http=False) 

            tickets.append(ticket)

            
        merged_buffer = helpers.merge_pdfs(tickets)
        if for_email: return merged_buffer

        response = HttpResponse(merged_buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="tickets-{self.pk}.pdf"'

        return response

    def send_mail(self):
        # we only need first because all info is the same for the matching participants
        participant = Participant.objects.filter(payment=self).first()
        print(participant)
        event = participant.ticket.event
        print(event)
        
        email_body = render_to_string('confirmation-email.html', {
            'event': event,
            'participant': participant,
        })

        # Generate tickets PDF
        tickets_pdf = self.generate_ticket(for_email=True)

        email = EmailMessage(
            'ChuDartz | Bevestiging',
            email_body,
            formataddr(('Evenementen | Saranalaya', settings.EMAIL_HOST_USER)),
            [participant.mail],
            bcc=[settings.EMAIL_HOST_USER]
        )
        email.content_subtype = 'html'

        # add tickets as attachment
        email.attach(f'tickets-{self.pk}.pdf', tickets_pdf.getvalue(), 'application/pdf')

        helpers.attach_image(email, "logo")
        helpers.attach_image(email, "facebook")
        helpers.attach_image(email, "mail")

        # Send the email
        email.send()



class SkillLevel:
    BEGINNER = "beginner"
    GEMIDDELD  = "gemiddeld"
    GEOEFEND = "geoefend"

    CHOICES = [
        (BEGINNER, pgettext_lazy("skill level", "Beginner")),
        (GEMIDDELD, pgettext_lazy("skill level", "Gemiddeld")),
        (GEOEFEND, pgettext_lazy("skill level", "Geoefend")),
    ]



class Participant(models.Model):

    def __str__(self) -> str:
        return f"{self.first_name} {self.last_name}" 
    
    class Meta:
        get_latest_by = "pk"
    
    first_name = models.CharField(max_length=50, verbose_name=_("Voornaam"))
    last_name = models.CharField(max_length=50, verbose_name=_("Achternaam"))
    mail = models.EmailField(verbose_name=_("Email"), max_length=254)
    straatnaam = models.CharField(verbose_name=_("Straatnaam"), max_length=100)
    nummer = models.CharField(verbose_name=_("Nummer"), max_length=6)
    stad = models.CharField(verbose_name=_("Stad"), max_length=40)
    level = models.CharField(max_length=10, choices=SkillLevel.CHOICES, default=SkillLevel.GEMIDDELD)
    payment = models.ForeignKey(Payment, on_delete=models.RESTRICT, verbose_name="Payment", blank=True, null=True)
    attended = models.BooleanField(verbose_name=_("Attended"), default=False)
    beschrijving = models.TextField(blank=True, null=True, verbose_name=_("beschrijving"))
    ticket = models.ForeignKey(Ticket, verbose_name=_("Ticket"), on_delete=models.RESTRICT)

    # seed for the QR codes
    random_seed = models.CharField(max_length=10, verbose_name="Random Seed", editable=False)
    
    history = HistoricalRecords(verbose_name=_("History"))


    def save(self, *args, **kwargs):
        if not self.random_seed:
            self.random_seed = self._generate_random_seed()
        super().save(*args, **kwargs)

    def _generate_random_seed(self):
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(10))
    
    def generate_qr_code(self):
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(f'participant_id:{self.pk}')
        qr.add_data(f'seed:{self.random_seed}')

        qr.make(fit=True)

        return qr.make_image(fill='black', back_color='white')
    
    def generate_ticket(self, return_as_http=True):
        # Create a buffer to hold the PDF data
        buffer = BytesIO()

        # Create a canvas object
        p = canvas.Canvas(buffer, pagesize=letter)

        qr_img = self.generate_qr_code()

        # Save the QR code afbeelding to a BytesIO object
        qr_buffer = BytesIO()
        qr_img.save(qr_buffer, format='PNG')
        qr_buffer.seek(0)

        qr_afbeelding = Image.open(qr_buffer)
        temp_path = "/tmp/qr_code.png"
        qr_afbeelding.save(temp_path)

        # Draw the QR code afbeelding onto the PDF
        p.drawImage(temp_path, 400, 590, 170, 170)

        # Add  logo
        logo_path = finders.find('img/logo-black.png')
        p.drawImage(logo_path, 100, 730, 427 * 0.3, 58 * 0.3)

        # get info about event
        event = self.ticket.event
        if dutch_date.dutch_date(event.start_datum) == dutch_date.dutch_date(event.einde_datum):
            formatted_date = f"{dutch_date.dutch_datetime(event.start_datum)} - {dutch_date.dutch_time(event.einde_datum)}"
        else:
            formatted_date = f"{dutch_date.dutch_datetime(event.start_datum)} - {dutch_date.dutch_datetime(event.einde_datum)}"

        # Add ticket details
        # Set correct font for titel
        font_path = finders.find('fonts/outfit/Outfit-Bold.ttf')
        pdfmetrics.registerFont(TTFont('Outfit', font_path))
        p.setFont("Outfit", 25)
        p.drawString(100, 690, str(event))

        # Set correct font for beschrijving
        font_path = finders.find('fonts/outfit/Outfit-Regular.ttf')
        pdfmetrics.registerFont(TTFont('Outfit', font_path))
        p.setFont("Outfit", 18)

        p.drawString(100, 660, formatted_date)
        p.drawString(100, 635, str(self.ticket))
        p.drawString(100, 610, strip_tags(event.locatie_kort))

        # Finalize the PDF
        p.save()

        # Get the value of the BytesIO buffer and write it to the response
        buffer.seek(0)

        if not return_as_http:
            return buffer
        
        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="ticket-{self.pk}.pdf"'

        return response