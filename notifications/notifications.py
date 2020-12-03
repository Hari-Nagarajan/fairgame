import queue
import threading
from os import path

import apprise

from utils.logger import log

TIME_FORMAT = "%Y-%m-%d @ %H:%M:%S"

APPRISE_CONFIG_PATH = "config/apprise.conf"


class NotificationHandler:
    def __init__(self):
        if path.exists(APPRISE_CONFIG_PATH):
            log.info(f"Initializing Apprise handler using: {APPRISE_CONFIG_PATH}")
            self.apb = apprise.Apprise()
            config = apprise.AppriseConfig()
            config.add(APPRISE_CONFIG_PATH)
            # Get the service names from the config, not the Apprise instance when reading from config file
            for server in config.servers():
                log.info(f"Found {server.service_name} configuration")
            self.apb.add(config)
            self.queue = queue.Queue()
            self.start_worker()
            self.enabled = True
        else:
            self.enabled = False
            log.debug("No Apprise config found.")

    def send_notification(self, message, ss_name=[], **kwargs):
        if self.enabled:
            self.queue.put((message, ss_name))

    def message_sender(self):
        while True:
            message, ss_name = self.queue.get()

            if ss_name:
                self.apb.notify(body=message, attach=ss_name)
            else:
                self.apb.notify(body=message)
            self.queue.task_done()

    def start_worker(self):
        threading.Thread(target=self.message_sender, daemon=True).start()
