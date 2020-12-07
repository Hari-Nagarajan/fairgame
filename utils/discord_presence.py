import time
import random
from utils.logger import log
from pypresence import Presence

start_time = time.time()

client_id = "783592971903696907"
RPC = Presence(client_id=client_id)
RPC.connect()


def start_presence(status, version):
    RPC.update(
        large_image="fairgame",
        state=f"{status}",
        details=f"{version}",
        start=start_time,
    )


def buy_update(version):
    RPC.update(
        large_image="fairgame",
        state="Going through checkout",
        details=f"{version}",
        start=start_time,
    )


def searching_update(version):
    RPC.update(
        large_image="fairgame",
        state="Looking for stock",
        details=f"{version}",
        start=start_time,
    )
