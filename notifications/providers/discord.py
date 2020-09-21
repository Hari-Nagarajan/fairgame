import json
from os import path

from discord_webhook import DiscordWebhook

from utils.logger import log

DISCORD_CONFIG_PATH = "discord_config.json"
DISCORD_CONFIG_KEYS = ["webhook_url"]


class DiscordHandler:
    enabled = False

    def __init__(self):
        log.debug("Initializing discord handler")

        if path.exists(DISCORD_CONFIG_PATH):
            with open(DISCORD_CONFIG_PATH) as json_file:
                self.config = json.load(json_file)
                if self.config["webhook_url"]:
                    self.webhook_url = self.config["webhook_url"]
                    self.enabled = True
        else:
            log.debug("No Discord creds found.")

    def send(self, message_body):
        try:
            web_hook = DiscordWebhook(url=self.webhook_url, content=message_body)
            response = web_hook.execute()
            log.info(f"Discord hook status: {response.status_code}")
        except Exception as e:
            log.error(e)
            log.warn("Discord send message failed. Disabling Discord notifications.")
            self.enabled = False
