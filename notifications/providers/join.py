import json
from os import path

import requests
import re

from utils.logger import log

JOIN_CONFIG_PATH = "join_config.json"
JOIN_CONFIG_KEYS = ["base_url","deviceId","apikey"]


class JoinHandler:
    enabled = False
    url_re = re.compile(r'https[^ ]+')

    def __init__(self):
        log.debug("Initializing join handler")

        if path.exists(JOIN_CONFIG_PATH):
            with open(JOIN_CONFIG_PATH) as json_file:
                self.config = json.load(json_file)
                if self.config["base_url"]:
                    self.base_url = self.config["base_url"]
                    self.deviceId = self.config["deviceId"]
                    self.apikey = self.config["apikey"]
                    self.enabled = True
        else:
            log.debug("No join config found.")

    def send(self, message_body):
        try:
            url = self.url_re.search(message_body)
            payload = { "text": message_body, "title": "Nvidia-Bot Alert", "deviceId": self.deviceId, "apikey": self.apikey}

            if url:
                message_body = self.url_re.sub('', message_body).strip()
                payload.update({"text": message_body, "url": url})
                
            response = requests.get(self.base_url, params=payload)
            log.info(f"Join notification status: {response.status_code}")
        except Exception as e:
            log.error(e)
            log.warn("Join notification failed")
            self.enabled = False