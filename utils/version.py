#      FairGame - Automated Purchasing Program
#      Copyright (C) 2021  Hari Nagarajan
#
#      This program is free software: you can redistribute it and/or modify
#      it under the terms of the GNU General Public License as published by
#      the Free Software Foundation, either version 3 of the License, or
#      (at your option) any later version.
#
#      This program is distributed in the hope that it will be useful,
#      but WITHOUT ANY WARRANTY; without even the implied warranty of
#      MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#      GNU General Public License for more details.
#
#      You should have received a copy of the GNU General Public License
#      along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
#      The author may be contacted through the project's GitHub, at:
#      https://github.com/Hari-Nagarajan/fairgame

import requests
from packaging.version import Version, parse, InvalidVersion

_LATEST_URL = "https://api.github.com/repos/Hari-Nagarajan/fairgame/releases/latest"

# Use a Version object to gain additional version identification capabilities
# See https://github.com/pypa/packaging for details
# See https://www.python.org/dev/peps/pep-0440/ for specification
# See https://www.python.org/dev/peps/pep-0440/#examples-of-compliant-version-schemes for examples

__VERSION = "0.6.0"
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
