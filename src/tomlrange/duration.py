"""Elapsed-time convert for `Domain(timedelta)`.

TOML local time is reinterpreted as **length since midnight**, not a
clock position. `00:15:00` is fifteen minutes elapsed. Overnight wrap
(`23:00` → `01:00`) is a time-of-day domain, not this helper.

Clock (#12) must keep its own convert — do not import `as_duration`
for time-as-position.
"""

from datetime import time, timedelta
from typing import Any

from tomlrange.domain import Spec
from tomlrange.error import TomlRangeError


def as_duration(raw: Any, *, path: str) -> timedelta:
    """Accept exact timedelta, naive time as since-midnight, or int seconds."""
    if type(raw) is timedelta:
        value = raw
    elif type(raw) is time:
        if raw.tzinfo is not None:
            raise TomlRangeError(path, "aware time is not a duration", raw)
        value = timedelta(
            hours=raw.hour,
            minutes=raw.minute,
            seconds=raw.second,
            microseconds=raw.microsecond,
        )
    elif type(raw) is int:
        if raw < 0:
            raise TomlRangeError(path, f"{raw!r} is a negative duration", raw)
        value = timedelta(seconds=raw)
    else:
        raise TomlRangeError(
            path,
            f"expected timedelta, got {type(raw).__name__}",
            raw,
        )
    if value < timedelta(0):
        raise TomlRangeError(path, f"{value!r} is a negative duration", raw)
    return value


class Duration(Spec):
    """Elapsed-time domain. Local time means length since midnight."""

    typ = timedelta
    lo = timedelta(0)
