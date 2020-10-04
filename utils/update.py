import git
import threading
from utils.logger import log

def get_remote_version():
    threading.Timer(600, get_remote_version).start()
    local_repo = git.Repo(".")
    local_commit = local_repo.commit()
    fetch = local_repo.remotes.origin.fetch()[0]
    remote_commit = fetch.commit
    if local_commit != remote_commit:
        log.warning(
          "\n!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n! Version out of date, please pull the latest. !\n!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
        )
