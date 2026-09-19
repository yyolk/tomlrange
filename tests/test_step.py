import tomllib
from datetime import UTC, time, timedelta

import pytest

from tomlrange import Bound, Clock, Domain, TomlRangeError

MONTH = Domain(int, lo=1, hi=12, name="month")
COLORS = Domain(
    str,
    members=("red", "orange", "yellow", "green", "blue"),
    name="color",
)


def test_int_step_walks_stride() -> None:
    bound = MONTH.bound({"from": 1, "to": 12, "step": 3})
    assert bound.step == 3
    assert bound.domain.step is None
    assert list(bound) == [1, 4, 7, 10]
    assert bound.width == 4
    assert bound.as_range() == range(1, 13, 3)
    assert bound.as_table() == {"from": 1, "to": 12, "step": 3}
    assert MONTH.bound(bound.as_table()).as_table() == bound.as_table()


def test_clock_step_is_count_of_domain_grain() -> None:
    data = tomllib.loads("open = { from = 09:00:00, to = 17:00:00, step = 15 }")
    bound = Clock.parse(data["open"])
    assert bound.start == time(9, 0)
    assert bound.stop == time(17, 0)
    assert bound.step == timedelta(minutes=15)
    assert bound.domain.step == timedelta(minutes=1)
    ticks = list(bound)
    assert ticks[:3] == [time(9, 0), time(9, 15), time(9, 30)]
    assert ticks[-1] == time(17, 0)
    assert bound.width == 8 * 4 + 1
    assert bound.as_table() == {"from": time(9, 0), "to": time(17, 0), "step": 15}
    assert Clock.parse(bound.as_table()).as_table() == bound.as_table()


def test_clock_step_accepts_local_time_as_length_since_midnight() -> None:
    data = tomllib.loads("open = { from = 09:00:00, to = 17:00:00, step = 00:30:00 }")
    bound = Clock.parse(data["open"])
    assert bound.step == timedelta(minutes=30)
    assert bound.domain.step == timedelta(minutes=1)
    assert bound.as_table() == {"from": time(9, 0), "to": time(17, 0), "step": 30}
    assert Clock.parse(bound.as_table()).as_table() == bound.as_table()
    ticks = list(bound)
    assert ticks[:3] == [time(9, 0), time(9, 30), time(10, 0)]
    assert ticks[-1] == time(17, 0)
    assert bound.width == 8 * 2 + 1


def test_clock_time_step_matching_domain_default_omitted_from_as_table() -> None:
    bound = Clock.parse({"from": time(9, 0), "to": time(17, 0), "step": time(0, 1)})
    assert bound.step == timedelta(minutes=1)
    assert bound.as_table() == {"from": time(9, 0), "to": time(17, 0)}


def test_duration_step_is_count_of_domain_grain() -> None:
    duration = Domain(timedelta, step=timedelta(seconds=1), name="duration")
    bound = duration.bound(
        {"from": timedelta(0), "to": timedelta(minutes=1), "step": 15}
    )
    assert bound.step == timedelta(seconds=15)
    assert bound.domain.step == timedelta(seconds=1)
    assert bound.as_table() == {
        "from": timedelta(0),
        "to": timedelta(minutes=1),
        "step": 15,
    }
    assert duration.bound(bound.as_table()).as_table() == bound.as_table()


def test_omitted_step_unchanged() -> None:
    months = MONTH.bound({"from": 1, "to": 12})
    assert months.step is None
    assert months.as_table() == {"from": 1, "to": 12}
    assert list(months) == list(range(1, 13))

    hours = Clock.parse({"from": time(9, 0), "to": time(17, 0)})
    assert hours.step is None
    assert hours.as_table() == {"from": time(9, 0), "to": time(17, 0)}
    assert hours.width == 8 * 60 + 1
    assert hours.domain.step == timedelta(minutes=1)


def test_step_matching_domain_default_omitted_from_as_table() -> None:
    bound = MONTH.bound({"from": 1, "to": 12, "step": 1})
    assert bound.step == 1
    assert list(bound) == list(range(1, 13))
    assert bound.as_table() == {"from": 1, "to": 12}

    clock = Clock.parse({"from": time(9, 0), "to": time(17, 0), "step": 1})
    assert clock.step == timedelta(minutes=1)
    assert clock.as_table() == {"from": time(9, 0), "to": time(17, 0)}


def test_step_key_name_with_custom_keys() -> None:
    hours = Domain(int, lo=0, hi=23, name="hour", keys=("start", "end"))
    bound = hours.bound({"start": 7, "end": 16, "step": 3})
    assert list(bound) == [7, 10, 13, 16]
    assert bound.as_table() == {"start": 7, "end": 16, "step": 3}


@pytest.mark.parametrize(
    "raw",
    [0, -3, 1.5, True, False, "PT15M", timedelta(minutes=15), time(0, 15)],
)
def test_reject_invalid_int_domain_step_values(raw: object) -> None:
    with pytest.raises(TomlRangeError) as exc:
        MONTH.bound({"from": 1, "to": 12, "step": raw})
    assert exc.value.path == "step"


@pytest.mark.parametrize(
    "raw",
    [
        0,
        -3,
        1.5,
        True,
        False,
        "PT15M",
        timedelta(minutes=15),
        time(0, 0),
        time(0, 30, tzinfo=UTC),
    ],
)
def test_reject_invalid_clock_step_values(raw: object) -> None:
    with pytest.raises(TomlRangeError) as clock_exc:
        Clock.parse({"from": time(9, 0), "to": time(17, 0), "step": raw})
    assert clock_exc.value.path == "step"


def test_reject_clock_step_not_multiple_of_domain_grain() -> None:
    with pytest.raises(TomlRangeError, match="positive multiple") as exc:
        Clock.parse({"from": time(9, 0), "to": time(17, 0), "step": time(0, 0, 30)})
    assert exc.value.path == "step"
    hourly = Domain(time, step=timedelta(hours=1), name="time")
    with pytest.raises(TomlRangeError, match="positive multiple") as hourly_exc:
        hourly.bound({"from": time(9, 0), "to": time(17, 0), "step": time(0, 30)})
    assert hourly_exc.value.path == "step"


def test_duration_step_rejects_local_time() -> None:
    duration = Domain(timedelta, step=timedelta(seconds=1), name="duration")
    with pytest.raises(TomlRangeError, match="expected int, got time") as exc:
        duration.bound(
            {
                "from": timedelta(0),
                "to": timedelta(minutes=1),
                "step": time(0, 30),
            }
        )
    assert exc.value.path == "step"


def test_reject_step_on_members_domain() -> None:
    with pytest.raises(TomlRangeError) as exc:
        COLORS.bound({"from": "red", "to": "blue", "step": 1})
    assert exc.value.path == "step"


def test_unknown_keys_still_rejected() -> None:
    with pytest.raises(TomlRangeError, match="unknown keys"):
        MONTH.bound({"from": 1, "to": 2, "wrap": True})
    with pytest.raises(TomlRangeError, match="unknown keys"):
        Clock.parse({"from": time(9, 0), "to": time(17, 0), "wrap": True})


def test_mixed_step_list_merges_on_touch() -> None:
    raw = [{"from": 1, "to": 4, "step": 3}, {"from": 5, "to": 8}]
    kept = MONTH.bounds(raw)
    assert len(kept.spans) == 2
    assert kept.spans[0].step == 3
    assert kept.spans[1].step is None
    assert kept.merge().spans == (Bound(1, 8, MONTH),)
