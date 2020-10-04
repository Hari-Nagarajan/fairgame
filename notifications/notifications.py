from concurrent.futures import ThreadPoolExecutor

from notifications.providers.audio import AudioHandler
from notifications.providers.discord import DiscordHandler
from notifications.providers.join import JoinHandler
from notifications.providers.pavlok import PavlokHandler
from notifications.providers.slack import SlackHandler
from notifications.providers.telegram import TelegramHandler
from notifications.providers.twilio import TwilioHandler
from utils.logger import log

TIME_FORMAT = "%Y-%m-%d @ %H:%M:%S"


class NotificationHandler:
    def __init__(self):
        log.info("Initializing notification handlers")
        self.audio_handler = AudioHandler()
        self.twilio_handler = TwilioHandler()
        self.discord_handler = DiscordHandler()
        self.join_handler = JoinHandler()
        self.telegram_handler = TelegramHandler()
        self.slack_handler = SlackHandler()
        self.pavlok_handler = PavlokHandler()
        log.info(f"Enabled Handlers: {self.get_enabled_handlers()}")

    def get_enabled_handlers(self):
        enabled_handlers = []
        if self.audio_handler.enabled:
            enabled_handlers.append("Audio")
        if self.twilio_handler.enabled:
            enabled_handlers.append("Twilio")
        if self.discord_handler.enabled:
            enabled_handlers.append("Discord")
        if self.join_handler.enabled:
            enabled_handlers.append("Join")
        if self.telegram_handler.enabled:
            enabled_handlers.append("Telegram")
        if self.slack_handler.enabled:
            enabled_handlers.append("Slack")
        if self.pavlok_handler.enabled:
            enabled_handlers.append("Pavlok")
        return enabled_handlers

    def send_notification(self, message, **kwargs):
        with ThreadPoolExecutor(
            max_workers=len(self.get_enabled_handlers())
        ) as executor:
            if self.audio_handler.enabled:
                executor.submit(self.audio_handler.play, **kwargs)
            if self.twilio_handler.enabled:
                executor.submit(self.twilio_handler.send, message)
            if self.discord_handler.enabled:
                executor.submit(self.discord_handler.send, message)
            if self.join_handler.enabled:
                executor.submit(self.join_handler.send, message)
            if self.telegram_handler.enabled:
                executor.submit(self.telegram_handler.send, message)
            if self.slack_handler.enabled:
                executor.submit(self.slack_handler.send, message)
            if self.pavlok_handler.enabled:
                executor.submit(self.pavlok_handler.zap)
