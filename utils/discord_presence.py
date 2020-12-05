from pypresence import Presence
import time
import random

start_time = time.time()
version = "0.4.2"

client_id = "783592971903696907"
RPC = Presence(client_id=client_id)


def start_rpc():
    try:
        RPC.connect()
    except:
        pass


def start_presence(status):
    start_rpc()
    RPC.update(
        large_image="fairgame",
        state=f"{status}",
        details=f"{version}",
        start=start_time,
    )


def buy_update():
    start_rpc()
    RPC.update(
        large_image="fairgame",
        state="Going through checkout",
        details=f"{version}",
        start=start_time,
    )


def searching_update():
    start_rpc()
    RPC.update(
        large_image="fairgame",
        state="Looking for stock",
        details=f"{version}",
        start=start_time,
    )
