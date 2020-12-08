import time

from pypresence import Presence, InvalidPipe

from utils.logger import log
from utils.version import version

start_time = int(time.time())
client_id = "783592971903696907"
available = False
try:
    RPC = Presence(client_id=client_id)
    RPC.connect()
    available = True
except InvalidPipe:
    log.warning(
        "Attempted to connect to your local Discord client to update status, but Discord wasn't available.  "
        "Is it running?"
    )


def start_presence(status):
    if available:
        RPC.update(
            large_image="fairgame",
            state=f"{status}",
            details=f"{version}",
            start=start_time,
        )


def buy_update():
    if available:
        RPC.update(
            large_image="fairgame",
            state="Going through checkout",
            details=f"{version}",
            start=start_time,
        )


def searching_update():
    if available:
        RPC.update(
            large_image="fairgame",
            state="Looking for stock",
            details=f"{version}",
            start=start_time,
        )
