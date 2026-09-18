import tomllib
from datetime import date, datetime, time

import pytest

from tomlrange import Bound, Day, Domain, Spec, TomlRangeError

DATE = Domain(date, name="date")
YEAR = Domain(date, lo=date(2026, 1, 1), hi=date(2026, 12, 31), name="date")

INLINE = "span = { from = 2026-01-01, to = 2026-01-07 }\n"
STANDARD = """
[span]
from = 2026-01-01
to = 2026-01-07
"""
MONTHS = """
[[span]]
from = 2026-06-01
to = 2026-06-30

[[span]]
from = 2026-07-01
to = 2026-07-31
"""


def test_week_span_inline_and_standard_table() -> None:
    a = DATE.bound(tomllib.loads(INLINE)["span"])
    b = DATE.bound(tomllib.loads(STANDARD)["span"])
    days = [date(2026, 1, d) for d in range(1, 8)]
    assert a == b
    assert list(a) == days
    assert a.width == 7
    assert len(a) == 7
    assert date(2026, 1, 4) in a
    assert date(2026, 1, 8) not in a
    assert datetime(2026, 1, 1) not in a


def test_merge_across_month_seam() -> None:
    raw = tomllib.loads(MONTHS)["span"]
    kept = DATE.bounds(raw)
    assert len(kept.spans) == 2
    merged = DATE.bounds(raw, overlap="merge")
    assert merged.spans == (Bound(date(2026, 6, 1), date(2026, 7, 31), DATE),)
    days = list(merged)
    assert days[0] == date(2026, 6, 1)
    assert days[-1] == date(2026, 7, 31)
    assert merged.spans[0].width == 61

    overlapping = [
        {"from": date(2026, 6, 1), "to": date(2026, 6, 15)},
        {"from": date(2026, 6, 10), "to": date(2026, 6, 20)},
    ]
    with pytest.raises(TomlRangeError, match="overlaps"):
        DATE.bounds(overlapping)


def test_singleton_day() -> None:
    raw = tomllib.loads("d = { from = 2026-03-15, to = 2026-03-15 }")["d"]
    bound = DATE.bound(raw)
    assert list(bound) == [date(2026, 3, 15)]
    assert bound.width == 1


def test_inverted_from_after_to() -> None:
    raw = tomllib.loads("d = { from = 2026-01-07, to = 2026-01-01 }")["d"]
    with pytest.raises(
        TomlRangeError, match="from \\(2026-01-07\\) is after to \\(2026-01-01\\)"
    ):
        DATE.bound(raw)


def test_lo_hi_planner_window() -> None:
    below = tomllib.loads("d = { from = 2025-12-31, to = 2026-01-02 }")["d"]
    with pytest.raises(TomlRangeError, match="below date") as exc:
        YEAR.bound(below)
    assert exc.value.path == "from"

    above = tomllib.loads("d = { from = 2026-12-31, to = 2027-01-01 }")["d"]
    with pytest.raises(TomlRangeError, match="above date") as above_exc:
        YEAR.bound(above)
    assert above_exc.value.path == "to"

    ok = tomllib.loads("d = { from = 2026-01-01, to = 2026-01-02 }")["d"]
    assert YEAR.bound(ok).as_tuple() == (date(2026, 1, 1), date(2026, 1, 2))
    assert YEAR.full().as_tuple() == (date(2026, 1, 1), date(2026, 12, 31))


def test_iso_string_endpoints() -> None:
    raw = tomllib.loads('d = { from = "2026-01-01", to = "2026-01-03" }')["d"]
    bound = DATE.bound(raw)
    assert list(bound) == [date(2026, 1, 1), date(2026, 1, 2), date(2026, 1, 3)]

    with pytest.raises(TomlRangeError, match="expected YYYY-MM-DD, got '20260101'"):
        DATE.bound({"from": "20260101", "to": "2026-01-02"})
    with pytest.raises(TomlRangeError, match="expected YYYY-MM-DD, got '2026-13-01'"):
        DATE.bound({"from": "2026-13-01", "to": "2026-01-02"})
    with pytest.raises(TomlRangeError, match="expected YYYY-MM-DD"):
        DATE.bound({"from": "2026-01-01T00:00:00", "to": "2026-01-02"})
    with pytest.raises(TomlRangeError, match="below date"):
        YEAR.bound({"from": "2025-12-31", "to": "2026-01-02"})


def test_reject_time_int_and_datetime() -> None:
    raw_time = tomllib.loads("d = { from = 09:00:00, to = 2026-01-01 }")["d"]
    with pytest.raises(TomlRangeError, match="expected date, got time") as exc:
        DATE.bound(raw_time)
    assert exc.value.path == "from"

    with pytest.raises(TomlRangeError, match="expected date, got int"):
        DATE.bound({"from": 738885, "to": date(2026, 1, 1)})

    raw_dt = tomllib.loads("d = { from = 2026-01-01T09:00:00, to = 2026-01-02 }")["d"]
    with pytest.raises(TomlRangeError, match="expected date, got datetime"):
        DATE.bound(raw_dt)
    with pytest.raises(TomlRangeError, match="expected date, got datetime"):
        DATE.bound({"from": datetime(2026, 1, 1, 9, 0), "to": date(2026, 1, 2)})
    assert time(9, 0) not in DATE.bound(
        tomllib.loads("d = { from = 2026-01-01, to = 2026-01-02 }")["d"]
    )


def test_leap_day_inside_and_outside_window() -> None:
    raw = tomllib.loads("d = { from = 2024-02-28, to = 2024-03-01 }")["d"]
    bound = DATE.bound(raw)
    assert date(2024, 2, 29) in bound
    assert bound.width == 3
    assert list(bound) == [date(2024, 2, 28), date(2024, 2, 29), date(2024, 3, 1)]

    year_2025 = Domain(date, lo=date(2025, 1, 1), hi=date(2025, 12, 31), name="date")
    leap = tomllib.loads("d = { from = 2024-02-29, to = 2024-03-01 }")["d"]
    with pytest.raises(TomlRangeError, match="below date"):
        year_2025.bound(leap)

    with pytest.raises(TomlRangeError, match="expected YYYY-MM-DD, got '2025-02-29'"):
        DATE.bound({"from": "2025-02-29", "to": "2025-03-01"})


def test_day_spec_and_as_range_stays_int_only() -> None:
    raw = tomllib.loads("d = { from = 2026-01-01, to = 2026-01-02 }")["d"]
    bound = Day.parse(raw)
    assert Day.domain.typ is date
    assert Day.domain.wrap is False
    assert Day.domain.members is None
    assert list(bound) == [date(2026, 1, 1), date(2026, 1, 2)]
    with pytest.raises(TypeError, match="date width is only defined for int"):
        bound.as_range()

    class Book(Spec):
        typ = date
        lo = date(2026, 1, 1)
        hi = date(2026, 12, 31)

    assert Book.full().width == 365
    june_july = Book.parse_many(tomllib.loads(MONTHS)["span"], overlap="merge")
    assert next(iter(june_july)) == date(2026, 6, 1)
