#
# Copyright (c) 2019-2024 Roke Manor Research Ltd
#

"""Utility functions for converting times to and from strings and integers."""

from datetime import datetime, timedelta

from typing import Optional
from google.protobuf.timestamp_pb2 import Timestamp


def str_to_datetime(timestamp_str: str):
    """Parses ISO date-time like "2012-09-07T23:59:59.3Z" or "2012-09-07T23:59:59Z".

    Returns a Python datetime object. Should perhaps use dateutil.parser.parse, but this function
    avoids using any external libraries.
    """
    try:
        parts = timestamp_str.split(".")
        if len(parts) == 1:
            return datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%SZ")
        elif len(parts) == 2 and parts[1][:-1].isdecimal() and parts[1][-1] == "Z":
            d = datetime.strptime(parts[0], "%Y-%m-%dT%H:%M:%S")
            if len(parts[1]) > 7:
                microsec_str = parts[1][:6]
            else:
                microsec_str = parts[1][:-1] + "0" * (7 - len(parts[1]))
            return d + timedelta(microseconds=int(microsec_str))
    except ValueError:
        pass
    raise ValueError("Invalid timestamp: " + timestamp_str)


def datetime_to_pb(dt: datetime):
    t = Timestamp()
    t.FromDatetime(dt)
    return t


def datetime_to_str(d: Optional[datetime], quiet=False):
    """Returns the time in ISO format, includes microseconds even if 0.

    :param quiet: If false use separator "T" and ending "Z", if true use separate " " and
    no trailing string.
    """
    if d is None:
        return "-"
    elif quiet:
        return d.isoformat(sep=" ", timespec="microseconds")
    else:
        return d.isoformat(sep="T", timespec="microseconds") + "Z"


def datetime_to_display_str(dt: Optional[datetime], max_time: datetime):
    """Returns the time in ISO format, showing only the time if recent, otherwise only the date.

    Unlike datetime_to_str, the resulting string does not contain enough information to precisely
    reconstruct the original datetime value."""
    if dt is None:
        return "-"
    if dt.date() < max_time.date():
        return dt.date().isoformat()
    else:
        return dt.time().isoformat(timespec="seconds")


def timedelta_to_display_str(interval: timedelta):
    """Returns the time interval in milliseconds if less than 10 seconds or in seconds otherwise."""
    total_us = ((interval.days * 24 * 3600) + interval.seconds) * 1_000_000 + interval.microseconds
    total_s = round(total_us, -6) // 1_000_000
    if total_s <= -10 or total_s >= 10:
        return str(total_s) + "s"
    else:
        total_ms = round(total_us, -3) // 1_000
        return str(total_ms) + "ms"


_epoch = datetime(1970, 1, 1)


def datetime_to_int(dt: Optional[datetime], reverse=False):
    """Returns number of microseconds since the epoch.

    :param reverse: If True, multiplies the result by -1, effectively reversing if used for sorting.
    """
    if dt is None:
        return None
    interval = dt - _epoch
    total_us = ((interval.days * 24 * 3600) + interval.seconds) * 1_000_000 + interval.microseconds
    return total_us * (-1 if reverse else 1)


def int_to_datetime(time_val):
    """Returns a datetime given the number of microseconds since the epoch."""
    if not isinstance(time_val, int):
        return None
    return _epoch + timedelta(microseconds=time_val)


# The two following convenience functions are very common usages of the above.


def datetime_str_to_int(timestamp_str: str) -> int:
    return datetime_to_int(str_to_datetime(timestamp_str))


def datetime_int_to_str(time_val: Optional[int], quiet=False) -> str:
    return datetime_to_str(int_to_datetime(time_val), quiet)
