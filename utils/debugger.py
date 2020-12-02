from utils.logger import log

import functools


def debug(func):
    """Print the function signature and return value"""

    @functools.wraps(func)
    def wrapper_debug(*args, **kwargs):
        args_repr = [repr(a) for a in args]  # 1
        kwargs_repr = [f"{k}={v!r}" for k, v in kwargs.items()]  # 2
        signature = ", ".join(args_repr + kwargs_repr)  # 3
        log.debug(f"Calling {func.__name__}({signature})")
        value = func(*args, **kwargs)
        log.debug(f"{func.__name__!r} returned {value!r}")  # 4
        return value

    return wrapper_debug
