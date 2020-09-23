from notifications.providers.discord import DiscordHandler
from notifications.providers.pavlok import PavlokHandler
from notifications.providers.slack import SlackHandler
from notifications.providers.telegram import TelegramHandler
from notifications.providers.twilio import TwilioHandler
from utils.logger import log


class NotificationHandler:
    def __init__(self):
        log.info("Initializing notification handlers")
        self.twilio_handler = TwilioHandler()
        self.discord_handler = DiscordHandler()
        self.telegram_handler = TelegramHandler()
        self.slack_handler = SlackHandler()
        self.pavlok_handler = PavlokHandler()
        log.info(f"Enabled Handlers: {self.get_enabled_handlers()}")

    def get_enabled_handlers(self):
        enabled_handlers = []
        if self.twilio_handler.enabled:
            enabled_handlers.append("Twilio")
        if self.discord_handler.enabled:
            enabled_handlers.append("Discord")
        if self.telegram_handler.enabled:
            enabled_handlers.append("Telegram")
        if self.slack_handler.enabled:
            enabled_handlers.append("Slack")
        if self.pavlok_handler.enabled:
            enabled_handlers.append("Pavlok")
        return enabled_handlers

    def send_notification(self, message):
        if self.twilio_handler.enabled:
            self.twilio_handler.send(message)
        if self.discord_handler.enabled:
            self.discord_handler.send(message)
        if self.telegram_handler.enabled:
            self.telegram_handler.send(message)
        if self.slack_handler.enabled:
            self.slack_handler.send(message)
        if self.pavlok_handler.enabled:
            self.pavlok_handler.zap()
