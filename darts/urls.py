from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name="index"),
    path('dartschool', views.dartschool, name="dartschool"),
    path('dartstornooien', views.dartstornooien, name="dartstornooien"),
    path('tornooi/<slug:slug>/', views.tornooi, name='tornooi'),
    path('about', views.about, name="about"),
    path('terms-of-service', views.terms_of_service, name="terms of service"),
    path('privacy-policy', views.privacy_policy, name="privacy policy"),
    path('contact', views.contact, name='contact'),
]