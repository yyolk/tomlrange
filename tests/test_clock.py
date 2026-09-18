import tomllib
from datetime import UTC, date, datetime, time, timedelta

import pytest

from tomlrange import Bound, Clock, Domain, Spec, TomlRangeError

NATIVE = "open = { from = 09:00:00, to = 17:00:00 }\n"


def test_native_toml_local_time() -> None:
    bound = Clock.parse(tomllib.loads(NATIVE)["open"])
    assert bound.as_tuple() == (time(9, 0), time(17, 0))
    assert time(9, 0) in bound
    assert time(12, 0) in bound
    assert time(17, 0) in bound
    assert time(8, 59) not in bound
    assert time(17, 1) not in bound
    ticks = list(bound)
    assert ticks[0] == time(9, 0)
    assert ticks[-1] == time(17, 0)
    assert bound.width == 8 * 60 + 1
    assert Clock.domain.step == timedelta(minutes=1)
    assert Clock.domain.index(time(1, 0)) == 3600


def test_singleton_is_not_full_day() -> None:
    one = Clock.parse({"from": time(9, 0), "to": time(9, 0)})
    assert list(one) == [time(9, 0)]
    assert one.width == 1
    assert time(9, 1) not in one
    assert time(8, 59) not in one
    full = Clock.full()
    assert full.as_tuple() == (time(0, 0), time(23, 59, 59))
    assert one.as_tuple() != full.as_tuple()
    assert time(0, 0) in full
    assert time(23, 59, 59) in full
    assert full.width == 24 * 60


def test_inverted_overnight_without_wrap() -> None:
    with pytest.raises(
        TomlRangeError, match="from \\(22:00:00\\) is after to \\(02:00:00\\)"
    ):
        Clock.parse({"from": time(22, 0), "to": time(2, 0)})


def test_overnight_with_wrap() -> None:
    night = Domain(
        time,
        lo=time(0, 0),
        hi=time(23, 59, 59),
        wrap=True,
        name="time",
    )
    bound = night.bound({"from": time(22, 0), "to": time(2, 0)})
    assert bound.as_tuple() == (time(22, 0), time(2, 0))
    assert time(22, 0) in bound
    assert time(23, 30) in bound
    assert time(0, 0) in bound
    assert time(2, 0) in bound
    assert time(12, 0) not in bound
    assert time(21, 59) not in bound
    assert time(2, 1) not in bound
    ticks = list(bound)
    assert ticks[0] == time(22, 0)
    assert ticks[-1] == time(2, 0)
    assert time(0, 0) in ticks
    assert night.successor(time(23, 59)) == time(0, 0)


def test_reject_wrong_types() -> None:
    with pytest.raises(TomlRangeError, match="expected time, got str"):
        Clock.parse({"from": "9 AM", "to": time(17, 0)})
    with pytest.raises(TomlRangeError, match="expected time, got datetime"):
        Clock.parse({"from": datetime(2026, 1, 1, 9, 0), "to": time(17, 0)})
    with pytest.raises(TomlRangeError, match="expected time, got timedelta"):
        Clock.parse({"from": timedelta(hours=9), "to": time(17, 0)})
    with pytest.raises(TomlRangeError, match="expected time, got date"):
        Clock.parse({"from": date(2026, 1, 1), "to": time(17, 0)})
    with pytest.raises(TomlRangeError, match="aware time is not a local time"):
        Clock.parse({"from": time(9, 0, tzinfo=UTC), "to": time(17, 0)})


def test_merge_adjacent_hour_blocks() -> None:
    overlapping = [
        {"from": time(9, 0), "to": time(10, 0)},
        {"from": time(10, 0), "to": time(11, 0)},
    ]
    with pytest.raises(TomlRangeError, match="overlaps"):
        Clock.parse_many(overlapping)
    adjacent = [
        {"from": time(9, 0), "to": time(9, 59)},
        {"from": time(10, 0), "to": time(10, 59)},
    ]
    kept = Clock.parse_many(adjacent)
    assert len(kept.spans) == 2
    assert kept.merge().spans == (Bound(time(9, 0), time(10, 59), Clock.domain),)


def test_wrap_merge_overnight_adjacent() -> None:
    class Night(Spec):
        typ = time
        lo = time(0, 0)
        hi = time(23, 59, 59)
        wrap = True
        name = "time"

    wrapping = [
        {"from": time(22, 0), "to": time(23, 59)},
        {"from": time(0, 0), "to": time(2, 0)},
    ]
    assert Night.parse_many(wrapping).merge().spans == (
        Bound(time(22, 0), time(2, 0), Night.domain),
    )
    kept = Clock.parse_many(wrapping)
    assert len(kept.merge().spans) == 2


def test_clock_constructor_guards() -> None:
    with pytest.raises(TypeError, match="step must be timedelta"):
        Domain(time, step=60, name="time")
    with pytest.raises(ValueError, match="step must be a positive interval"):
        Domain(time, step=timedelta(0), name="time")
    hourly = Domain(time, step=timedelta(hours=1), name="time")
    bound = hourly.bound({"from": time(9, 0), "to": time(17, 0)})
    assert list(bound) == [
        time(9, 0),
        time(10, 0),
        time(11, 0),
        time(12, 0),
        time(13, 0),
        time(14, 0),
        time(15, 0),
        time(16, 0),
        time(17, 0),
    ]
    assert bound.width == 9
