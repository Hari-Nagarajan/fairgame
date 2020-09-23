import json
from os import path

import requests

from utils.logger import log

PAVLOK_CONFIG_PATH = "pavlok_config.json"
PAVLOK_CONFIG_KEYS = ["base_url"]


ZAP_URL = "/zap/255"


class PavlokHandler:
    enabled = False

    def __init__(self):
        log.debug("Initializing pavlok handler")

        if path.exists(PAVLOK_CONFIG_PATH):
            with open(PAVLOK_CONFIG_PATH) as json_file:
                self.config = json.load(json_file)
                if self.config["base_url"]:
                    self.base_url = self.config["base_url"]
                    self.enabled = True
        else:
            log.debug("No pavlok config found.")

    def zap(self):
        try:
            response = requests.get(self.base_url + ZAP_URL)
            log.info(f"Pavlok zaped")
        except Exception as e:
            log.error(e)
            log.warn("Pavlok failed to zap..")
            self.enabled = False
