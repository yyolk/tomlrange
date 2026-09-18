import tomllib
from datetime import time, timedelta

import pytest

from tomlrange import Clock, Domain, elapsed

NATIVE = "open = { from = 09:00:00, to = 17:00:00 }\n"
LABELS = 'open = { from = "9 AM", to = "5 PM" }\n'


def test_elapsed_native_toml_and_labels() -> None:
    block = Clock.parse(tomllib.loads(NATIVE)["open"])
    assert type(block.start) is time
    assert type(block.stop) is time
    assert elapsed(block) == timedelta(hours=8)

    labels = Clock.parse({"from": "9 AM", "to": "5 PM"})
    quoted = Clock.parse(tomllib.loads(LABELS)["open"])
    assert elapsed(labels) == elapsed(quoted) == timedelta(hours=8)


def test_elapsed_is_not_inclusive_tick_width() -> None:
    block = Clock.parse({"from": time(9, 0), "to": time(17, 0)})
    assert block.width == 8 * 60 + 1
    assert elapsed(block) == timedelta(hours=8)


def test_elapsed_singleton_is_zero() -> None:
    one = Clock.parse({"from": "9 AM", "to": "9 AM"})
    assert elapsed(one) == timedelta(0)
    assert one.width == 1


def test_elapsed_partial_hour() -> None:
    assert elapsed(Clock.parse({"from": "9 AM", "to": "9:30 AM"})) == timedelta(
        minutes=30
    )


def test_elapsed_overnight_wrap_walk() -> None:
    night = Domain(
        time,
        lo=time(0, 0),
        hi=time(23, 59, 59),
        wrap=True,
        name="time",
    )
    bound = night.bound({"from": time(22, 0), "to": time(2, 0)})
    assert type(bound.start) is time
    assert type(bound.stop) is time
    assert bound.as_tuple() == (time(22, 0), time(2, 0))
    assert elapsed(bound) == timedelta(hours=4)
    assert elapsed(night.bound({"from": "10 PM", "to": "2 AM"})) == timedelta(hours=4)
    ticks = list(bound)
    assert ticks[0] == time(22, 0)
    assert ticks[-1] == time(2, 0)
    assert elapsed(bound) == (len(ticks) - 1) * night.step


def test_elapsed_rejects_non_time_bound() -> None:
    month = Domain(int, lo=1, hi=12, name="month")
    with pytest.raises(TypeError, match="elapsed is only defined for time bounds"):
        elapsed(month.bound({"from": 1, "to": 4}))
