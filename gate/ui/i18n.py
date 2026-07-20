"""Nederlandse teksten voor het toegangspoortje."""

from __future__ import annotations

# UI-statussen
TITLE_IDLE = "Scan je ticket"
TITLE_CHECKING = "Even geduld…"
TITLE_SUCCESS = "Welkom!"
TITLE_DENIED = "Toegang geweigerd"
TITLE_NOT_CONFIGURED = "Nog niet ingesteld"

MSG_READY = "Houd de QR-code voor de scanner"
MSG_CHECKING = "Je ticket wordt gecontroleerd"
MSG_SETTINGS_SAVED = "Instellingen opgeslagen"
MSG_RESET = "Scanner gereset — klaar om te scannen"
MSG_NOT_CONFIGURED = "Open de instellingen en vul de server-URL en API-sleutel in"
MSG_IGNORED_BUSY = "Even wachten — vorige scan is nog bezig"

BTN_RESET = "Herstel"
BTN_SETTINGS = "Instellingen"
BTN_SAVE = "Opslaan"
BTN_CANCEL = "Annuleren"

FILTER_ANY = "Alle tickets"
FILTER_EVENT = "Evenement {id}"
FILTER_TICKET = "Ticket {id}"

DEBUG_WAITING = "Wachten op scannerinvoer…"
WINDOW_TITLE = "ChudartZ Collectibles — Toegang"
SETTINGS_TITLE = "Poortinstellingen"

# Serverfouten → duidelijke NL-tekst (EN + NL keys for older/newer backends)
_SERVER_MESSAGES = {
    "QR code not recognised!": "QR-code niet herkend. Probeer opnieuw te scannen.",
    "Fraud Detected! Customer has not payed yet.": "Dit ticket is nog niet betaald.",
    "Fraud Detected! QR code has been tampered with.": "Deze QR-code is ongeldig of gewijzigd.",
    "Participant already attended!": "Dit ticket is al gebruikt.",
    "Wrong event for this entrance!": "Dit ticket hoort niet bij dit evenement.",
    "Wrong ticket type for this entrance!": "Dit is niet het juiste tickettype voor deze ingang.",
    "Invalid event_id or ticket_id.": "Ongeldig evenement- of ticketnummer in de instellingen.",
    "Unauthorized": "API-sleutel geweigerd. Controleer de instellingen.",
    "unknown request.": "Onverwacht antwoord van de server.",
    "QR-code niet herkend. Probeer opnieuw te scannen.": "QR-code niet herkend. Probeer opnieuw te scannen.",
    "Dit ticket is nog niet betaald.": "Dit ticket is nog niet betaald.",
    "Deze QR-code is ongeldig of gewijzigd.": "Deze QR-code is ongeldig of gewijzigd.",
    "Dit ticket is al gebruikt.": "Dit ticket is al gebruikt.",
    "Dit ticket hoort niet bij dit evenement.": "Dit ticket hoort niet bij dit evenement.",
    "Dit is niet het juiste tickettype voor deze ingang.": "Dit is niet het juiste tickettype voor deze ingang.",
    "Ongeldig evenement- of ticketnummer.": "Ongeldig evenement- of ticketnummer in de instellingen.",
    "API-sleutel geweigerd. Controleer de instellingen.": "API-sleutel geweigerd. Controleer de instellingen.",
}


def translate_server_message(message: str) -> str:
    if not message:
        return "Er ging iets mis. Probeer opnieuw."
    return _SERVER_MESSAGES.get(message, message)


def filter_caption(event_id: str = "", ticket_id: str = "") -> str:
    parts = []
    if event_id:
        parts.append(FILTER_EVENT.format(id=event_id))
    if ticket_id:
        parts.append(FILTER_TICKET.format(id=ticket_id))
    return " · ".join(parts) if parts else FILTER_ANY
