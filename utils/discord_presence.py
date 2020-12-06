from pypresence import Presence
import time
import random
from utils.logger import log

start_time = time.time()
version = "0.4.2"

log.info(f"FairGame version {version}")

client_id = "783592971903696907"
RPC = Presence(client_id=client_id)
RPC.connect()


def start_presence(status):
    RPC.update(
        large_image="fairgame",
        state=f"{status}",
        details=f"{version}",
        start=start_time,
    )


def buy_update():
    RPC.update(
        large_image="fairgame",
        state="Going through checkout",
        details=f"{version}",
        start=start_time,
    )


def searching_update():
    RPC.update(
        large_image="fairgame",
        state="Looking for stock",
        details=f"{version}",
        start=start_time,
    )
