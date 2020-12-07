import requests
import json
from utils.logger import log

LATEST_URL = "https://api.github.com/repos/Hari-Nagarajan/fairgame/releases/latest"

version = "0.4.2"


def check_version(version):
    try:
        r = requests.get(LATEST_URL)
        data = r.json()
        remote_version = str(data["tag_name"])
        local_version = version

        if local_version is not remote_version:
            log.warning(
                f"You are running FairGame v{local_version}, but the most recent version is v{remote_version}... Consider upgrading"
            )
        else:
            log.info(f"FairGame v{local_version}")
    except:
        pass
