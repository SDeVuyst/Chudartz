from django.contrib import messages
from django.contrib import admin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.translation import gettext as _
from simple_history.admin import SimpleHistoryAdmin
from unfold.admin import ModelAdmin
from unfold.contrib.filters.admin import RelatedDropdownFilter
from unfold.contrib.inlines.admin import StackedInline
from unfold.decorators import action, display
from django.utils.safestring import mark_safe

from .models import *

class TicketInline(StackedInline):
    model = Ticket
    verbose_name = _("Evenement Ticket")
    verbose_name_plural = _("Evenement Tickets")

@admin.register(Ticket)
class TicketAdmin(SimpleHistoryAdmin, ModelAdmin):
    list_display = ('titel', 'price', 'participants_count', 'remaining_tickets', 'is_sold_out')
    ordering = ("id",)

    search_fields = ('titel', 'beschrijving')

    @display(
        description=_("Sold out"),
        label={
            True: "danger",
            False: "success"
        }
    )
    def is_sold_out(self, obj):
        label = _("Sold out!") if obj.is_sold_out else _("Available")
        return obj.is_sold_out, label
    

@admin.register(Partner)
class PartnerAdmin(SimpleHistoryAdmin, ModelAdmin):
    list_display = ('name',)
    ordering = ('id',)

    search_fields = ('name', )

@admin.register(Participant)
class ParticipantAdmin(SimpleHistoryAdmin, ModelAdmin):
    list_display = ['mail', 'evenement', 'attendance']
    ordering = ('id',)

    @display(description=_("Evenement"))
    def evenement(self, obj):
        return mark_safe('<a href="{}">{}</a>'.format(
            reverse("admin:pokemon_evenement_change", args=(obj.ticket.event.pk,)),
            obj.ticket.event.titel
        ))

    @display(
        description=_('Status van Betaling'), 
        label={
            PaymentStatus.PAID: "success",
            PaymentStatus.OPEN: "warning",
            PaymentStatus.CANCELED: "danger",
            PaymentStatus.EXPIRED: "danger",
            PaymentStatus.FAILED: "danger",
        },
        header=True,
    )
    def payment_status(self, obj):
        if obj.payment is None: return PaymentStatus.OPEN

        return obj.payment.status
    
    @display(
        description=_("Attended"),
        label={
            True: "success",
            False: "danger"
        }
    )
    def attendance(self, obj):
        label = _("Yes") if obj.attended else _("No")
        return obj.attended, label
    

    search_fields = ('mail',)
    list_filter = (
        ('attended', admin.BooleanFieldListFilter),
        ('ticket', RelatedDropdownFilter),
    )

    list_filter_submit = True
    actions_detail = ["generate_ticket", "send_confirmation_mail"]
    
    @action(description=_("Genereer Ticket"))
    def generate_ticket(modeladmin, request, object_id: int):
        participant = get_object_or_404(Participant, pk=object_id)

        return participant.generate_ticket()

    @action(description=_("Stuur bevestiging mail"))
    def send_confirmation_mail(modeladmin, request, object_id: int):
        participant = get_object_or_404(Participant, pk=object_id)

        try:
            participant.payment.send_mail()
            messages.success(request, _("Bevestigings mail is verstuurd!"))
        
        except Exception as e:
            messages.error(request, _("Bevestigings mail versturen mislukt. Error: ") + str(e))
        

        return redirect(reverse('admin:pokemon_participant_change', args=[participant.pk]))


@admin.register(Evenement)
class EvenementAdmin(SimpleHistoryAdmin, ModelAdmin):
    list_display = ('titel', 'participants_count', 'remaining_tickets', 'is_sold_out')
    ordering = ('id',)
    exclude = ('tickets',)
    inlines = [
        TicketInline
    ]
    actions_detail = ["generate_qr_code",]

    search_fields = ('titel', 'beschrijving', 'start_datum', 'einde_datum', 'locatie_lang')

    @display(
        description=_("Uitverkocht"),
        label={
            True: "danger",
            False: "success"
        }
    )
    def is_sold_out(self, obj):
        label = _("Sold out!") if obj.is_sold_out else _("Available")
        return obj.is_sold_out, label

    def view_on_site(self, obj):
        return obj.get_absolute_url()
    
    @action(description=_("Genereer QR Code"))
    def generate_qr_code(modeladmin, request, object_id: int):
        evenement = get_object_or_404(Evenement, pk=object_id)

        url = request.build_absolute_uri(evenement.get_absolute_url())
        qr = qrcode.make(url)

        # Save the QR code to an in-memory file
        buffer = BytesIO()
        qr.save(buffer, format="PNG")
        buffer.seek(0)

        # Create an HTTP response with the image
        response = HttpResponse(buffer, content_type="image/png")
        response['Content-Disposition'] = f'attachment; filename=qr_{evenement.titel}.png'
        return response      
    

@admin.register(TicketEigenschap)
class TicketEigenschapAdmin(SimpleHistoryAdmin, ModelAdmin):
    list_display = ('tekst', )
