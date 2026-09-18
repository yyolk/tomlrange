import tomllib

import pytest

from tomlrange import Bound, TomlRangeError, Weekday

MON_WED = 'weekdays = { from = "mon", to = "wed" }\n'
FRIDAY_SAT = 'weekdays = { from = "friday", to = "sat" }\n'
ARRAY_TABLES = """
[[weekdays]]
from = "mon"
to = "wed"

[[weekdays]]
from = "fri"
to = "sat"
"""
WRAP = 'weekdays = { from = "sat", to = "mon" }\n'
SINGLETON = 'weekdays = { from = "mon", to = "mon" }\n'


def test_weekday_is_cyclic_str_members() -> None:
    assert Weekday.typ is str
    assert Weekday.members == ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
    assert Weekday.wrap is True
    assert Weekday.domain.wrap is True
    assert Weekday.domain.name == "weekday"


def test_weekday_mon_to_wed() -> None:
    raw = tomllib.loads(MON_WED)["weekdays"]
    bound = Weekday.parse(raw)
    assert list(bound) == ["mon", "tue", "wed"]
    assert bound.as_tuple() == ("mon", "wed")
    assert bound.width == 3


def test_weekday_friday_alias_to_sat() -> None:
    raw = tomllib.loads(FRIDAY_SAT)["weekdays"]
    assert list(Weekday.parse(raw)) == ["fri", "sat"]


def test_weekday_array_of_tables() -> None:
    raw = tomllib.loads(ARRAY_TABLES)["weekdays"]
    spans = Weekday.parse_many(raw)
    assert list(spans) == ["mon", "tue", "wed", "fri", "sat"]
    assert spans.spans == (
        Bound("mon", "wed", Weekday.domain),
        Bound("fri", "sat", Weekday.domain),
    )


def test_weekday_wrap_sat_to_mon() -> None:
    raw = tomllib.loads(WRAP)["weekdays"]
    bound = Weekday.parse(raw)
    assert list(bound) == ["sat", "sun", "mon"]
    assert "sat" in bound
    assert "sun" in bound
    assert "mon" in bound
    assert "fri" not in bound
    assert "tue" not in bound


def test_weekday_singleton_mon_to_mon() -> None:
    raw = tomllib.loads(SINGLETON)["weekdays"]
    one = Weekday.parse(raw)
    assert list(one) == ["mon"]
    assert one.width == 1
    assert "sun" not in one
    assert "tue" not in one
    assert list(Weekday.full()) == ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    assert Weekday.full().width == 7


def test_weekday_unknown_name() -> None:
    with pytest.raises(TomlRangeError, match="unknown weekday 'funday'") as exc:
        Weekday.parse({"from": "mon", "to": "funday"})
    assert exc.value.path == "to"
    with pytest.raises(TomlRangeError, match="unknown weekday 'Montag'") as from_exc:
        Weekday.parse({"from": "Montag", "to": "tue"})
    assert from_exc.value.path == "from"


def test_weekday_overlap_and_merge() -> None:
    overlapping = [{"from": "mon", "to": "wed"}, {"from": "wed", "to": "fri"}]
    with pytest.raises(TomlRangeError, match="overlaps"):
        Weekday.parse_many(overlapping)
    merged = Weekday.parse_many(overlapping, overlap="merge")
    assert merged.spans == (Bound("mon", "fri", Weekday.domain),)
    assert list(merged) == ["mon", "tue", "wed", "thu", "fri"]


def test_weekday_adjacent_across_week_seam() -> None:
    cycle_adj = [{"from": "fri", "to": "sat"}, {"from": "sun", "to": "mon"}]
    kept = Weekday.parse_many(cycle_adj)
    assert len(kept.spans) == 2
    assert kept.merge().spans == (Bound("fri", "mon", Weekday.domain),)

    not_adj = [{"from": "fri", "to": "sat"}, {"from": "mon", "to": "tue"}]
    skipped = Weekday.parse_many(not_adj)
    assert skipped.merge().spans == (
        Bound("mon", "tue", Weekday.domain),
        Bound("fri", "sat", Weekday.domain),
    )


def test_weekday_iso_and_short_aliases() -> None:
    assert list(Weekday.parse({"from": 1, "to": 3})) == ["mon", "tue", "wed"]
    assert list(Weekday.parse({"from": 5, "to": 6})) == ["fri", "sat"]
    assert list(Weekday.parse({"from": "mo", "to": "we"})) == ["mon", "tue", "wed"]
    assert Weekday.parse({"from": "Monday", "to": "SU"}).as_tuple() == ("mon", "sun")
    assert Weekday.parse({"from": "TUE", "to": "Thu"}).as_tuple() == ("tue", "thu")
    assert Weekday.parse({"from": 7, "to": 1}).as_tuple() == ("sun", "mon")


def test_weekday_rejects_datetime_weekday_zero() -> None:
    with pytest.raises(TomlRangeError, match="expected str, got int"):
        Weekday.parse({"from": 0, "to": 1})
    with pytest.raises(TomlRangeError, match="expected str, got int"):
        Weekday.parse({"from": 8, "to": 1})
