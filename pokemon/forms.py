from django import forms

class ContactForm(forms.Form):
    name = forms.CharField(max_length=100)
    email = forms.EmailField()
    phone = forms.CharField(max_length=15, required=False)
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

    telefoon = forms.CharField(max_length=20, required=True, widget=forms.TextInput(attrs={
        'placeholder': 'Gsm-nummer',
        'class': 'form-control',
    }))

    aantal_tafels = forms.IntegerField(min_value=1, required=True, widget=forms.NumberInput(attrs={
        'placeholder': 'Aantal plaatsen ',
        'class': 'form-control',
    }))

    factuur = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={
        'class': 'form-check-input',
    }))

    electriciteit = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={
        'class': 'form-check-input',
    }))

    tafel = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={
        'class': 'form-check-input',
    }))

    opmerkingen = forms.CharField(required=False, widget=forms.Textarea(attrs={
        'placeholder': 'Opmerkingen',
        'class': 'form-control',
        'rows': 5
    }))
