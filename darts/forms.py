from django import forms
from  .models import Beurtkaart, SkillLevel
from phonenumber_field.formfields import PhoneNumberField

class ContactForm(forms.Form):
    name = forms.CharField(max_length=100)
    email = forms.EmailField()
    phone = forms.CharField(max_length=15, required=False)
    subject = forms.CharField(max_length=100)
    message = forms.CharField()

class ToernooiForm(forms.Form):
    voornaam = forms.CharField(max_length=100, required=True, widget=forms.TextInput(attrs={
        'placeholder': 'Voornaam',
        'class': 'form-control',
    }))
    
    achternaam = forms.CharField(max_length=100, required=True, widget=forms.TextInput(attrs={
        'placeholder': 'Achternaam',
        'class': 'form-control',
    }))
    
    geboortejaar = forms.IntegerField(min_value=1900, max_value=2100, required=True, widget=forms.NumberInput(attrs={
        'placeholder': 'Geboortejaar',
        'class': 'form-control',
    }))
    
    email = forms.EmailField(max_length=254, required=True, widget=forms.EmailInput(attrs={
        'placeholder': 'Email',
        'class': 'form-control',
    }))
    
    gsm = PhoneNumberField(required=True, widget=forms.TextInput(attrs={
        'placeholder': 'Gsm-nummer',
        'class': 'form-control',
    }))
    
    straatnaam = forms.CharField(max_length=100, required=True, widget=forms.TextInput(attrs={
        'placeholder': 'Straatnaam',
        'class': 'form-control',
    }))
    
    nummer = forms.CharField(max_length=6, required=True, widget=forms.TextInput(attrs={
        'placeholder': 'Nummer',
        'class': 'form-control',
    }))
    
    postcode = forms.IntegerField(min_value=0, max_value=9999, required=True, widget=forms.NumberInput(attrs={
        'placeholder': 'Postcode',
        'class': 'form-control',
    }))
    
    stad = forms.CharField(max_length=40, required=True, widget=forms.TextInput(attrs={
        'placeholder': 'Stad',
        'class': 'form-control',
    }))
    
    ticket = forms.CharField(required=True)


class BeurtkaartForm(forms.Form):
    beurtkaart = forms.ModelChoiceField(queryset=Beurtkaart.objects.all())
    code = forms.CharField(max_length=6)


class CodeForm(forms.Form):
    voornaam = forms.CharField(max_length=100)
    achternaam = forms.CharField(max_length=100)
    email = forms.EmailField(max_length=254)
