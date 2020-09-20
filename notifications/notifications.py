from notifications.providers.discord import DiscordHandler
from notifications.providers.telegram import TelegramHandler
from notifications.providers.twilio import TwilioHandler
from utils.logger import log


class NotificationHandler:

    def __init__(self):
        log.info("Initializing notification handlers")
        self.twilio_handler = TwilioHandler()
        self.discord_handler = DiscordHandler()
        self.telegram_handler = TelegramHandler()

    def send_notification(self, message):
        if self.twilio_handler.enabled:
            self.twilio_handler.send(message)
        if self.discord_handler.enabled:
            self.discord_handler.send(message)
        if self.telegram_handler.enabled:
            self.telegram_handler.send(message)
