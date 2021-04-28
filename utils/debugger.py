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

from utils.logger import log

import functools
import time


def debug(func):
    """Print the function signature and return value"""

    @functools.wraps(func)
    def wrapper_debug(*args, **kwargs):
        args_repr = [repr(a) for a in args]  # 1
        kwargs_repr = [f"{k}={v!r}" for k, v in kwargs.items()]  # 2
        signature = ", ".join(args_repr + kwargs_repr)  # 3
        log.dev(f"Calling {func.__name__}({signature})")
        start_time = time.time()
        value = func(*args, **kwargs)
        log.dev(
            f"{func.__name__!r} returned {value!r}. Function ran for {time.time()-start_time} seconds.".encode(
                "utf-8"
            )
        )
        return value

    return wrapper_debug


def timer(func):
    """Time the function"""

    @functools.wraps(func)
    def wrapper_timer(*args, **kwargs):
        log.debug(f"Calling {func.__name__}")
        start_time = time.time_ns()
        value = func(*args, **kwargs)
        difference = time.time_ns() - start_time
        # if difference > 1000000:
        #     difference = round((difference / 1000000), 2)
        #     difference_string = f"{difference} milliseconds"
        # else:
        #     difference_string = f"{difference} microseconds"
        log.debug(f"{func.__name__!r} ran for {difference} nanoseconds".encode("utf-8"))
        return value

    return wrapper_timer
