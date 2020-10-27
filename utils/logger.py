import coloredlogs
import logging
import os

logging.basicConfig(
    filename="nvidia-bot.log",
    level=logging.DEBUG,
    format='%(levelname)s: "%(asctime)s - %(message)s',
)

log = logging.getLogger("nvidia-bot")

LOGLEVEL = os.environ.get("LOGLEVEL", "INFO").upper()
stream_handler = logging.StreamHandler()
stream_handler.setLevel(logging.INFO)
stream_handler.setFormatter(
    logging.Formatter('%(levelname)s: "%(asctime)s - %(message)s')
)

log.addHandler(stream_handler)

coloredlogs.install(LOGLEVEL, logger=log)
