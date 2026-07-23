from io import BytesIO

from django.contrib.staticfiles import finders
from django.utils.html import strip_tags
from PIL import Image
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from darts.templatetags import dutch_date

PAGE_WIDTH, PAGE_HEIGHT = letter
MARGIN = 36
CONTENT_WIDTH = PAGE_WIDTH - (2 * MARGIN)

FONT_BOLD = "Outfit-Bold"
FONT_REGULAR = "Outfit-Regular"

COLOR_LABEL = colors.HexColor("#6C757D")
COLOR_TEXT = colors.HexColor("#212529")
COLOR_ACCENT = colors.HexColor("#343A40")
COLOR_DIVIDER = colors.HexColor("#DEE2E6")

LOGO_MAX_HEIGHT = 34
PAGE_HEADER_GAP = 14
QR_SIZE = 118
COLUMN_GAP = 16
QR_LABEL_GAP = 6
TICKET_GAP = 16

_fonts_registered = False


def _register_fonts():
    global _fonts_registered
    if _fonts_registered:
        return

    bold_path = finders.find("fonts/outfit/Outfit-Bold.ttf")
    regular_path = finders.find("fonts/outfit/Outfit-Regular.ttf")
    pdfmetrics.registerFont(TTFont(FONT_BOLD, bold_path))
    pdfmetrics.registerFont(TTFont(FONT_REGULAR, regular_path))
    _fonts_registered = True


def _string_width(text, font_name, font_size):
    return pdfmetrics.stringWidth(text, font_name, font_size)


def _scaled_logo_size(logo_path, max_height):
    reader = ImageReader(logo_path)
    width, height = reader.getSize()
    if height == 0:
        return max_height * 2.6, max_height
    scale = max_height / height
    return width * scale, max_height


def _page_header_height():
    return LOGO_MAX_HEIGHT + PAGE_HEADER_GAP


def _truncate_line_with_ellipsis(text, font_name, font_size, max_width):
    ellipsis = "..."
    truncated = text
    while truncated and _string_width(f"{truncated}{ellipsis}", font_name, font_size) > max_width:
        truncated = truncated[:-1].rstrip()
    return f"{truncated}{ellipsis}" if truncated else ellipsis


def _wrap_text(text, font_name, font_size, max_width, max_lines):
    words = text.split()
    if not words:
        return [""]

    lines = []
    idx = 0

    while idx < len(words):
        current_line = words[idx]
        idx += 1

        while idx < len(words):
            candidate = f"{current_line} {words[idx]}"
            if _string_width(candidate, font_name, font_size) > max_width:
                break
            current_line = candidate
            idx += 1

        lines.append(current_line)

        if len(lines) >= max_lines:
            if idx < len(words):
                remainder = " ".join(words[idx:])
                lines[-1] = _truncate_line_with_ellipsis(
                    f"{lines[-1]} {remainder}".strip(),
                    font_name,
                    font_size,
                    max_width,
                )
            elif _string_width(lines[-1], font_name, font_size) > max_width:
                lines[-1] = _truncate_line_with_ellipsis(
                    lines[-1],
                    font_name,
                    font_size,
                    max_width,
                )
            return lines[:max_lines]

    return lines


def _format_access_period(ticket):
    start = ticket.get_toegang_start()
    end = ticket.get_toegang_einde()
    if dutch_date.dutch_date(start) == dutch_date.dutch_date(end):
        return f"{dutch_date.dutch_datetime(start)} - {dutch_date.dutch_time(end)}"
    return f"{dutch_date.dutch_datetime(start)} - {dutch_date.dutch_datetime(end)}"


def _draw_label_value_block(p, x, y, label, value, text_width, value_font_size=12, max_lines=2):
    p.setFont(FONT_REGULAR, 8)
    p.setFillColor(COLOR_LABEL)
    p.drawString(x, y, label.upper())

    p.setFillColor(COLOR_TEXT)
    p.setFont(FONT_REGULAR, value_font_size)
    lines = _wrap_text(value, FONT_REGULAR, value_font_size, text_width, max_lines)
    line_y = y - 14
    for line in lines:
        p.drawString(x, line_y, line)
        line_y -= value_font_size + 3

    return line_y - 6


def _estimate_ticket_height(event, ticket, text_width):
    title_lines = _wrap_text(str(event), FONT_BOLD, 16, text_width, 2)
    title_height = len(title_lines) * 20

    field_blocks = [
        _format_access_period(ticket),
        str(ticket),
        strip_tags(event.locatie_kort),
    ]
    field_height = 0
    for value in field_blocks:
        lines = _wrap_text(value, FONT_REGULAR, 12, text_width, 2)
        field_height += 14 + len(lines) * 15 + 6

    left_height = title_height + 4 + field_height
    qr_height = QR_LABEL_GAP + QR_SIZE + 18
    body_height = max(left_height, qr_height)

    return 6 + body_height + 8 + TICKET_GAP


