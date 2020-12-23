import requests

from utils.logger import log

LATEST_URL = "https://api.github.com/repos/Hari-Nagarajan/fairgame/releases/latest"

version = "0.5.2"


def check_version():
    try:
        r = requests.get(LATEST_URL)
        data = r.json()
        remote_version = str(data["tag_name"])

        if version < remote_version:
            log.warning(
                f"You are running FairGame v{version}, but the most recent version is v{remote_version}... Consider upgrading"
            )
        else:
            log.info(f"FairGame v{version}")
    except:
        log.error("Failed version check.  Continuing execution with mystery code.")
        pass
