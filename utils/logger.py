import logging
import os

log = logging.getLogger("nvidia-bot")
LOGLEVEL = os.environ.get("LOGLEVEL", "INFO").upper()
log.setLevel(level=LOGLEVEL)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(levelname)s: "%(asctime)s - %(message)s'))

file_log_handler = logging.FileHandler("nvidia-bot.log")
file_log_handler.setFormatter(
    logging.Formatter('%(levelname)s: "%(asctime)s - %(message)s')
)
log.addHandler(handler)
log.addHandler(file_log_handler)
