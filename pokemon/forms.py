from django import forms

from pokemon.models import StandhouderInschrijving, StandhouderVraag, VraagType


class ContactForm(forms.Form):
    name = forms.CharField(max_length=100)
    email = forms.EmailField()
    phone = forms.CharField(max_length=18, required=False)
    subject = forms.CharField(max_length=100)
    message = forms.CharField()


class StandhouderGegevensForm(forms.ModelForm):
    class Meta:
        model = StandhouderInschrijving
        fields = ["bedrijfsnaam", "naam", "email", "telefoon", "opmerkingen"]
        widgets = {
            "bedrijfsnaam": forms.TextInput(attrs={
                "placeholder": "Bedrijfsnaam",
                "class": "form-control",
            }),
            "naam": forms.TextInput(attrs={
                "placeholder": "Naam",
                "class": "form-control",
            }),
            "email": forms.EmailInput(attrs={
                "placeholder": "Email",
                "class": "form-control",
            }),
            "telefoon": forms.TextInput(attrs={
                "placeholder": "Gsm-nummer",
                "class": "form-control",
            }),
            "opmerkingen": forms.Textarea(attrs={
                "placeholder": "Opmerkingen",
                "class": "form-control",
                "rows": 5,
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in ("bedrijfsnaam", "naam", "email", "telefoon"):
            self.fields[field_name].required = True


class StandhouderTafelsForm(forms.Form):
    tafels = forms.MultipleChoiceField(required=True)

    def clean_tafels(self):
        tafels = self.cleaned_data.get("tafels", [])
        if not tafels:
            raise forms.ValidationError("Selecteer minstens één tafel.")
        return tafels


def build_standhouder_vragen_form(vragen, aantal_tafels):
    class StandhouderVragenForm(forms.Form):
        pass

    for vraag in vragen:
        if vraag.min_tafels and aantal_tafels < vraag.min_tafels:
            continue
        if vraag.max_tafels and aantal_tafels > vraag.max_tafels:
            continue

        field_name = f"vraag_{vraag.pk}"
        field_kwargs = {
            "label": vraag.tekst,
            "required": vraag.verplicht,
        }

        if vraag.vraag_type == VraagType.TEKST:
            field = forms.CharField(
                widget=forms.TextInput(attrs={"class": "form-control"}),
                **field_kwargs,
            )
        elif vraag.vraag_type == VraagType.TEXTAREA:
            field = forms.CharField(
                widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
                **field_kwargs,
            )
        elif vraag.vraag_type == VraagType.BOOLEAN:
            field = forms.BooleanField(
                widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
                required=False,
                label=vraag.tekst,
            )
            if vraag.verplicht:
                field.required = True
        elif vraag.vraag_type == VraagType.CHECKBOX:
            field = forms.BooleanField(
                widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
                required=vraag.verplicht,
                label=vraag.tekst,
            )
        elif vraag.vraag_type == VraagType.NUMBER:
            field = forms.IntegerField(
                widget=forms.NumberInput(attrs={"class": "form-control"}),
                **field_kwargs,
            )
        elif vraag.vraag_type == VraagType.SELECT:
            field = forms.ChoiceField(
                choices=[("", "---------")] + [(o, o) for o in vraag.opties_lijst],
                widget=forms.Select(attrs={"class": "form-control"}),
                **field_kwargs,
            )
        else:
            continue

        StandhouderVragenForm.base_fields[field_name] = field
        StandhouderVragenForm.base_fields[field_name].vraag = vraag

    return StandhouderVragenForm


def serialize_vraag_antwoord(vraag, value):
    if vraag.vraag_type in (VraagType.BOOLEAN, VraagType.CHECKBOX):
        return "true" if value else "false"
    return str(value) if value is not None else ""
