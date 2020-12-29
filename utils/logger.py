import coloredlogs
import logging
import os

from logging import handlers

LOG_DIR = "logs"
LOG_FILE_NAME = "fairgame.log"
if not os.path.exists(LOG_DIR):
    try:
        os.makedirs(LOG_DIR)
    except OSError:
        raise

LOG_FILE_PATH = os.path.join(LOG_DIR, LOG_FILE_NAME)

# This check *must* be executed before logging.basicConfig because, at least on Windows,
# basicConfig creates a lock on the log file that prevents renaming.  Possibly a workaround
# but putting this first seems to dodge the issue
if os.path.isfile(LOG_FILE_PATH):
    # Create a transient handler to do the rollover for us on startup.  This won't
    # be added to the logger as a handler... just used to roll the log on startup.
    rollover_handler = handlers.RotatingFileHandler(LOG_FILE_PATH, backupCount=10)
    # Prior log file exists, so roll it to get a clean log for this run
    try:
        rollover_handler.doRollover()
    except Exception:
        # Eat it since it's *probably* non-fatal and since we're *probably* still able to log to the prior file
        pass

logging.basicConfig(
    filename=LOG_FILE_PATH,
    level=logging.DEBUG,
    format='%(levelname)s: "%(asctime)s - %(message)s',
)

log = logging.getLogger("fairgame")
log.setLevel(logging.DEBUG)

LOGLEVEL = os.environ.get("LOGLEVEL", "INFO").upper()
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(
    logging.Formatter('%(levelname)s: "%(asctime)s - %(message)s')
)

log.addHandler(stream_handler)

coloredlogs.install(LOGLEVEL, logger=log, fmt="%(asctime)s %(levelname)s %(message)s")
