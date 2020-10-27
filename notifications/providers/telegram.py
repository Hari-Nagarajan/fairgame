import json
from os import path
from urllib.parse import quote

import requests

from utils.logger import log

TELEGRAM_CONFIG_PATH = "telegram_config.json"
TELEGRAM_CONFIG_KEYS = ["BOT_TOKEN", "BOT_CHAT_ID"]


class TelegramHandler:
    enabled = False

    def __init__(self):
        log.debug("Initializing telegram handler")

        if path.exists(TELEGRAM_CONFIG_PATH):
            with open(TELEGRAM_CONFIG_PATH) as json_file:
                self.config = json.load(json_file)
                if self.config["BOT_TOKEN"] and self.config["BOT_CHAT_ID"]:
                    self.bot_token = self.config["BOT_TOKEN"]
                    self.bot_chat_id = self.config["BOT_CHAT_ID"]
                    if not isinstance(self.bot_chat_id, list):
                        self.bot_chat_id = [self.bot_chat_id]
                    self.enabled = True
        else:
            log.info("No Telegram config found.")

    def generate_apprise_url(self):
        self.enabled = False
        return f"tgram://{self.bot_token}/{self.bot_chat_id}/"

    def send(self, message_body):
        try:
            for chat_id in self.bot_chat_id:
                requests.get(
                    f"https://api.telegram.org/bot{self.bot_token}/sendMessage?"
                    f"chat_id={chat_id}&text={quote(message_body)}"
                )
        except Exception as e:
            log.debug(e)
            log.warn("Telegram send message failed. Disabling Telegram notifications.")
            self.enabled = False
