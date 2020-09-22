import json
from os import path

from slack import WebClient

from slack.errors import SlackApiError

from utils.logger import log


SLACK_CONFIG_PATH = "slack_config.json"
SLACK_CONFIG_KEYS = ["slack_user", "slack_channel", "slack_token"]


class SlackHandler:

    enabled = False

    def __init__(self):
        log.debug("Initializing slack handler")

        if path.exists(SLACK_CONFIG_PATH):
            with open(SLACK_CONFIG_PATH) as json_file:
                self.config = json.load(json_file)
                if self.has_valid_creds():
                    self.enabled = True
                    try:
                        self.client = WebClient(token=self.config["slack_token"])
                    except Exception as e:
                        log.warn(
                            "Slack client creation failed. Disabling Slack notifications."
                        )
                        self.enabled = False
        else:
            log.debug("No Slack creds found.")

    def has_valid_creds(self):
        if all(item in self.config.keys() for item in SLACK_CONFIG_KEYS):
            return True
        else:
            return False

    def send(self, message_body):
        try:
            response = self.client.chat_postMessage(
                channel=self.config["slack_channel"], text=message_body
            )

            log.info(f"Slack message sent: {response.status_code}")
        except SlackApiError as e:
            log.error(e)
            log.warn("Slack send message failed. Disabling Slack notifications.")
            self.enabled = False
