from django.contrib import messages
from django.contrib import admin
from django.shortcuts import get_object_or_404, redirect
from django.utils.translation import gettext as _
from simple_history.admin import SimpleHistoryAdmin
from unfold.admin import ModelAdmin
from unfold.contrib.filters.admin import RelatedDropdownFilter
from unfold.contrib.inlines.admin import StackedInline
from unfold.decorators import action, display

from .models import *

@admin.register(Evenement) # todo generate qr code with link to event page
class EvenementAdmin(SimpleHistoryAdmin, ModelAdmin):
    list_display = ('titel', 'participants_count', 'remaining_tickets', 'is_sold_out')
    ordering = ('id',)
    exclude = ('tickets',)

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