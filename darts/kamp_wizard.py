from django.utils.translation import gettext_lazy as _


def session_key(kamp):
    return f"kamp_wizard_{kamp.slug}"


def pending_payment_session_key(kamp):
    return f"kamp_pending_{kamp.slug}"


def get_wizard_data(request, kamp):
    return request.session.get(session_key(kamp), {})


def set_wizard_data(request, kamp, data):
    request.session[session_key(kamp)] = data
    request.session.modified = True


def clear_wizard_data(request, kamp):
    request.session.pop(session_key(kamp), None)


def heeft_kindgegevens(wizard_data):
    required = (
        "voornaam",
        "achternaam",
        "geboortejaar",
        "email",
        "gsm",
        "straatnaam",
        "nummer",
        "postcode",
        "stad",
    )
    return all(wizard_data.get(field) not in (None, "") for field in required)


def build_wizard_stappen(huidige_stap):
    stappen = [
        {"nummer": 1, "label": _("Kindgegevens"), "url_name": "inschrijven_dartskamp"},
        {"nummer": 2, "label": _("Overzicht"), "url_name": "inschrijven_dartskamp_overzicht"},
        {"nummer": 3, "label": _("Betalen"), "url_name": "inschrijven_dartskamp_betalen"},
    ]
    for stap in stappen:
        stap["is_reachable"] = stap["nummer"] < huidige_stap
    return stappen


def kamp_base_context(request, kamp, stap):
    stap_nummers = {"gegevens": 1, "overzicht": 2, "betalen": 3, "success": 4}
    huidige = stap_nummers.get(stap, 1)
    wizard_data = get_wizard_data(request, kamp)
    return {
        "kamp": kamp,
        "wizard_stap": huidige,
        "stappen": build_wizard_stappen(huidige),
        "wizard_data": wizard_data,
    }
