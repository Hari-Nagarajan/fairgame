import requests
from packaging.version import Version, parse, InvalidVersion

_LATEST_URL = "https://api.github.com/repos/Hari-Nagarajan/fairgame/releases/latest"

# Use a Version object to gain additional version identification capabilities
# See https://github.com/pypa/packaging for details
# See https://www.python.org/dev/peps/pep-0440/ for specification
# See https://www.python.org/dev/peps/pep-0440/#examples-of-compliant-version-schemes for examples

__VERSION = "0.6.0.dev1"
version = Version(__VERSION)


def is_latest():
    remote_version = get_latest_version()

    if version < remote_version:
        return False
    elif version.is_prerelease:
        return False
    else:
        return True


def get_latest_version():
    try:
        r = requests.get(_LATEST_URL)
        data = r.json()
        latest_version = parse(str(data["tag_name"]))
    except InvalidVersion:
        # Return a safe, but wrong version
        latest_version = parse("0.0")
    return latest_version
