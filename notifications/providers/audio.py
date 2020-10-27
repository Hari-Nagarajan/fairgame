from os import path

from playsound import playsound

from utils.logger import log

PROJECT_DIR = path.abspath(path.dirname(path.dirname(__file__)))
NOTIFICATION_SOUND_PATH = "notify.mp3"


class AudioHandler:
    enabled = False

    def __init__(self):
        log.debug("Initializing local audio handler")

        if path.exists(NOTIFICATION_SOUND_PATH):
            self.enabled = True
        else:
            log.info("No notification sound file found.")

    def play(self, audio_file=None, **kwargs):
        try:
            playsound(audio_file if audio_file else NOTIFICATION_SOUND_PATH, True)
        except Exception as e:
            log.debug(e)
            log.warn(
                "Error playing notification sound. Disabling local audio notifications."
            )
            self.enabled = False
