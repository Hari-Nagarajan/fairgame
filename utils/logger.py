import coloredlogs
import logging
import os

logging.basicConfig(
    format='%(levelname)s: "%(asctime)s - %(message)s',
    filename="nvidia-bot.log",
    level=logging.DEBUG,
)

LOGLEVEL = os.environ.get("LOGLEVEL", "INFO").upper()
coloredlogs.install(level=LOGLEVEL, fmt='%(levelname)s: "%(asctime)s - %(message)s')

log = logging.getLogger("nvidia-bot")
