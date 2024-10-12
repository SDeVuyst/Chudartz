from django import forms
from phonenumber_field.formfields import PhoneNumberField

class ContactForm(forms.Form):
    name = forms.CharField(max_length=100)
    email = forms.EmailField()
    subject = forms.CharField(max_length=100)
    message = forms.CharField()


class StandhouderForm(forms.Form):
    bedrijfsnaam = forms.CharField(max_length=100, required=True, widget=forms.TextInput(attrs={
        'placeholder': 'Bedrijfsnaam',
        'class': 'form-control',
    }))

    naam = forms.CharField(max_length=100, required=True, widget=forms.TextInput(attrs={
        'placeholder': 'Naam',
        'class': 'form-control',
    }))

    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={
        'placeholder': 'Email',
        'class': 'form-control',
    }))

    telefoon = PhoneNumberField(required=True, widget=forms.TextInput(attrs={
        'placeholder': 'Gsm-nummer',
        'class': 'form-control',
    }))

    aantal_tafels = forms.IntegerField(required=True, widget=forms.NumberInput(attrs={
        'placeholder': 'Aantal plaatsen ',
        'class': 'form-control',
    }))

    factuur = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={
        'class': 'form-check-input',
    }))

    elektriciteit = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={
        'class': 'form-check-input',
    }))

    tafel/stoel = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={
        'class': 'form-check-input',
    }))


    opmerkingen = forms.CharField(required=False, widget=forms.Textarea(attrs={
        'placeholder': 'Opmerkingen',
        'class': 'form-control',
        'rows': 5
    }))
