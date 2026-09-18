"""Time-of-day convert helpers.

Clock position on the 24h line — not duration. Naive `datetime.time` is
the native endpoint; AM/PM strings are a convenience layer. This path
never reinterprets a time as since-midnight length.
"""

from __future__ import annotations

import re
from datetime import time

from tomlrange.error import TomlRangeError

_AMPM = re.compile(r"(\d{1,2})(?::([0-5]\d))? (AM|PM)", re.IGNORECASE)


def parse_clock_label(raw: str, *, path: str, name: str) -> time:
    """Parse `"9 AM"` / `"9:30 AM"` into a naive `datetime.time`."""
    match = _AMPM.fullmatch(raw)
    if match is None:
        raise TomlRangeError(path, f"unknown {name} {raw!r}", raw)
    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    if hour < 1 or hour > 12:
        raise TomlRangeError(path, f"unknown {name} {raw!r}", raw)
    period = match.group(3).upper()
    if period == "AM":
        hour = 0 if hour == 12 else hour
    else:
        hour = 12 if hour == 12 else hour + 12
    return time(hour, minute)


def seconds_since_midnight(value: time) -> int:
    """Position on the 24h line. Not elapsed length."""
    return value.hour * 3600 + value.minute * 60 + value.second

