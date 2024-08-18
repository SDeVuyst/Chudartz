from io import BytesIO

from django.contrib import admin
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext as _
from simple_history.admin import SimpleHistoryAdmin
from unfold.admin import ModelAdmin
from unfold.contrib.filters.admin import RelatedDropdownFilter
from unfold.contrib.inlines.admin import StackedInline
from unfold.decorators import action, display

from .models import *


# INLINES #
class TicketInline(StackedInline):
    model = Ticket
    verbose_name = _("Evenement Ticket")
    verbose_name_plural = _("Evenement Tickets")


# FILTERS #


# MODELS #
@admin.register(Evenement)
class EventAdmin(SimpleHistoryAdmin, ModelAdmin):
    list_display = ('titel', 'participants_count', 'remaining_tickets', 'is_sold_out')
    ordering = ('id',)
    exclude = ('tickets',)

    search_fields = ('titel', 'beschrijving', 'start_datum', 'einde_datum', 'locatie_lang')
    inlines = [
        TicketInline
    ]

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


@admin.register(Participant)
class ParticipantAdmin(SimpleHistoryAdmin, ModelAdmin):
    list_display = ['voornaam', 'achternaam', 'payment_status', 'attendance']
    ordering = ('id',)

    @display(
        description=_('Payment Status'), 
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
    

    search_fields = ('voornaam', 'achternaam', 'email')
    list_filter = (
        ('attended', admin.BooleanFieldListFilter),
        ('ticket', RelatedDropdownFilter),
    )

    list_filter_submit = True
    actions_detail = ["generate_ticket", "generate_qr_code"]

    @action(description=_("Generate QR-code"))
    def generate_qr_code(modeladmin, request, object_id: int):

        participant = get_object_or_404(Participant, pk=object_id)

        img = participant.generate_qr_code()
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)

        response = HttpResponse(buffer, content_type='image/png')
        response['Content-Disposition'] = f'attachment; filename=ticket_{object_id}_qr.png'
        return response
    
    @action(description=_("Generate Ticket"))
    def generate_ticket(modeladmin, request, object_id: int):
        participant = get_object_or_404(Participant, pk=object_id)

        return participant.generate_ticket()



@admin.register(Payment)
class PaymentAdmin(SimpleHistoryAdmin, ModelAdmin):
    actions_detail = ["generate_ticket",]

    @action(description=_("Generate Ticket"))
    def generate_ticket(modeladmin, request, object_id: int):
        p = get_object_or_404(Payment, pk=object_id)

        return p.generate_ticket()


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