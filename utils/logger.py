#      FairGame - Automated Purchasing Program
#      Copyright (C) 2021  Hari Nagarajan
#
#      This program is free software: you can redistribute it and/or modify
#      it under the terms of the GNU General Public License as published by
#      the Free Software Foundation, either version 3 of the License, or
#      (at your option) any later version.
#
#      This program is distributed in the hope that it will be useful,
#      but WITHOUT ANY WARRANTY; without even the implied warranty of
#      MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#      GNU General Public License for more details.
#
#      You should have received a copy of the GNU General Public License
#      along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
#      The author may be contacted through the project's GitHub, at:
#      https://github.com/Hari-Nagarajan/fairgame

import coloredlogs
import logging
import os
from utils.version import version
from logging import handlers

FORMAT = "%(asctime)s|{}|%(levelname)s|%(message)s".format(version)

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
    rollover_handler = handlers.RotatingFileHandler(
        LOG_FILE_PATH, backupCount=10, maxBytes=100 * 1024 * 1024
    )
    # Prior log file exists, so roll it to get a clean log for this run
    try:
        rollover_handler.doRollover()
    except Exception:
        # Eat it since it's *probably* non-fatal and since we're *probably* still able to log to the prior file
        pass

logging.basicConfig(
    filename=LOG_FILE_PATH,
    level=logging.DEBUG,
    format=FORMAT,
)

log = logging.getLogger("fairgame")
log.setLevel(logging.DEBUG)

LOGLEVEL = os.environ.get("LOGLEVEL", "INFO").upper()
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(logging.Formatter(FORMAT))

log.addHandler(stream_handler)

coloredlogs.install(LOGLEVEL, logger=log, fmt=FORMAT)
