from django import forms
from  .models import Beurtkaart, LeagueDivisie, SkillLevel
from phonenumber_field.formfields import PhoneNumberField
from .utils.league_tables import (
    blank_if_default,
    default_stand_html,
    default_uitslagen_html,
    is_default_league_table,
)

class ContactForm(forms.Form):
    name = forms.CharField(max_length=100)
    email = forms.EmailField()
    phone = forms.CharField(max_length=18, required=False)
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


class LeagueDivisieForm(forms.ModelForm):
    class Meta:
        model = LeagueDivisie
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.is_bound:
            return
        uitslagen = self.instance.uitslagen
        if not uitslagen or is_default_league_table(uitslagen, 'uitslagen'):
            self.initial['uitslagen'] = default_uitslagen_html()
        stand = self.instance.stand
        if not stand or is_default_league_table(stand, 'stand'):
            self.initial['stand'] = default_stand_html()

    def clean_uitslagen(self):
        return blank_if_default(self.cleaned_data.get('uitslagen'), 'uitslagen')

    def clean_stand(self):
        return blank_if_default(self.cleaned_data.get('stand'), 'stand')
