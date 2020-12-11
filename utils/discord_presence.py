import time

from pypresence import Presence

from utils.logger import log
from utils.version import version

FAILS_BETWEEN_RETRY = 5

start_time = int(time.time())
client_id = "783592971903696907"
enabled = True
connected = False
failure_count = 0
RPC = Presence(client_id=client_id)

try:
    RPC.connect()
    connected = True
except:
    # Eat the exception to allow main app processing to continue
    connected = False
    pass


def start_presence():
    send_update("Spinning up")


def buy_update():
    send_update("Going through checkout")


def searching_update():
    send_update("Looking for stock")


def send_update(state):
    global connected
    global failure_count

    if enabled:
        # Only process messages if the user has this enabled
        if connected:
            # Only try to send messages if the connection is available
            try:
                RPC.update(
                    large_image="fairgame",
                    state=state,
                    details=f"{version}",
                    start=start_time,
                )
                # Reset the failure count on every successful update
                failure_count = 0
                return
            except:
                # Track the number of failures
                failure_count += 1
                # Eat the exception to allow main app processing to continue
                pass
        else:
            failure_count += 1

        # Retry the Discord connection every now and then in case it was disconnected and is back
        if failure_count % FAILS_BETWEEN_RETRY == 0:
            try:
                RPC.connect()
                connected = True
                log.debug("Reconnected to Discord Presence")
            except Exception as e:
                # Well, we tried.
                log.debug(f"Failed reconnect attempt. {e}")
                connected = False
                pass
