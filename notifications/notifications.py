import queue
import threading
from os import path
from playsound import playsound
import apprise

from utils.logger import log

TIME_FORMAT = "%Y-%m-%d @ %H:%M:%S"

APPRISE_CONFIG_PATH = "config/apprise.conf"
NOTIFICATION_SOUND_PATH = "notifications/notify.mp3"
PURCHASE_SOUND_PATH = "notifications/purchase.mp3"
ALARM_SOUND_PATH = "notifications/alarm-frenzy-493.mp3"


class NotificationHandler:
    enabled_handlers = []
    sound_enabled = True

    def __init__(self):
        if path.exists(APPRISE_CONFIG_PATH):
            log.info(f"Initializing Apprise handler using: {APPRISE_CONFIG_PATH}")
            self.apb = apprise.Apprise()
            config = apprise.AppriseConfig()
            config.add(APPRISE_CONFIG_PATH)
            # Get the service names from the config, not the Apprise instance when reading from config file
            for server in config.servers():
                log.info(f"Found {server.service_name} configuration")
                self.enabled_handlers.append(server.service_name)
            self.apb.add(config)
            self.queue = queue.Queue()
            self.start_worker()
            self.enabled = True
        else:
            self.enabled = False
            log.info(f"No Apprise config found at {APPRISE_CONFIG_PATH}.")
            log.info(f"For notifications, see {APPRISE_CONFIG_PATH}_template")

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

    def play_notify_sound(self):
        self.play(NOTIFICATION_SOUND_PATH)

    def play_alarm_sound(self):
        self.play(ALARM_SOUND_PATH)

    def play_purchase_sound(self):
        self.play(PURCHASE_SOUND_PATH)

    def play(self, audio_file=None, **kwargs):
        if self.sound_enabled:
            try:
                # See https://github.com/TaylorSMarks/playsound
                playsound(audio_file if audio_file else NOTIFICATION_SOUND_PATH, False)
            except Exception as e:
                log.error(e)
                log.warn(
                    "Error playing notification sound. Disabling local audio notifications."
                )
                self.sound_enabled = False
