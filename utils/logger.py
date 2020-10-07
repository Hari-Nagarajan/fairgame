import coloredlogs
import logging
import os

logging.basicConfig(
    filename="nvidia-bot.log",
    level=logging.DEBUG,
    format='%(levelname)s: "%(asctime)s - %(message)s',
)

log = logging.getLogger("nvidia-bot")
log.setLevel(logging.DEBUG)

LOGLEVEL = os.environ.get("LOGLEVEL", "INFO").upper()
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(
    logging.Formatter('%(levelname)s: "%(asctime)s - %(message)s')
)

log.addHandler(stream_handler)

coloredlogs.install(LOGLEVEL, logger=log)
