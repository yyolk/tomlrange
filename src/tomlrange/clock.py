"""Time-of-day convert helpers.

Clock position on the 24h line — not duration. Naive `datetime.time` is
the native endpoint. This path never reinterprets a time as since-midnight
length.
"""

from __future__ import annotations

from datetime import time, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tomlrange.bound import Bound


def seconds_since_midnight(value: time) -> int:
    """Position on the 24h line. Not elapsed length."""
    return value.hour * 3600 + value.minute * 60 + value.second


def elapsed(bound: Bound[time]) -> timedelta:
    """Elapsed length of a local-time bound. Endpoints stay `time`.

    ``(width - 1) * step`` on the clock walk. Overnight is the wrap walk
    already used by ``Domain._walk_clock`` — not a negative ``stop - start``.
    """
    start, stop = bound.start, bound.stop
    if type(start) is not time or type(stop) is not time:
        raise TypeError("elapsed is only defined for time bounds")
    step = bound.domain.step
    if type(step) is not timedelta:
        raise TypeError("elapsed is only defined for time bounds")
    return (bound.width - 1) * step
