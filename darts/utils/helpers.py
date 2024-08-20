import io
import re
from email.mime.image import MIMEImage

from django.contrib.auth.models import Group
from django.contrib.staticfiles import finders
from pypdf import PdfReader, PdfWriter


def emailIsValid(email):
    return len(email) > 6 and re.search(r"/^[a-zA-Z0-9.!#$%&’*+/=?^_`{|}~-]+@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)*$/", email) != []


def merge_pdfs(pdf_buffers):
    """Merge multiple PDF files into a single PDF using pypdf."""
    pdf_writer = PdfWriter()
    
    for buffer in pdf_buffers:
        pdf_reader = PdfReader(buffer)
        for page in pdf_reader.pages:
            pdf_writer.add_page(page)

    # Save the merged PDF to a buffer
    merged_buffer = io.BytesIO()
    pdf_writer.write(merged_buffer)
    merged_buffer.seek(0)
    
    return merged_buffer


def attach_image(email, filename):
    logo_path = finders.find(f'img/{filename}.png')
    with open(logo_path, 'rb') as img_file:
        img = MIMEImage(img_file.read())
        img.add_header('Content-ID', f'<{filename}_image>')
        img.add_header('Content-Disposition', 'inline', filename=f'{filename}.png')
        email.attach(img)