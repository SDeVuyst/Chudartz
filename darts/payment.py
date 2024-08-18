from mollie.api.client import Client
import os

class MollieClient():
    def __init__(self):
      self.client = Client()
      self.client.set_api_key(os.environ.get("MOLLIE_API_KEY"))
      # TODO zorg dat het de juiste app gebruikt


    def create_mollie_payment(self, amount, description, slug):
        return self.client.payments.create({
            'amount': {
                'currency': 'EUR',
                'value': str(format(amount, ".2f"))
            },
            'description': description,
            'redirectUrl': f'http://localhost/tornooien/{slug}/inschrijven/success', #TODO
            'webhookUrl': 'http://localhost/mollie-webhook/', #TODO
        })