from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name="index"),

    path('dartschool', views.dartschool, name="dartschool"),
    path('dartschool/inschrijven/', views.inschrijven_dartschool, name='inschrijven dartschool'),

    path('tornooien', views.tornooien, name="tornooien"),
    path('tornooien/<slug:slug>/', views.tornooi, name='tornooi'),
    path('tornooien/<slug:slug>/inschrijven', views.inschrijven_tornooi, name='inschrijven tornooi'),
    path('tornooien/<slug:slug>/inschrijven/success', views.inschrijven_tornooi_success, name='inschrijven tornooi'),

    path('over-ons', views.about, name="over ons"),
    path('terms-of-service', views.terms_of_service, name="terms of service"),
    path('privacy-policy', views.privacy_policy, name="privacy policy"),
    path('contact', views.contact, name='contact'),

    path("darts/scanner/", views.scanner),
    path("mollie-webhook/", views.mollie_webhook),
]