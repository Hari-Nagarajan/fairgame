import json
from os import path

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
                    self.enabled = True
        else:
            log.debug("No Telegram config found.")

    def send(self, message_body):
        try:
            if type(self.bot_chat_id) is list:
                for chat_id in self.bot_chat_id:
                    requests.get(
                        f"https://api.telegram.org/bot{self.bot_token}/sendMessage?"
                        f"chat_id={chat_id}&parse_mode=Markdown&text={message_body}"
                    )
            else:
                requests.get(
                    f"https://api.telegram.org/bot{self.bot_token}/sendMessage?"
                    f"chat_id={self.bot_chat_id}&parse_mode=Markdown&text={message_body}"
                )
        except Exception as e:
            log.error(e)
            log.warn("Telegram send message failed. Disabling Telegram notifications.")
            self.enabled = False
