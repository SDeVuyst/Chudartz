import logging
import secrets
import string
from email.utils import formataddr

import pytz
import qrcode
from ckeditor.fields import RichTextField
from django.conf import settings
from django.utils.translation import pgettext_lazy

logger = logging.getLogger(__name__)
from django.core.mail import EmailMessage, send_mail
from django.db import models
from django.db.models import Q
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from djmoney.models.fields import MoneyField
from simple_history.models import HistoricalRecords
from phonenumber_field.modelfields import PhoneNumberField

from chudartz.ticket_renderer import render_ticket_pdf
from darts.utils import helpers
from darts.validators.image_validator import validate_image_max_size


class Partner(models.Model):
    name = models.CharField(max_length=100)
    logo = models.ImageField(upload_to='partner_logos/')
    website_url = models.URLField(verbose_name=_("Website URL"))

    def __str__(self):
        return self.name
    

class Evenement(models.Model):

    def __str__(self) -> str:
        return self.titel
    
    class Meta:
        get_latest_by = "start_datum"
        ordering = ['-start_datum']
        verbose_name = "Evenement"
        verbose_name_plural = "Evenementen"
    
    titel = models.CharField(max_length=100, verbose_name=_("Titel"))
    intro_op_index = models.TextField(_("Intro op homepagina"), max_length=400)
    slug = models.SlugField(unique=True)
    titel_sectie_a = models.CharField(_("Titel Sectie A"), max_length=50)
    tekst_sectie_a = RichTextField(verbose_name=_("Tekst Sectie A"))
    start_datum = models.DateTimeField(verbose_name=_("Start Datum"))
    einde_datum = models.DateTimeField(verbose_name=_("Eind Datum"))
    max_deelnemers = models.IntegerField(verbose_name=_("Max Deelnemers"))
    locatie_kort = models.CharField(max_length=25, verbose_name=_("Locatie (kort)"))
    locatie_lang = models.TextField(verbose_name=_("Locatie (lang)"))
    afbeelding = models.ImageField(verbose_name=_("afbeelding"), upload_to="darts")
    standhouder_inbegrepen = models.TextField(verbose_name=_("Inbegrepen Standhouder (Elk op een nieuwe lijn)"))
    standhouder_prijzen = models.TextField(verbose_name=_("Prijzen Standhouder (Elk op een nieuwe lijn)"))
    enable_standhouder = models.BooleanField(verbose_name=_("Standhouder Inschrijvingen Inschakelen"), default=True)
    standhouder_zaalplan_actief = models.BooleanField(
        verbose_name=_("Zaalplan (tafelkeuze) tonen"),
        default=True,
        help_text=_("Aan: standhouders kiezen hun tafel(s) op de plattegrond. Uit: de tafelkeuze-stap wordt overgeslagen en de standhouder geeft het gewenste aantal tafels op."),
    )
    standhouder_prijs_per_tafel = MoneyField(
        verbose_name=_("Prijs per tafel (zonder zaalplan)"),
        default_currency="EUR",
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text=_("Enkel gebruikt wanneer het zaalplan uitstaat."),
    )
    standhouder_max_tafels = models.PositiveIntegerField(
        verbose_name=_("Max. aantal tafels per standhouder"),
        default=3,
        help_text=_(
            "Maximum aantal tafels dat één standhouder mag kiezen of opgeven, "
            "ongeacht of het zaalplan aan of uit staat."
        ),
    )
    standhouder_betaling_verplicht = models.BooleanField(
        verbose_name=_("Online betaling via Mollie"),
        default=False,
        help_text=_(
            "Aan: standhouder betaalt direct online via Mollie na bevestiging. "
            "Uit: geen online betaling; de standhouder ontvangt een voorlopige bevestiging "
            "per e-mail en jullie nemen manueel contact op."
        ),
    )
    enable_inschrijvingen = models.BooleanField(verbose_name=_("Inschrijvingen Inschakelen"), default=False)
    partners = models.ManyToManyField(Partner, verbose_name=_("Partners"), blank=True, null=True)
    toon_op_site = models.BooleanField(verbose_name=_("Toon op site"), default=False)
    highlight_event = models.BooleanField(verbose_name=_("Highlight Event"), default=False)
    volgorde = models.SmallIntegerField(verbose_name=_("Volgorde op pagina"), default=0)

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
         return f'https://chudartz-collectibles.com/nl/evenement/{self.slug}/'
    
    @property
    def standhouder_inbegrepen_lijst(self):
        return self.standhouder_inbegrepen.split('\n')
    
    @property
    def standhouder_prijzen_lijst(self):
        return self.standhouder_prijzen.split('\n')

    @property
    def standhouder_inschrijving_mogelijk(self):
        return self.enable_standhouder and self.is_in_future

    STANDHOUDER_CONTACT_EMAIL = "chudartz@gmail.com"

    def standhouder_tafel_limiet_bericht(self):
        return _(
            "Wenst u meer dan %(max)s tafels? Neem dan contact met ons op."
        ) % {"max": self.standhouder_max_tafels}


