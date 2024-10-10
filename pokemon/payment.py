from mollie.api.client import Client
import os

class MollieClient():
    def __init__(self):
      self.client = Client()
      self.client.set_api_key(os.environ.get("MOLLIE_API_KEY_COLLECTIBLES"))


    def create_mollie_payment(self, amount, description, redirect_url):
        return self.client.payments.create({
            'amount': {
                'currency': 'EUR',
                'value': str(format(amount, ".2f"))
            },
            'description': description,
            'redirectUrl': redirect_url,
            'webhookUrl': 'https://chudartz-collectibles.com/nl/mollie-webhook/',
        })