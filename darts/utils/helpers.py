import hashlib
import hmac
import io
import os
import re
import requests
from email.mime.image import MIMEImage

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


def attach_image(email, filename, from_pokemon=False):
    if from_pokemon:
        logo_path = finders.find(f'pokemon/img/{filename}.png')
    else:
        logo_path = finders.find(f'img/{filename}.png')
        
    with open(logo_path, 'rb') as img_file:
        img = MIMEImage(img_file.read())
        img.add_header('Content-ID', f'<{filename}_image>')
        img.add_header('Content-Disposition', 'inline', filename=f'{filename}.png')
        email.attach(img)


def verify_recaptcha(token):
    response = requests.post(
        'https://www.google.com/recaptcha/api/siteverify',
        data={'secret': os.environ.get('CAPTCHA_SECRET'), 'response': token}
    )
    result = response.json()
    return result.get('success', False) and result.get('score', 0) >= 0.5



def verify_webhook_signature(payload_body, received_signature):
    """
    Verifies the authenticity of a webhook payload.

    :param secret_key: The secret key used to create the HMAC SHA256 hash.
    :param payload_body: The raw JSON payload received from the webhook.
    :param received_signature: The signature from the X-Cal-Signature-256 header.
    :return: True if the signature is valid, False otherwise.
    """
    # Create the HMAC SHA256 signature using the secret key and the payload body
    generated_signature = hmac.new(
        os.environ.get("CAL_WEBHOOK_KEY").encode(),
        payload_body.encode(),
        hashlib.sha256
    ).hexdigest()                    
    
    # Compare the generated signature with the received signature
    return hmac.compare_digest(generated_signature, received_signature)