class Ticket(models.Model):
    class Meta:
        verbose_name = "Ticket"
        verbose_name_plural = "Tickets"

    def __str__(self) -> str:
        return f"{self.titel} - {self.price}"
    
    titel = models.CharField(max_length=100, verbose_name=_("titel"))
    price = MoneyField(verbose_name="Price", default_currency="EUR", max_digits=10, decimal_places=2)
    icon = models.CharField(max_length=40, verbose_name=_("Bootstrap Icon"))
    max_deelnemers = models.IntegerField(verbose_name=_("Max Deelnemers"))
    event = models.ForeignKey(Evenement, verbose_name=_("Evenement"), on_delete=models.RESTRICT)
    disable_ticket = models.BooleanField(_("Schakel ticket uit"))
    toegang_start = models.DateTimeField(
        _("Toegang vanaf"),
        null=True,
        blank=True,
        help_text=_("Laat leeg om de evenementtijden te gebruiken. Alleen zichtbaar op het ticket."),
    )
    toegang_einde = models.DateTimeField(
        _("Toegang tot"),
        null=True,
        blank=True,
        help_text=_("Laat leeg om de evenementtijden te gebruiken. Alleen zichtbaar op het ticket."),
    )

    history = HistoricalRecords(verbose_name=_("Geschiedenis"))

    def get_toegang_start(self):
        return self.toegang_start or self.event.start_datum

    def get_toegang_einde(self):
        return self.toegang_einde or self.event.einde_datum

    @property 
    def is_sold_out(self):
        amount_of_participants_with_this_as_ticket = Participant.objects.filter(ticket_id=self.pk).filter(
            Q(payment__status=PaymentStatus.PAID) | 
            Q(payment__status=PaymentStatus.OPEN)
        ).count()
        return amount_of_participants_with_this_as_ticket >= self.max_deelnemers
    
    @property
    def remaining_tickets(self):
        return self.max_deelnemers - self.participants_count
    
    @property
    def participants_count(self):
        return Participant.objects.filter(ticket_id=self.pk).filter(
            Q(payment__status=PaymentStatus.PAID) | 
            Q(payment__status=PaymentStatus.OPEN)
        ).count()
    
    @property
    def voordelen(self):
        return self.eigenschappen.filter(is_voordeel=True).order_by('volgorde')

    @property
    def nadelen(self):
        return self.eigenschappen.filter(is_voordeel=False).order_by('volgorde')


class TicketEigenschap(models.Model):
    class Meta:
        verbose_name = "Ticket Eigenschap"
        verbose_name_plural = "Ticket Eigenschappen"

    def __str__(self):
        return self.tekst

    tekst = models.CharField(_("Tekst"), max_length=100)
    is_voordeel = models.BooleanField(_("Voordeel"))
    volgorde = models.SmallIntegerField(verbose_name=_("Volgorde"), default=0)
    
    ticket = models.ManyToManyField(Ticket, related_name='eigenschappen')

    history = HistoricalRecords(verbose_name=_("Geschiedenis"))


class KortingscodeType:
    PERCENT = "percent"
    FIXED = "fixed"

    CHOICES = [
        (PERCENT, _("Percentage")),
        (FIXED, _("Vast bedrag")),
    ]


