import json
import re
from os import path

import requests

from utils.logger import log

JOIN_CONFIG_PATH = "join_config.json"
JOIN_CONFIG_KEYS = ["deviceId", "apikey"]


class JoinHandler:
    enabled = False
    url_re = re.compile(r"https[^ ]+")

    def __init__(self):
        log.debug("Initializing join handler")

        if path.exists(JOIN_CONFIG_PATH):
            with open(JOIN_CONFIG_PATH) as json_file:
                self.config = json.load(json_file)
                if self.config["deviceId"]:
                    self.deviceId = self.config["deviceId"]
                    self.apikey = self.config["apikey"]
                    self.enabled = True
        else:
            log.debug("No join config found.")

    def generate_apprise_url(self):
        self.enabled = False
        return f"join://{self.apikey}/{self.deviceId}"

    def send(self, message_body):
        try:
            url = self.url_re.search(message_body)
            payload = {
                "text": message_body,
                "title": "FairGame Alert",
                "deviceId": self.deviceId,
                "apikey": self.apikey,
            }

            if url:
                message_body = self.url_re.sub("", message_body).strip()
                payload.update({"text": message_body, "url": url.group(0)})

            response = requests.get(
                "https://joinjoaomgcd.appspot.com/_ah/api/messaging/v1/sendPush",
                params=payload,
            )
            log.info(f"Join notification status: {response.status_code}")
        except Exception as e:
            log.error(e)
            log.warn("Join notification failed")
            self.enabled = False
