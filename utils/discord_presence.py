from pypresence import Presence
import time

version = "v0.1a"

client_id = "783592971903696907"
RPC = Presence(client_id=client_id)
RPC.connect()


def start_presence():
    start_time = time.time()
    RPC.update(large_image="fairgame", details=f"{version}", start=start_time)
