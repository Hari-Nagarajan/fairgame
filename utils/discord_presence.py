import time

from pypresence import Presence

from utils.version import version

start_time = int(time.time())

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
