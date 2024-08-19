from django.utils.translation import gettext_lazy as _
from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name="index"),

    path(_('dartschool'), views.dartschool, name="dartschool"),
    path(_('dartschool/inschrijven/'), views.inschrijven_dartschool, name='inschrijven_dartschool'),

    path(_('tornooien'), views.tornooien, name="tornooien"),
    path(_('tornooien/<slug:slug>/'), views.tornooi, name='tornooi'),
    path(_('tornooien/<slug:slug>/inschrijven'), views.inschrijven_tornooi, name='inschrijven_tornooi'),
    path(_('tornooien/<slug:slug>/inschrijven/success'), views.inschrijven_tornooi_success, name='inschrijven_tornooi_success'),

    path(_('over-ons'), views.over_ons, name="over_ons"),
    path(_('terms-of-service'), views.terms_of_service, name="terms_of_service"),
    path(_('privacy-policy'), views.privacy_policy, name="privacy_policy"),
    path(_('contact'), views.contact, name='contact'),

    path(_('darts/scanner/'), views.scanner),
    path(_('mollie-webhook/'), views.mollie_webhook),
]