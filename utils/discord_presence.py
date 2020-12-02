from pypresence import Presence
import time
import random

client_id = "783592971903696907"
RPC = Presence(client_id=client_id)
RPC.connect()

start_time = time.time()


def start_presence(status, version):
    RPC.update(
        large_image="fairgame",
        state=f"{status}",
        details=f"{version}",
        start=start_time,
    )
