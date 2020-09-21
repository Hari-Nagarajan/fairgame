import logging
import os
logging.basicConfig(level=logging.DEBUG)

log = logging.getLogger("nvidia-bot")
LOGLEVEL = os.environ.get("LOGLEVEL", "INFO").upper()
log.setLevel(logging.DEBUG)

stream_handler = logging.StreamHandler()
stream_handler.setFormatter(logging.Formatter('%(levelname)s: "%(asctime)s - %(message)s'))
stream_handler.setLevel(LOGLEVEL)

file_log_handler = logging.FileHandler("nvidia-bot.log")
file_log_handler.setFormatter(
    logging.Formatter('%(levelname)s: "%(asctime)s - %(message)s')
)
file_log_handler.setLevel(logging.DEBUG)

log.addHandler(stream_handler)
log.addHandler(file_log_handler)
