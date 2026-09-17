from django import forms
from django.utils.translation import gettext_lazy as _
import json

from pokemon.models import StandhouderInschrijving, StandhouderVraag, VraagType


class TicketGegevensForm(forms.Form):
    email = forms.EmailField(
        label=_("E-mailadres"),
        widget=forms.EmailInput(attrs={"class": "form-control", "placeholder": "E-mailadres"}),
    )
    first_name = forms.CharField(
        label=_("Voornaam"),
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Voornaam (optioneel)"}),
    )
    last_name = forms.CharField(
        label=_("Achternaam"),
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Achternaam (optioneel)"}),
    )


class TicketOverzichtForm(forms.Form):
    kortingscode = forms.CharField(
        label=_("Kortingscode"),
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Kortingscode (optioneel)",
            "autocomplete": "off",
        }),
    )
    terms_voorwaarden = forms.BooleanField(required=True)
    terms_privacy = forms.BooleanField(required=True)
    terms_disclaimer = forms.BooleanField(required=True)
    terms_huisreglement = forms.BooleanField(required=True)


class StandhouderOverzichtForm(forms.Form):
    terms_voorwaarden = forms.BooleanField(required=True)
    terms_privacy = forms.BooleanField(required=True)
    terms_wettelijk = forms.BooleanField(required=True)


class ContactForm(forms.Form):
    name = forms.CharField(max_length=100)
    email = forms.EmailField()
    phone = forms.CharField(max_length=18, required=False)
    subject = forms.CharField(max_length=100)
    message = forms.CharField()


class StandhouderGegevensForm(forms.ModelForm):
    class Meta:
        model = StandhouderInschrijving
        fields = [
            "bedrijfsnaam",
            "naam",
            "email",
            "telefoon",
            "factuur",
            "btw_of_kvk_nummer",
            "opmerkingen",
        ]
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
            "factuur": forms.CheckboxInput(attrs={
                "class": "form-check-input",
            }),
            "btw_of_kvk_nummer": forms.TextInput(attrs={
                "placeholder": "BTW-nummer",
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
        self.fields["btw_of_kvk_nummer"].required = False

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("factuur"):
            value = (cleaned.get("btw_of_kvk_nummer") or "").strip()
            cleaned["btw_of_kvk_nummer"] = value
            if not value:
                self.add_error(
                    "btw_of_kvk_nummer",
                    _("Dit veld is verplicht wanneer u een factuur wenst."),
                )
        return cleaned


class StandhouderTafelsForm(forms.Form):
    tafels = forms.MultipleChoiceField(required=True)

    def clean_tafels(self):
        tafels = self.cleaned_data.get("tafels", [])
        if not tafels:
            raise forms.ValidationError("Selecteer minstens één tafel.")
        return tafels


def _multiselect_choice_label(optie):
    label = optie["label"]
    prijs = optie.get("prijs")
    if prijs is not None and prijs > 0:
        return f"{label} (+€{prijs})"
    return label


def build_standhouder_vragen_form(vragen, aantal_tafels, vraag_aantal_tafels=False, max_tafels=3):
    class StandhouderVragenForm(forms.Form):
        pass

    if vraag_aantal_tafels:
        StandhouderVragenForm.base_fields["aantal_tafels"] = forms.IntegerField(
            label="Aantal tafels",
            min_value=1,
            max_value=max_tafels,
            required=True,
            widget=forms.NumberInput(attrs={"class": "form-control", "min": 1, "max": max_tafels}),
        )

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
            boolean_choices = [("true", "Ja"), ("false", "Nee")]
            if vraag.verplicht:
                field = forms.ChoiceField(
                    choices=boolean_choices,
                    widget=forms.RadioSelect(attrs={"class": "form-check-input"}),
                    required=True,
                    label=vraag.tekst,
                )
            else:
                field = forms.ChoiceField(
                    choices=[("", "—")] + boolean_choices,
                    widget=forms.RadioSelect(attrs={"class": "form-check-input"}),
                    required=False,
                    label=vraag.tekst,
                )
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
        elif vraag.vraag_type == VraagType.MULTISELECT:
            opties = vraag.multiselect_opties()
            choices = [(o["label"], _multiselect_choice_label(o)) for o in opties]
            field = forms.MultipleChoiceField(
                choices=choices,
                widget=forms.CheckboxSelectMultiple(attrs={"class": "form-check-input"}),
                required=False,
                label=vraag.tekst,
            )
        else:
            continue

        StandhouderVragenForm.base_fields[field_name] = field
        StandhouderVragenForm.base_fields[field_name].vraag = vraag

    for vraag in vragen:
        if vraag.vraag_type != VraagType.MULTISELECT:
            continue
        if vraag.min_tafels and aantal_tafels < vraag.min_tafels:
            continue
        if vraag.max_tafels and aantal_tafels > vraag.max_tafels:
            continue

        field_name = f"vraag_{vraag.pk}"
        min_sel = vraag.min_selecties
        if vraag.verplicht and not min_sel:
            min_sel = 1
        max_sel = vraag.max_selecties

        def _make_clean(fname, minimum, maximum):
            def clean_method(self):
                value = self.cleaned_data.get(fname) or []
                count = len(value)
                if minimum and count < minimum:
                    raise forms.ValidationError(
                        _("Selecteer minstens %(min)s optie(s).") % {"min": minimum}
                    )
                if maximum and count > maximum:
                    raise forms.ValidationError(
                        _("Selecteer maximaal %(max)s optie(s).") % {"max": maximum}
                    )
                return value

            return clean_method

        setattr(
            StandhouderVragenForm,
            f"clean_{field_name}",
            _make_clean(field_name, min_sel, max_sel),
        )

    return StandhouderVragenForm


def serialize_vraag_antwoord(vraag, value):
    if vraag.vraag_type == VraagType.BOOLEAN:
        if value in ("true", "false"):
            return value
        return "true" if value else "false"
    if vraag.vraag_type == VraagType.CHECKBOX:
        return "true" if value else "false"
    if vraag.vraag_type == VraagType.MULTISELECT:
        if not value:
            return "[]"
        if isinstance(value, str):
            return value
        return json.dumps(list(value), ensure_ascii=False)
    return str(value) if value is not None else ""


def deserialize_vraag_antwoord_initial(vraag, antwoord_tekst):
    """Zet opgeslagen antwoord om naar form-initialwaarde."""
    if vraag.vraag_type == VraagType.BOOLEAN:
        return antwoord_tekst
    if vraag.vraag_type == VraagType.CHECKBOX:
        return antwoord_tekst == "true"
    if vraag.vraag_type == VraagType.MULTISELECT:
        if not antwoord_tekst:
            return []
        try:
            raw = json.loads(antwoord_tekst)
        except (json.JSONDecodeError, TypeError):
            return []
        if isinstance(raw, list):
            return [str(x) for x in raw]
        return []
    return antwoord_tekst
