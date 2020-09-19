import json
from os import path

from twilio.rest import Client

from utils.logger import log

TWILIO_CONFIG_PATH = "twilio_config.json"
TWILIO_CONFIG_KEYS = ['account_sid', 'auth_token', 'from', 'to']


class TwilioHandler:

    enabled = False

    def __init__(self):
        log.info("Initializing twilio handler")

        if path.exists(TWILIO_CONFIG_PATH):
            with open(TWILIO_CONFIG_PATH) as json_file:
                self.config = json.load(json_file)
                if self.has_valid_creds():
                    self.enabled = True
                    try:
                        self.client = Client(self.config['account_sid'], self.config['auth_token'])
                    except Exception as e:
                        log.warn("Twilio client creation failed. Disabling Twilio notifications.")
                        self.enabled = False
        else:
            log.info("No Twilio creds found.")

    def has_valid_creds(self):
        if all(item in self.config.keys() for item in TWILIO_CONFIG_KEYS):
            return True
        else:
            return False

    def send(self, message_body):
        try:
            message = self.client.messages.create(
                from_=self.config['from'],
                body=message_body,
                to=self.config['to']
            )
            log.info("SMS Sent: " + message.sid)
        except Exception as e:
            log.warn("Twilio send message failed. Disabling Twilio notifications.")
            self.enabled = False
