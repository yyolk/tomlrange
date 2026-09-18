import tomllib
from datetime import UTC, date, datetime, time, timedelta

import pytest

from tomlrange import Bound, Clock, Domain, Duration, Spec, TomlRangeError

NAP = "nap = { from = 00:15:00, to = 00:45:00 }\n"
SINGLETON = "one = { from = 00:15:00, to = 00:15:00 }\n"
INVERTED = "bad = { from = 00:45:00, to = 00:15:00 }\n"

SECONDS = Domain(timedelta, lo=timedelta(0), name="duration")
MINUTES = Domain(
    timedelta,
    lo=timedelta(0),
    name="duration",
    step=timedelta(minutes=1),
)
WINDOW = Domain(
    timedelta,
    lo=timedelta(minutes=10),
    hi=timedelta(hours=1),
    name="duration",
    step=timedelta(minutes=1),
)


def test_local_time_is_since_midnight_length() -> None:
    bound = MINUTES.bound(tomllib.loads(NAP)["nap"])
    assert bound.start == timedelta(minutes=15)
    assert bound.stop == timedelta(minutes=45)
    assert bound.stop - bound.start == timedelta(minutes=30)
    assert list(bound) == [timedelta(minutes=m) for m in range(15, 46)]
    assert bound.width == 31
    assert timedelta(minutes=30) in bound
    assert timedelta(minutes=14) not in bound
    assert time(0, 30) not in bound
    assert MINUTES.index(bound.start) == 15 * 60


def test_singleton_is_one_tick() -> None:
    bound = MINUTES.bound(tomllib.loads(SINGLETON)["one"])
    assert list(bound) == [timedelta(minutes=15)]
    assert bound.width == 1
    assert timedelta(minutes=15) in bound
    assert timedelta(minutes=16) not in bound


def test_inverted_endpoints_error() -> None:
    with pytest.raises(
        TomlRangeError, match="from \\(0:45:00\\) is after to \\(0:15:00\\)"
    ):
        MINUTES.bound(tomllib.loads(INVERTED)["bad"])


def test_lo_hi_window() -> None:
    with pytest.raises(TomlRangeError, match="below duration"):
        WINDOW.bound({"from": time(0, 5), "to": time(0, 20)})
    with pytest.raises(TomlRangeError, match="above duration"):
        WINDOW.bound({"from": time(0, 15), "to": time(1, 30)})
    ok = WINDOW.bound({"from": time(0, 15), "to": time(0, 45)})
    assert ok.as_tuple() == (timedelta(minutes=15), timedelta(minutes=45))


def test_int_seconds() -> None:
    bound = SECONDS.bound({"from": 90, "to": 180})
    assert bound.start == timedelta(seconds=90)
    assert bound.stop == timedelta(seconds=180)
    assert bound.width == 91
    assert timedelta(seconds=90) in bound
    assert timedelta(seconds=181) not in bound


def test_exact_timedelta() -> None:
    bound = MINUTES.bound({"from": timedelta(minutes=15), "to": timedelta(minutes=45)})
    assert bound.as_tuple() == (timedelta(minutes=15), timedelta(minutes=45))


def test_reject_bad_types() -> None:
    cases: list[tuple[object, str]] = [
        (date(2026, 1, 1), "expected timedelta, got date"),
        (datetime(2026, 1, 1, 0, 15), "expected timedelta, got datetime"),
        (timedelta(seconds=-1), "negative duration"),
        (-30, "negative duration"),
        ("PT15M", "expected timedelta, got str"),
        ("1h30m", "expected timedelta, got str"),
        (time(0, 15, tzinfo=UTC), "aware time is not a duration"),
        (15.0, "expected timedelta, got float"),
        (True, "expected timedelta, got bool"),
    ]
    for raw, match in cases:
        with pytest.raises(TomlRangeError, match=match) as exc:
            SECONDS.bound({"from": raw, "to": timedelta(minutes=1)})
        assert exc.value.path == "from"


def test_merge_adjacent_minute_blocks() -> None:
    overlapping = [
        {"from": timedelta(minutes=15), "to": timedelta(minutes=45)},
        {"from": timedelta(minutes=45), "to": timedelta(hours=1)},
    ]
    with pytest.raises(TomlRangeError, match="overlaps"):
        MINUTES.bounds(overlapping)
    merged_overlap = MINUTES.bounds(overlapping, overlap="merge")
    assert merged_overlap.spans == (
        Bound(timedelta(minutes=15), timedelta(hours=1), MINUTES),
    )

    adjacent = [
        {"from": timedelta(minutes=15), "to": timedelta(minutes=44)},
        {"from": timedelta(minutes=45), "to": timedelta(hours=1)},
    ]
    kept = MINUTES.bounds(adjacent)
    assert len(kept.spans) == 2
    assert kept.merge().spans == (
        Bound(timedelta(minutes=15), timedelta(hours=1), MINUTES),
    )


def test_duration_spec_export() -> None:
    bound = Duration.parse(tomllib.loads(NAP)["nap"])
    assert bound.domain.typ is timedelta
    assert bound.domain.wrap is False
    assert bound.domain.step == timedelta(seconds=1)
    assert bound.as_tuple() == (timedelta(minutes=15), timedelta(minutes=45))
    assert Duration.parse({"from": 90, "to": 180}).start == timedelta(seconds=90)

    class MinuteBlock(Duration):
        step = timedelta(minutes=1)

    ticks = MinuteBlock.parse({"from": 60, "to": 180})
    assert ticks.domain.step == timedelta(minutes=1)
    assert ticks.width == 3
    assert list(ticks) == [
        timedelta(minutes=1),
        timedelta(minutes=2),
        timedelta(minutes=3),
    ]


def test_time_domain_keeps_time_as_position() -> None:
    table = tomllib.loads(NAP)["nap"]
    clock = Clock.parse(table)
    length = Duration.parse(table)
    assert clock.as_tuple() == (time(0, 15), time(0, 45))
    assert type(clock.start) is time
    assert length.as_tuple() == (timedelta(minutes=15), timedelta(minutes=45))
    assert type(length.start) is timedelta
    with pytest.raises(TomlRangeError, match="expected time, got timedelta"):
        Clock.parse({"from": timedelta(minutes=15), "to": time(0, 45)})
    with pytest.raises(TomlRangeError, match="expected time, got int"):
        Clock.parse({"from": 90, "to": 180})
    with pytest.raises(TomlRangeError, match="expected timedelta, got str"):
        Duration.parse({"from": "9 AM", "to": "9:15 AM"})


def test_timedelta_constructor_guards() -> None:
    with pytest.raises(ValueError, match="timedelta domain cannot wrap"):
        Domain(timedelta, wrap=True, name="duration")
    with pytest.raises(TypeError, match="step must be timedelta"):
        Domain(timedelta, step=60, name="duration")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="step must be a positive interval"):
        Domain(timedelta, step=timedelta(0), name="duration")
    assert SECONDS.step == timedelta(seconds=1)
    assert SECONDS.wrap is False


def test_spec_step_on_timedelta() -> None:
    class Block(Spec):
        typ = timedelta
        lo = timedelta(0)
        step = timedelta(minutes=1)

    assert Block.domain.step == timedelta(minutes=1)
    assert list(Block.parse({"from": 0, "to": 120})) == [
        timedelta(0),
        timedelta(minutes=1),
        timedelta(minutes=2),
    ]