def _draw_page_header(p, x, y_top, width):
    logo_path = finders.find("img/logo-black.png")
    if logo_path:
        logo_w, logo_h = _scaled_logo_size(logo_path, LOGO_MAX_HEIGHT)
        p.drawImage(
            logo_path,
            x,
            y_top - logo_h,
            logo_w,
            logo_h,
            mask="auto",
            preserveAspectRatio=True,
        )

    return y_top - _page_header_height()


def _draw_ticket_strip(p, x, y_top, width, event, ticket, qr_image):
    text_width = width - QR_SIZE - COLUMN_GAP
    qr_x = x + width - QR_SIZE
    qr_center_x = qr_x + (QR_SIZE / 2)
    content_top = y_top - 6

    p.setFont(FONT_BOLD, 16)
    p.setFillColor(COLOR_TEXT)
    title_lines = _wrap_text(str(event), FONT_BOLD, 16, text_width, 2)
    title_y = content_top
    for line in title_lines:
        p.drawString(x, title_y, line)
        title_y -= 20

    field_y = title_y - 4
    field_y = _draw_label_value_block(
        p,
        x,
        field_y,
        "Datum & tijd",
        _format_access_period(ticket),
        text_width,
    )
    field_y = _draw_label_value_block(
        p,
        x,
        field_y,
        "Ticket",
        str(ticket),
        text_width,
    )
    left_bottom = _draw_label_value_block(
        p,
        x,
        field_y,
        "Locatie",
        strip_tags(event.locatie_kort),
        text_width,
    )

    p.setFont(FONT_BOLD, 10)
    p.setFillColor(COLOR_ACCENT)
    p.drawCentredString(qr_center_x, content_top, "ENTREE TICKET")

    qr_buffer = BytesIO()
    qr_image.save(qr_buffer, format="PNG")
    qr_buffer.seek(0)
    qr_reader = ImageReader(qr_buffer)

    qr_bottom = content_top - QR_LABEL_GAP - QR_SIZE
    p.drawImage(qr_reader, qr_x, qr_bottom, QR_SIZE, QR_SIZE, mask="auto")

    p.setFont(FONT_REGULAR, 8)
    p.setFillColor(COLOR_LABEL)
    caption = "Scan bij ingang"
    caption_width = _string_width(caption, FONT_REGULAR, 8)
    p.drawString(qr_x + (QR_SIZE - caption_width) / 2, qr_bottom - 12, caption)
    qr_bottom -= 16

    content_bottom = min(left_bottom, qr_bottom) - 4

    p.setStrokeColor(COLOR_DIVIDER)
    p.setLineWidth(0.75)
    p.line(x, content_bottom, x + width, content_bottom)

    return y_top - content_bottom + TICKET_GAP


def render_tickets_pdf(ticket_items):
    _register_fonts()

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    y_cursor = PAGE_HEIGHT - MARGIN
    page_has_header = False

    for event, ticket, qr_image in ticket_items:
        text_width = CONTENT_WIDTH - QR_SIZE - COLUMN_GAP
        ticket_height = _estimate_ticket_height(event, ticket, text_width)
        header_height = 0 if page_has_header else _page_header_height()
        total_height = header_height + ticket_height

        if y_cursor - total_height < MARGIN:
            pdf.showPage()
            y_cursor = PAGE_HEIGHT - MARGIN
            page_has_header = False
            header_height = _page_header_height()
            total_height = header_height + ticket_height

        if not page_has_header:
            y_cursor = _draw_page_header(pdf, MARGIN, y_cursor, CONTENT_WIDTH)
            page_has_header = True

        used_height = _draw_ticket_strip(
            pdf,
            MARGIN,
            y_cursor,
            CONTENT_WIDTH,
            event,
            ticket,
            qr_image,
        )
        y_cursor -= used_height

    pdf.save()
    buffer.seek(0)
    return buffer


def render_ticket_pdf(*, event, ticket, qr_image: Image.Image) -> BytesIO:
    return render_tickets_pdf([(event, ticket, qr_image)])


# Backwards-compatible layout constants used in tests
TEXT_COLUMN_WIDTH = CONTENT_WIDTH - QR_SIZE - COLUMN_GAP
QR_COLUMN_LEFT = MARGIN + TEXT_COLUMN_WIDTH + COLUMN_GAP