class Kortingscode(models.Model):
    class Meta:
        verbose_name = _("Kortingscode")
        verbose_name_plural = _("Kortingscodes")

    def __str__(self):
        return self.code

    code = models.CharField(_("Code"), max_length=50, unique=True)
    discount_type = models.CharField(
        _("Type korting"),
        max_length=10,
        choices=KortingscodeType.CHOICES,
        default=KortingscodeType.PERCENT,
    )
    amount = models.DecimalField(
        _("Waarde"),
        max_digits=10,
        decimal_places=2,
        help_text=_("Percentage (0-100) of vast bedrag in euro."),
    )
    geldig_van = models.DateTimeField(_("Geldig vanaf"), null=True, blank=True)
    geldig_tot = models.DateTimeField(_("Geldig tot"), null=True, blank=True)
    max_gebruik = models.PositiveIntegerField(
        _("Max. aantal keer te gebruiken"),
        null=True,
        blank=True,
        help_text=_("Leeg = onbeperkt."),
    )
    aantal_gebruikt = models.PositiveIntegerField(_("Aantal keer gebruikt"), default=0)
    actief = models.BooleanField(_("Actief"), default=True)
    evenementen = models.ManyToManyField(
        Evenement,
        verbose_name=_("Evenementen"),
        blank=True,
        help_text=_("Leeg = geldig voor alle evenementen."),
    )
    tickets = models.ManyToManyField(
        Ticket,
        verbose_name=_("Tickets"),
        blank=True,
        help_text=_("Leeg = geldig voor alle tickettypes."),
    )
    min_bedrag = MoneyField(
        _("Minimum bestelbedrag"),
        default_currency="EUR",
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )

    history = HistoricalRecords(verbose_name=_("Geschiedenis"))

    def bereken_korting(self, subtotaal):
        from decimal import Decimal

        subtotaal = Decimal(str(subtotaal))
        if self.discount_type == KortingscodeType.PERCENT:
            korting = (subtotaal * self.amount / Decimal("100")).quantize(Decimal("0.01"))
        else:
            korting = min(self.amount, subtotaal)
        return max(korting, Decimal("0"))

    def is_geldig_op_moment(self):
        now = timezone.now()
        if not self.actief:
            return False
        if self.geldig_van and now < self.geldig_van:
            return False
        if self.geldig_tot and now > self.geldig_tot:
            return False
        if self.max_gebruik is not None and self.aantal_gebruikt >= self.max_gebruik:
            return False
        return True


class PaymentStatus:
    PAID = "paid"
    AUTHORIZED = "authorized"
    OPEN = "open"
    CANCELED = "canceled"
    EXPIRED = "expired"
    FAILED = "failed"
    REFUNDED = "refunded"


    CHOICES = [
        (PAID, pgettext_lazy("payment status", "Betaald")),
        (OPEN, pgettext_lazy("payment status", "Open")),
        (CANCELED, pgettext_lazy("payment status", "Geannuleerd")),
        (EXPIRED, pgettext_lazy("payment status", "Verlopen")),
        (FAILED, pgettext_lazy("payment status", "Gefaald")),
        (REFUNDED, pgettext_lazy("payment status", "Teruggestort"))
    ]

