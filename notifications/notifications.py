import json
import queue
import threading
from concurrent.futures import ThreadPoolExecutor
from os import path

import apprise

from notifications.providers.audio import AudioHandler
from notifications.providers.discord import DiscordHandler
from notifications.providers.join import JoinHandler
from notifications.providers.slack import SlackHandler
from notifications.providers.telegram import TelegramHandler
from notifications.providers.twilio import TwilioHandler
from utils.logger import log

TIME_FORMAT = "%Y-%m-%d @ %H:%M:%S"


APPRISE_CONFIG_PATH = "config/apprise_config.json"


class NotificationHandler:
    def __init__(self):
        log.info("Initializing Apprise handler")
        self.apb = apprise.Apprise()

        if path.exists(APPRISE_CONFIG_PATH):
            with open(APPRISE_CONFIG_PATH) as json_file:
                configs = json.load(json_file)
                for config in configs:
                    self.apb.add(config["url"])
            self.queue = queue.Queue()
            self.start_worker()
            self.enabled = True
        else:
            self.enabled = False
            log.info("No Apprise config found.")

        log.info("Initializing other notification handlers")
        self.audio_handler = AudioHandler()
        self.twilio_handler = TwilioHandler()  # Deprecate soon
        self.discord_handler = DiscordHandler()  # Deprecate soon
        self.join_handler = JoinHandler()  # Deprecate soon
        self.telegram_handler = TelegramHandler()  # Deprecate soon
        self.slack_handler = SlackHandler()  # Deprecate soon

        deprecation_message = "The standalone {notification} handler will be deprecated soon, please delete your {notification}_config.json and add the equivalent apprise url: '{apprise_url}' to 'config/apprise_config.json'"
        if self.slack_handler.enabled:
            slack_apprise_url = self.slack_handler.generate_apprise_url()
            log.warning(
                deprecation_message.format(
                    notification="slack", apprise_url=slack_apprise_url
                )
            )
            self.apb.add(slack_apprise_url)

        if self.twilio_handler.enabled:
            twilio_apprise_url = self.twilio_handler.generate_apprise_url()
            log.warning(
                deprecation_message.format(
                    notification="twilio", apprise_url=twilio_apprise_url
                )
            )
            self.apb.add(twilio_apprise_url)

        if self.telegram_handler.enabled:
            telegram_apprise_url = self.telegram_handler.generate_apprise_url()
            log.warning(
                deprecation_message.format(
                    notification="telegram", apprise_url=telegram_apprise_url
                )
            )
            self.apb.add(telegram_apprise_url)

        if self.join_handler.enabled:
            join_apprise_url = self.join_handler.generate_apprise_url()
            log.warning(
                deprecation_message.format(
                    notification="join", apprise_url=join_apprise_url
                )
            )
            self.apb.add(join_apprise_url)

        if self.discord_handler.enabled:
            discord_apprise_url = self.discord_handler.generate_apprise_url()
            log.warning(
                deprecation_message.format(
                    notification="discord", apprise_url=discord_apprise_url
                )
            )
            self.apb.add(discord_apprise_url)

        enabled_handlers = self.get_enabled_handlers()
        log.info(f"Enabled Handlers: {enabled_handlers}")
        if len(enabled_handlers) > 0:
            self.executor = ThreadPoolExecutor(max_workers=len(enabled_handlers))

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
        return enabled_handlers

    def send_notification(self, message, screenshot=False, **kwargs):
        if self.enabled:
            self.queue.put((message, screenshot))

        if self.audio_handler.enabled:
            self.executor.submit(self.audio_handler.play, **kwargs)
        if self.twilio_handler.enabled:
            self.executor.submit(self.twilio_handler.send, message)
        if self.discord_handler.enabled:
            self.executor.submit(self.discord_handler.send, message)
        if self.join_handler.enabled:
            self.executor.submit(self.join_handler.send, message)
        if self.telegram_handler.enabled:
            self.executor.submit(self.telegram_handler.send, message)
        if self.slack_handler.enabled:
            self.executor.submit(self.slack_handler.send, message)

    def message_sender(self):
        while True:
            message, screenshot = self.queue.get()
            if screenshot:
                self.apb.notify(body=message, attach="screenshot.png")
            else:
                self.apb.notify(body=message)
            self.queue.task_done()

    def start_worker(self):
        threading.Thread(target=self.message_sender, daemon=True).start()
