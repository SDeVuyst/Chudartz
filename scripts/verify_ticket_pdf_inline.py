from datetime import timedelta

from reportlab.pdfbase import pdfmetrics

from chudartz.ticket_renderer import (
    FONT_BOLD,
    QR_COLUMN_LEFT,
    TEXT_COLUMN_WIDTH,
    _format_access_period,
    _register_fonts,
    _wrap_text,
)
from darts.models import Participant as DartsParticipant
from pokemon.models import Participant

_register_fonts()

text_right = 60 + TEXT_COLUMN_WIDTH
print(f"text_right={text_right}, qr_left={QR_COLUMN_LEFT}, gap={QR_COLUMN_LEFT - text_right}")
assert text_right < QR_COLUMN_LEFT, "Text column overlaps QR column"

p = Participant.objects.select_related("ticket__event").first()
if p:
    data = p.generate_ticket(return_as_http=False).getvalue()
    print(f"pokemon participant {p.pk}: pdf_bytes={len(data)}")
    assert data[:4] == b"%PDF"
    assert p.generate_qr_code() is not None
else:
    print("no pokemon participant found")

dp = DartsParticipant.objects.select_related("ticket__event").first()
if dp:
    data = dp.generate_ticket(return_as_http=False).getvalue()
    print(f"darts participant {dp.pk}: pdf_bytes={len(data)}")
    assert data[:4] == b"%PDF"
else:
    print("no darts participant found")

if p:
    ticket = p.ticket
    event = ticket.event
    ticket.toegang_start = event.start_datum - timedelta(hours=1)
    ticket.toegang_einde = None
    formatted = _format_access_period(ticket)
    print(f"vip formatted: {formatted}")
    assert ticket.get_toegang_start().strftime("%H:%M") in formatted

long_title = "Super Mega Ultra Lange Evenement Titel Die Zeker Over De QR Code Zou Gaan"
lines = _wrap_text(long_title, FONT_BOLD, 20, TEXT_COLUMN_WIDTH, 2)
widths = [round(pdfmetrics.stringWidth(line, FONT_BOLD, 20), 1) for line in lines]
print(f"long title lines={len(lines)} widths={widths}")
for line in lines:
    width = pdfmetrics.stringWidth(line, FONT_BOLD, 20)
    assert width <= TEXT_COLUMN_WIDTH + 1, (line, width)

print("ALL CHECKS PASSED")