class Payment(models.Model):

    def __str__(self) -> str:
        return f"{self.mollie_id} | {self.first_name} {self.last_name}" 
    
    def save(self, *args, **kwargs):
        became_paid = False
        if self.pk:
            previous = Payment.objects.filter(pk=self.pk).only("status").first()
            if (
                previous
                and previous.status != PaymentStatus.PAID
                and self.status == PaymentStatus.PAID
            ):
                became_paid = True
        elif self.status == PaymentStatus.PAID:
            became_paid = True

        super().save(*args, **kwargs)

        if became_paid:
            if Participant.objects.filter(payment=self).exists():
                self.send_mail()
            if self.kortingscode_id:
                from django.db.models import F
                Kortingscode.objects.filter(pk=self.kortingscode_id).update(
                    aantal_gebruikt=F("aantal_gebruikt") + 1
                )

    mollie_id = models.CharField(verbose_name=_("Mollie id"), blank=True, null=True)
    first_name = models.CharField(max_length=50, verbose_name=_("Voornaam"), blank=True, null=True)
    last_name = models.CharField(max_length=50, verbose_name=_("Achternaam"), blank=True, null=True)
    mail = models.EmailField(verbose_name=_("Email"), max_length=254, blank=True, null=True)
    status = models.CharField(max_length=10, choices=PaymentStatus.CHOICES, default=PaymentStatus.OPEN)
    amount = MoneyField(verbose_name="Prijs", default_currency="EUR", max_digits=10, decimal_places=2, blank=True, null=True)
    subtotaal = MoneyField(
        verbose_name=_("Subtotaal"),
        default_currency="EUR",
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
    )
    korting_bedrag = MoneyField(
        verbose_name=_("Korting"),
        default_currency="EUR",
        max_digits=10,
        decimal_places=2,
        default=0,
    )
    kortingscode = models.ForeignKey(
        Kortingscode,
        verbose_name=_("Kortingscode"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="betalingen",
    )

    history = HistoricalRecords(verbose_name=_("Geschiedenis"))

    def generate_ticket(self, for_email=False):
        from chudartz.ticket_renderer import render_tickets_pdf

        participants = Participant.objects.filter(payment=self).select_related("ticket__event")
        ticket_items = [
            (p.ticket.event, p.ticket, p.generate_qr_code())
            for p in participants
        ]
        merged_buffer = render_tickets_pdf(ticket_items)
        if for_email:
            return merged_buffer

        response = HttpResponse(merged_buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="tickets-{self.pk}.pdf"'

        return response

    def send_mail(self):
        # we only need first because all info is the same for the matching participants
        participant = Participant.objects.filter(payment=self).first()
        print(participant)
        event = participant.ticket.event
        print(event)
        
        email_body = render_to_string('pokemon/email/confirmation-mail-participant.html', {
            'evenement': event,
        })

        # Generate tickets PDF
        tickets_pdf = self.generate_ticket(for_email=True)

        email = EmailMessage(
            'ChudartZ Collectibles | Bevestiging',
            email_body,
            formataddr(('Evenementen | Chudartz', settings.EMAIL_HOST_USER)),
            [participant.mail],
            bcc=[settings.EMAIL_HOST_USER]
        )
        email.content_subtype = 'html'

        # add tickets as attachment
        email.attach(f'tickets-{self.pk}.pdf', tickets_pdf.getvalue(), 'application/pdf')

        helpers.attach_image(email, "logo-black", from_pokemon=True)

        # Send the email
        email.send()


# Deelnemer van evenement
class Participant(models.Model):

    def __str__(self) -> str:
        return f"{self.mail}" 
    
    class Meta:
        get_latest_by = "pk"
        verbose_name = "Deelnemer"
        verbose_name_plural = "Deelnemers"

    
    mail = models.EmailField(verbose_name=_("Email"), max_length=254, blank=True, null=True)
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
        buffer = render_ticket_pdf(
            event=self.ticket.event,
            ticket=self.ticket,
            qr_image=self.generate_qr_code(),
        )

        if not return_as_http:
            return buffer

        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="ticket-{self.pk}.pdf"'

        return response
    
    def send_mail(self):
        event = self.ticket.event
        
        email_body = render_to_string('pokemon/email/confirmation-mail-participant.html', {
            'evenement': event,
        })

        # Generate tickets PDF
        tickets_pdf = self.generate_ticket()

        email = EmailMessage(
            'ChudartZ Collectibles | Bevestiging',
            email_body,
            formataddr(('Evenementen | Chudartz', settings.EMAIL_HOST_USER)),
            [self.mail],
            bcc=[settings.EMAIL_HOST_USER]
        )
        email.content_subtype = 'html'

        # add tickets as attachment
        email.attach(f'ticket.pdf', tickets_pdf.getvalue(), 'application/pdf')

        helpers.attach_image(email, "logo-black", from_pokemon=True)

        # Send the email
        email.send()


class Sponsor(models.Model):
    naam = models.CharField(max_length=50, verbose_name=_("Naam"))
    website_url = models.URLField(verbose_name=_("Website URL"))
    info = RichTextField(verbose_name=_("Info over Sponsor"))
    toon_op_index = models.BooleanField(verbose_name=_("Toon Op Voorpagina"), default=True)
    toon_in_footer = models.BooleanField(verbose_name=_("Toon in footer"), default=True)
    toon_op_sponsors_pagina = models.BooleanField(verbose_name=_("Toon op sponsor pagina"), default=True)
    toon_knop_op_sponsors_pagina = models.BooleanField(verbose_name=_("Toon knop op sponsors pagina"), default=True)
    volgorde_footer = models.SmallIntegerField(verbose_name=_("Volgorde in footer"), default=0)
    volgorde_pagina = models.SmallIntegerField(verbose_name=_("Volgorde op pagina"), default=0)
    logo = models.ImageField(verbose_name=_("Logo"), upload_to="sponsor")
    afbeelding = models.ImageField(verbose_name=_("afbeelding"), upload_to="sponsor")

    history = HistoricalRecords(verbose_name=_("History"))

    def __str__(self):
        return self.naam
    
    class Meta:
        verbose_name = "Sponsor"
        verbose_name_plural = "Sponsors"


class EvenementFoto(models.Model):
    evenement = models.ForeignKey(Evenement, on_delete=models.CASCADE, related_name="fotos_evenement", verbose_name=_("Evenement"))
    afbeelding = models.ImageField(upload_to="evenement_fotos", verbose_name=_("Foto"), validators=[validate_image_max_size])
    omschrijving = models.CharField(max_length=255, blank=True, null=True, verbose_name=_("Omschrijving"))
    volgorde = models.PositiveIntegerField(default=0, verbose_name=_("Volgorde"))

    class Meta:
        ordering = ["volgorde", "id"]
        verbose_name = "Evenement Foto"
        verbose_name_plural = "Evenement Foto's"

    def __str__(self):
        return f"Foto voor {self.evenement.titel} ({self.id})"


class CelType:
    LEEG = "leeg"
    TAFEL = "tafel"
    GEBLOKKEERD = "geblokkeerd"

    CHOICES = [
        (LEEG, _("Leeg")),
        (TAFEL, _("Tafel")),
        (GEBLOKKEERD, _("Geblokkeerd")),
    ]


class StandhouderInschrijvingStatus:
    CONCEPT = "concept"
    INGEDIEND = "ingediend"
    WACHT_OP_BETALING = "wacht_op_betaling"
    BETAALD = "betaald"
    VERLOPEN = "verlopen"

    CHOICES = [
        (CONCEPT, _("Concept")),
        (INGEDIEND, _("Ingediend")),
        (WACHT_OP_BETALING, _("Wacht op betaling")),
        (BETAALD, _("Betaald")),
        (VERLOPEN, _("Verlopen")),
    ]

    BEZET = {INGEDIEND, WACHT_OP_BETALING, BETAALD}


class VraagType:
    TEKST = "tekst"
    TEXTAREA = "textarea"
    BOOLEAN = "boolean"
    CHECKBOX = "checkbox"
    NUMBER = "number"
    SELECT = "select"

    CHOICES = [
        (TEKST, _("Tekst")),
        (TEXTAREA, _("Lange tekst")),
        (BOOLEAN, _("Ja/Nee")),
        (CHECKBOX, _("Checkbox")),
        (NUMBER, _("Getal")),
        (SELECT, _("Keuzelijst")),
    ]


class Zaalplan(models.Model):
    evenement = models.OneToOneField(
        Evenement,
        on_delete=models.CASCADE,
        related_name="zaalplan",
        verbose_name=_("Evenement"),
    )
    rijen = models.PositiveIntegerField(verbose_name=_("Aantal rijen"), default=8)
    kolommen = models.PositiveIntegerField(verbose_name=_("Aantal kolommen"), default=12)
    standaard_prijs = MoneyField(
        verbose_name=_("Standaard prijs per tafel"),
        default_currency="EUR",
        max_digits=10,
        decimal_places=2,
        default=0,
    )

    history = HistoricalRecords(verbose_name=_("Geschiedenis"))

    class Meta:
        verbose_name = _("Zaalplan")
        verbose_name_plural = _("Zaalplannen")

    def __str__(self):
        return f"Zaalplan {self.evenement.titel}"

    def genereer_rooster(self):
        for rij in range(self.rijen):
            for kolom in range(self.kolommen):
                ZaalplanCel.objects.get_or_create(
                    zaalplan=self,
                    rij=rij,
                    kolom=kolom,
                    defaults={"cel_type": CelType.LEEG},
                )
        self.cellen.filter(rij__gte=self.rijen).delete()
        self.cellen.filter(kolom__gte=self.kolommen).delete()

        # Groepen met minder dan 2 overgebleven cellen ontkoppelen
        from collections import Counter
        counts = Counter(
            self.cellen.exclude(groep=None).values_list("groep", flat=True)
        )
        for groep_id, aantal in counts.items():
            if aantal < 2:
                self.cellen.filter(groep=groep_id).update(groep=None)


class ZaalplanCel(models.Model):
    zaalplan = models.ForeignKey(
        Zaalplan,
        on_delete=models.CASCADE,
        related_name="cellen",
        verbose_name=_("Zaalplan"),
    )
    rij = models.PositiveIntegerField(verbose_name=_("Rij"))
    kolom = models.PositiveIntegerField(verbose_name=_("Kolom"))
    cel_type = models.CharField(
        max_length=12,
        choices=CelType.CHOICES,
        default=CelType.LEEG,
        verbose_name=_("Type"),
    )
    label = models.CharField(max_length=30, blank=True, verbose_name=_("Label"))
    prijs = MoneyField(
        verbose_name=_("Prijs override"),
        default_currency="EUR",
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
    )
    groep = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_("Groep (samengevoegde cel)"),
    )
    gereserveerd = models.BooleanField(
        default=False,
        verbose_name=_("Reeds gereserveerd"),
    )

    history = HistoricalRecords(verbose_name=_("Geschiedenis"))

    class Meta:
        verbose_name = _("Zaalplan cel")
        verbose_name_plural = _("Zaalplan cellen")
        unique_together = ("zaalplan", "rij", "kolom")
        ordering = ["rij", "kolom"]

    def __str__(self):
        return self.display_label

    @property
    def display_label(self):
        if self.label:
            return self.label
        return f"{chr(65 + self.rij)}{self.kolom + 1}"

    @property
    def effectieve_prijs(self):
        if self.prijs is not None:
            return self.prijs
        return self.zaalplan.standaard_prijs

    @property
    def is_samengevoegd(self):
        return self.groep is not None

    def groepsleden(self):
        """Alle cellen die tot dezelfde samengevoegde entiteit behoren."""
        if not self.groep:
            return ZaalplanCel.objects.filter(pk=self.pk)
        return ZaalplanCel.objects.filter(zaalplan=self.zaalplan, groep=self.groep)

    def primary_cel(self):
        """De hoofdcel van de groep (linksboven); draagt label/prijs/selectie."""
        if not self.groep:
            return self
        return self.groepsleden().order_by("rij", "kolom").first()

    @property
    def is_primary(self):
        return self.primary_cel().pk == self.pk

    def is_bezet(self, exclude_inschrijving_id=None):
        primary = self.primary_cel()
        if primary.cel_type != CelType.TAFEL:
            return False
        qs = StandhouderTafelKeuze.objects.filter(
            cel=primary,
            inschrijving__status__in=StandhouderInschrijvingStatus.BEZET,
        )
        if exclude_inschrijving_id:
            qs = qs.exclude(inschrijving_id=exclude_inschrijving_id)
        return qs.exists()

    def ontgroepeer(self):
        """Maak van een samengevoegde cel weer losse cellen."""
        if not self.groep:
            return
        self.groepsleden().update(groep=None)


class StandhouderVraag(models.Model):
    evenement = models.ForeignKey(
        Evenement,
        on_delete=models.CASCADE,
        related_name="standhouder_vragen",
        verbose_name=_("Evenement"),
    )
    tekst = models.CharField(max_length=200, verbose_name=_("Vraag"))
    vraag_type = models.CharField(
        max_length=10,
        choices=VraagType.CHOICES,
        default=VraagType.BOOLEAN,
        verbose_name=_("Type"),
    )
    opties = models.TextField(
        blank=True,
        verbose_name=_("Opties (één per regel, voor keuzelijst)"),
    )
    verplicht = models.BooleanField(default=False, verbose_name=_("Verplicht"))
    volgorde = models.SmallIntegerField(default=0, verbose_name=_("Volgorde"))
    prijs_toeslag = MoneyField(
        verbose_name=_("Prijs toeslag"),
        default_currency="EUR",
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        help_text=_("Wordt toegevoegd bij een positief antwoord (ja/checkbox/select)."),
    )
    is_borg = models.BooleanField(
        default=False,
        verbose_name=_("Is borg"),
        help_text=_(
            "Markeer als borg: bij een positief antwoord verschijnt op het overzicht "
            "een melding dat deze borg niet wordt terugbetaald bij annulatie."
        ),
    )
    min_tafels = models.PositiveIntegerField(
        blank=True,
        null=True,
        verbose_name=_("Min. aantal tafels"),
        help_text=_("Vraag alleen tonen als minstens dit aantal tafels gekozen is."),
    )
    max_tafels = models.PositiveIntegerField(
        blank=True,
        null=True,
        verbose_name=_("Max. aantal tafels"),
        help_text=_("Vraag alleen tonen als hoogstens dit aantal tafels gekozen is."),
    )

    history = HistoricalRecords(verbose_name=_("Geschiedenis"))

    class Meta:
        verbose_name = _("Standhouder vraag")
        verbose_name_plural = _("Standhouder vragen")
        ordering = ["volgorde", "id"]

    def __str__(self):
        return self.tekst

    @property
    def opties_lijst(self):
        return [o.strip() for o in self.opties.split("\n") if o.strip()]


class StandhouderInschrijving(models.Model):
    evenement = models.ForeignKey(
        Evenement,
        on_delete=models.CASCADE,
        related_name="standhouder_inschrijvingen",
        verbose_name=_("Evenement"),
    )
    bedrijfsnaam = models.CharField(max_length=100, verbose_name=_("Bedrijfsnaam"), blank=True, default="")
    naam = models.CharField(max_length=100, verbose_name=_("Naam"), blank=True, default="")
    email = models.EmailField(verbose_name=_("Email"), blank=True, default="")
    telefoon = models.CharField(max_length=20, verbose_name=_("Telefoon"), blank=True, default="")
    factuur = models.BooleanField(default=False, verbose_name=_("Factuur gewenst"))
    opmerkingen = models.TextField(blank=True, verbose_name=_("Opmerkingen"))
    status = models.CharField(
        max_length=20,
        choices=StandhouderInschrijvingStatus.CHOICES,
        default=StandhouderInschrijvingStatus.CONCEPT,
        verbose_name=_("Status"),
    )
    totaal_bedrag = MoneyField(
        verbose_name=_("Totaalbedrag"),
        default_currency="EUR",
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
    )
    aantal_tafels_manueel = models.PositiveIntegerField(
        verbose_name=_("Aantal tafels (zonder zaalplan)"),
        null=True,
        blank=True,
    )
    payment = models.ForeignKey(
        Payment,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        verbose_name=_("Betaling"),
    )
    aangemaakt_op = models.DateTimeField(auto_now_add=True, verbose_name=_("Aangemaakt op"))
    bijgewerkt_op = models.DateTimeField(auto_now=True, verbose_name=_("Bijgewerkt op"))

    history = HistoricalRecords(verbose_name=_("Geschiedenis"))

    class Meta:
        verbose_name = _("Standhouder inschrijving")
        verbose_name_plural = _("Standhouder inschrijvingen")
        ordering = ["-aangemaakt_op"]

    def __str__(self):
        return f"{self.bedrijfsnaam} - {self.evenement.titel}"

    @property
    def gekozen_tafels(self):
        return ZaalplanCel.objects.filter(
            standhoudertafelkeuze_set__inschrijving=self
        ).order_by("rij", "kolom")

    @property
    def zaalplan_actief(self):
        return self.evenement.standhouder_zaalplan_actief

    @property
    def aantal_tafels(self):
        if self.zaalplan_actief:
            return self.gekozen_tafels.count()
        return self.aantal_tafels_manueel or 0

    @property
    def borg_bedrag(self):
        from decimal import Decimal

        totaal = Decimal("0")
        for antwoord in self.antwoorden.select_related("vraag"):
            if antwoord.vraag.is_borg and antwoord.heeft_toeslag():
                totaal += antwoord.vraag.prijs_toeslag.amount
        return totaal

    @property
    def heeft_borg(self):
        return self.borg_bedrag > 0

    def bereken_totaal(self):
        from decimal import Decimal

        totaal = Decimal("0")
        if self.zaalplan_actief:
            for cel in self.gekozen_tafels:
                totaal += cel.effectieve_prijs.amount
        else:
            aantal = self.aantal_tafels_manueel or 0
            totaal += aantal * self.evenement.standhouder_prijs_per_tafel.amount

        for antwoord in self.antwoorden.select_related("vraag"):
            if antwoord.heeft_toeslag():
                totaal += antwoord.vraag.prijs_toeslag.amount

        self.totaal_bedrag = totaal
        return totaal

    def valideer_tafels_beschikbaar(self):
        from pokemon.standhouder_wizard import valideer_max_tafels

        if self.zaalplan_actief:
            valideer_max_tafels(self.evenement, self.aantal_tafels)
            for cel in self.gekozen_tafels:
                if cel.cel_type != CelType.TAFEL:
                    raise ValueError(f"Cel {cel.display_label} is geen tafel.")
                if cel.is_bezet(exclude_inschrijving_id=self.pk):
                    raise ValueError(f"Tafel {cel.display_label} is niet meer beschikbaar.")
        else:
            valideer_max_tafels(self.evenement, self.aantal_tafels_manueel or 0)

    def verstuur_bevestiging(self, voorlopig=False):
        tafels = list(self.gekozen_tafels)
        antwoorden = list(self.antwoorden.select_related("vraag").order_by("vraag__volgorde"))
        user_sent = False

        if voorlopig:
            template = "pokemon/email/confirmation-mail-standhouder-voorlopig.html"
            subject = _("ChudartZ Collectibles | Voorlopige standhouder-aanvraag ontvangen")
            admin_subject = "Standhouder aanvraag (voorlopig)"
        else:
            template = "pokemon/email/confirmation-mail-standhouder.html"
            subject = _("ChudartZ Collectibles | Standhouder inschrijving bevestigd")
            admin_subject = "Standhouder inschrijving (betaald)"

        try:
            user_body = render_to_string(
                template,
                {
                    "inschrijving": self,
                    "evenement": self.evenement,
                    "tafels": tafels,
                    "antwoorden": antwoorden,
                },
            )
            email = EmailMessage(
                subject,
                user_body,
                formataddr(("Evenementen | Chudartz", settings.EMAIL_HOST_USER)),
                [self.email],
            )
            email.content_subtype = "html"
            email.send()
            user_sent = True
        except Exception:
            logger.exception(
                "Kon bevestigingsmail niet versturen naar standhouder voor inschrijving %s",
                self.pk,
            )

        try:
            if self.zaalplan_actief:
                tafels_regel = f"Tafels: {', '.join(c.display_label for c in tafels)}"
            else:
                tafels_regel = f"Aantal tafels: {self.aantal_tafels_manueel or 0}"

            admin_lines = [
                f"Evenement: {self.evenement.titel}",
                f"Status: {self.get_status_display()}",
                f"Bedrijfsnaam: {self.bedrijfsnaam}",
                f"Naam: {self.naam}",
                f"Email: {self.email}",
                f"Telefoon: {self.telefoon}",
                tafels_regel,
                f"Totaalbedrag: €{self.totaal_bedrag}",
            ]
            if self.factuur:
                admin_lines.append("Factuur gewenst: Ja")
            for antwoord in antwoorden:
                admin_lines.append(f"{antwoord.vraag.tekst}: {antwoord.weergave()}")
            if self.heeft_borg:
                admin_lines.append(
                    f"Borg: €{self.borg_bedrag} (niet terugbetaalbaar bij annulatie)"
                )
            if self.opmerkingen:
                admin_lines.append(f"Opmerkingen: {self.opmerkingen}")

            send_mail(
                admin_subject,
                "\n".join(admin_lines),
                formataddr(("Contact | ChudartZ", settings.EMAIL_HOST_USER)),
                [settings.EMAIL_HOST_USER],
                fail_silently=False,
            )
        except Exception:
            logger.exception(
                "Kon admin-notificatie niet versturen voor standhouder-inschrijving %s",
                self.pk,
            )

        return user_sent


class StandhouderTafelKeuze(models.Model):
    inschrijving = models.ForeignKey(
        StandhouderInschrijving,
        on_delete=models.CASCADE,
        related_name="tafel_keuzes",
        verbose_name=_("Inschrijving"),
    )
    cel = models.ForeignKey(
        ZaalplanCel,
        on_delete=models.CASCADE,
        related_name="standhoudertafelkeuze_set",
        verbose_name=_("Cel"),
    )

    history = HistoricalRecords(verbose_name=_("Geschiedenis"))

    class Meta:
        verbose_name = _("Tafelkeuze")
        verbose_name_plural = _("Tafelkeuzes")
        unique_together = ("inschrijving", "cel")

    def __str__(self):
        return f"{self.inschrijving} - {self.cel.display_label}"


class StandhouderVraagAntwoord(models.Model):
    inschrijving = models.ForeignKey(
        StandhouderInschrijving,
        on_delete=models.CASCADE,
        related_name="antwoorden",
        verbose_name=_("Inschrijving"),
    )
    vraag = models.ForeignKey(
        StandhouderVraag,
        on_delete=models.CASCADE,
        verbose_name=_("Vraag"),
    )
    antwoord = models.TextField(verbose_name=_("Antwoord"))

    history = HistoricalRecords(verbose_name=_("Geschiedenis"))

    class Meta:
        verbose_name = _("Standhouder vraag antwoord")
        verbose_name_plural = _("Standhouder vraag antwoorden")
        unique_together = ("inschrijving", "vraag")

    def __str__(self):
        return f"{self.vraag.tekst}: {self.antwoord}"

    def weergave(self):
        if self.vraag.vraag_type in (VraagType.BOOLEAN, VraagType.CHECKBOX):
            return _("Ja") if self.antwoord in ("true", "1", "on", "yes") else _("Nee")
        return self.antwoord

    def heeft_toeslag(self):
        if not self.vraag.prijs_toeslag:
            return False
        if self.vraag.vraag_type in (VraagType.BOOLEAN, VraagType.CHECKBOX):
            return self.antwoord in ("true", "1", "on", "yes")
        if self.vraag.vraag_type == VraagType.SELECT:
            return bool(self.antwoord)
        return False


class GateDevice(models.Model):
    """Hardware gate scanner authenticated by a device API key."""

    name = models.CharField(max_length=100, verbose_name=_("Name"))
    is_active = models.BooleanField(default=True, verbose_name=_("Active"))
    api_key_prefix = models.CharField(
        max_length=8,
        editable=False,
        verbose_name=_("API key prefix"),
        help_text=_("First 8 characters of the key, for identification."),
    )
    api_key_hash = models.CharField(max_length=255, editable=False, verbose_name=_("API key hash"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created at"))
    last_used_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Last used at"))

    class Meta:
        verbose_name = _("Gate device")
        verbose_name_plural = _("Gate devices")

    def __str__(self):
        return self.name

    @staticmethod
    def generate_api_key():
        return secrets.token_urlsafe(32)

    def set_api_key(self, raw_key: str):
        from django.contrib.auth.hashers import make_password

        self.api_key_hash = make_password(raw_key)
        self.api_key_prefix = raw_key[:8]

    def check_api_key(self, raw_key: str) -> bool:
        from django.contrib.auth.hashers import check_password

        return check_password(raw_key, self.api_key_hash)

    @classmethod
    def authenticate(cls, raw_key: str):
        if not raw_key or len(raw_key) < 8:
            return None
        prefix = raw_key[:8]
        for device in cls.objects.filter(is_active=True, api_key_prefix=prefix):
            if device.check_api_key(raw_key):
                return device
        return None

    def touch_last_used(self):
        self.last_used_at = timezone.now()
        self.save(update_fields=["last_used_at"])