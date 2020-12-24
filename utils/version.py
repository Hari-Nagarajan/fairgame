import requests
from packaging.version import Version, parse, InvalidVersion

from utils.logger import log

_LATEST_URL = "https://api.github.com/repos/Hari-Nagarajan/fairgame/releases/latest"

# Use a Version object to gain additional version identification capabilities
# See https://github.com/pypa/packaging for details
# See https://www.python.org/dev/peps/pep-0440/ for specification
# See https://www.python.org/dev/peps/pep-0440/#examples-of-compliant-version-schemes for examples

__VERSION = "0.6.0.dev1"
version = Version(__VERSION)


def check_version():
    remote_version = get_latest_version()

    if version < remote_version:
        log.warning(
            f"You are running FairGame v{version.release}, but the most recent version is v{remote_version.release}. "
            f"Consider upgrading "
        )
    elif version.is_prerelease:
        log.warning(f"FairGame PRE-RELEASE v{version}")
    else:
        log.info(f"FairGame v{version}")


def get_latest_version():
    try:
        r = requests.get(_LATEST_URL)
        data = r.json()
        latest_version = parse(str(data["tag_name"]))
    except InvalidVersion:
        # Return a safe, but wrong version1
        latest_version = parse("0.0")
        log.error(
            f"Failed complete check for latest version.  Assuming v{latest_version}"
        )
    return latest_version
