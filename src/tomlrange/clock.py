"""Time-of-day convert helpers.

Clock position on the 24h line — not duration. Naive `datetime.time` is
the native endpoint. This path never reinterprets a time as since-midnight
length.
"""

from __future__ import annotations

from datetime import time


def seconds_since_midnight(value: time) -> int:
    """Position on the 24h line. Not elapsed length."""
    return value.hour * 3600 + value.minute * 60 + value.second
