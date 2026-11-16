from django import forms
from django.utils.translation import gettext_lazy as _
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

class DartskampForm(forms.Form):
    voornaam = forms.CharField(label=_('Voornaam'), max_length=100, required=True, widget=forms.TextInput(attrs={
        'placeholder': _('Voornaam'),
        'class': 'form-control',
    }))
    
    achternaam = forms.CharField(label=_('Achternaam'), max_length=100, required=True, widget=forms.TextInput(attrs={
        'placeholder': _('Achternaam'),
        'class': 'form-control',
    }))
    
    geboortejaar = forms.IntegerField(label=_('Geboortejaar'), min_value=1900, max_value=2100, required=True, widget=forms.NumberInput(attrs={
        'placeholder': _('Geboortejaar'),
        'class': 'form-control',
    }))
    
    email = forms.EmailField(label=_('Email'), max_length=254, required=True, widget=forms.EmailInput(attrs={
        'placeholder': _('Email'),
        'class': 'form-control',
    }))
    
    gsm = PhoneNumberField(label=_('GSM'), required=True, widget=forms.TextInput(attrs={
        'placeholder': _('Gsm-nummer'),
        'class': 'form-control',
    }))
    
    straatnaam = forms.CharField(label=_('Straatnaam'), max_length=100, required=True, widget=forms.TextInput(attrs={
        'placeholder': _('Straatnaam'),
        'class': 'form-control',
    }))
    
    nummer = forms.CharField(label=_('Nummer'), max_length=6, required=True, widget=forms.TextInput(attrs={
        'placeholder': _('Nummer'),
        'class': 'form-control',
    }))
    
    postcode = forms.IntegerField(label=_('Postcode'), min_value=0, max_value=9999, required=True, widget=forms.NumberInput(attrs={
        'placeholder': _('Postcode'),
        'class': 'form-control',
    }))
    
    stad = forms.CharField(label=_('Stad'), max_length=40, required=True, widget=forms.TextInput(attrs={
        'placeholder': _('Stad'),
        'class': 'form-control',
    }))


class DartskampBetalenForm(forms.Form):
    terms_voorwaarden = forms.BooleanField(required=True)
    terms_voogd = forms.BooleanField(required=False)

    def __init__(self, *args, kamp=None, **kwargs):
        super().__init__(*args, **kwargs)
        if kamp is not None and kamp.vereist_voogd_toestemming:
            self.fields['terms_voogd'].required = True


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
