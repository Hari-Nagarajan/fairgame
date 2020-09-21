import logging
import os

log = logging.getLogger("nvidia-bot")
log.setLevel(logging.DEBUG)

file_log_handler = logging.FileHandler("nvidia-bot.log")
file_log_handler.setFormatter(logging.Formatter('%(levelname)s: "%(asctime)s - %(message)s'))
file_log_handler.setLevel(logging.DEBUG)


LOGLEVEL = os.environ.get("LOGLEVEL", "INFO").upper()
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(logging.Formatter('%(levelname)s: "%(asctime)s - %(message)s'))
stream_handler.setLevel(LOGLEVEL)

log.addHandler(stream_handler)
log.addHandler(file_log_handler)
