import git
import threading
from utils.logger import log

proj_url = "https://github.com/Hari-Nagarajan/nvidia-bot.git"

def get_remote_version():
    threading.Timer(600, get_remote_version).start()
    local_repo = git.Repo(".")
    fetch = local_repo.remotes.origin.fetch()[0]
    info = fetch.flags
    if info is not 4:
        log.warning(
          "Version out of date, please pull the latest."
        )
