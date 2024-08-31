from django import forms
from  .models import Beurtkaart, SkillLevel

class ContactForm(forms.Form):
    name = forms.CharField(max_length=100)
    email = forms.EmailField()
    subject = forms.CharField(max_length=100)
    message = forms.CharField()

class TornooiForm(forms.Form):
    voornaam = forms.CharField(max_length=100)
    achternaam = forms.CharField(max_length=100)
    email = forms.EmailField(max_length=254)
    straatnaam = forms.CharField(max_length=100)
    nummer = forms.CharField(max_length=6)
    postcode = forms.IntegerField()
    stad = forms.CharField(max_length=40)
    niveau = forms.ChoiceField(choices=SkillLevel.CHOICES)
    ticket = forms.CharField()

class BeurtkaartForm(forms.Form):
    beurtkaart = forms.ModelChoiceField(queryset=Beurtkaart.objects.all())
    code = forms.CharField(max_length=6)

class CodeForm(forms.Form):
    voornaam = forms.CharField(max_length=100)
    achternaam = forms.CharField(max_length=100)
    email = forms.EmailField(max_length=254)