import tomllib

import pytest

from tomlrange import Bound, Domain, Spec, TomlRangeError

MONTH = Domain(int, lo=1, hi=12, name="month")

INLINE = "months = { from = 1, to = 12 }\n"
STANDARD = """
[months_copy]
from = 1
to = 12
"""
ARRAY_INLINE = """
months_ranges = [
    { from = 1, to = 4 },
    { from = 6, to = 10 }
]
"""
ARRAY_TABLES = """
[[months_ranges_copy]]
from = 1
to = 4

[[months_ranges_copy]]
from = 6
to = 10
"""


def test_inline_table_and_standard_table_are_the_same() -> None:
    a = MONTH.bound(tomllib.loads(INLINE)["months"])
    b = MONTH.bound(tomllib.loads(STANDARD)["months_copy"])
    assert a == b
    assert a.as_tuple() == (1, 12)
    assert a.as_table() == {"from": 1, "to": 12}
    assert list(a) == list(range(1, 13))
    assert 12 in a
    assert 0 not in a


def test_array_of_inline_tables_and_array_of_tables_are_the_same() -> None:
    a = MONTH.bounds(tomllib.loads(ARRAY_INLINE)["months_ranges"])
    b = MONTH.bounds(tomllib.loads(ARRAY_TABLES)["months_ranges_copy"])
    assert a == b
    assert list(a) == [1, 2, 3, 4, 6, 7, 8, 9, 10]
    assert 4 in a
    assert 5 not in a


def test_bounds_accepts_a_single_table() -> None:
    one = MONTH.bounds({"from": 2, "to": 3})
    assert one.spans == (Bound.parse({"from": 2, "to": 3}, MONTH),)


def test_singleton_and_full() -> None:
    one = MONTH.bound({"from": 7, "to": 7})
    assert list(one) == [7]
    assert MONTH.full().as_tuple() == (1, 12)


def test_rejects_inverted_and_out_of_domain() -> None:
    with pytest.raises(TomlRangeError, match="from \\(5\\) is after to \\(1\\)"):
        MONTH.bound({"from": 5, "to": 1})
    with pytest.raises(TomlRangeError, match="above month 12"):
        MONTH.bound({"from": 1, "to": 13})
    with pytest.raises(TomlRangeError, match="below month 1"):
        MONTH.bound({"from": 0, "to": 3})


def test_rejects_wrong_shape_and_unknown_keys() -> None:
    with pytest.raises(TomlRangeError, match="expected a table"):
        MONTH.bound([1, 12])
    with pytest.raises(TomlRangeError, match="unknown keys"):
        MONTH.bound({"from": 1, "to": 2, "step": 1})
    with pytest.raises(TomlRangeError, match="must have keys"):
        MONTH.bound({"from": 1})
    with pytest.raises(TomlRangeError, match="expected int, got float"):
        MONTH.bound({"from": 1.0, "to": 2})
    with pytest.raises(TomlRangeError, match="expected int, got bool"):
        MONTH.bound({"from": True, "to": 2})


def test_overlap_policies() -> None:
    raw = [{"from": 1, "to": 4}, {"from": 4, "to": 6}]
    with pytest.raises(TomlRangeError, match="overlaps"):
        MONTH.bounds(raw)
    allowed = MONTH.bounds(raw, overlap="allow")
    assert list(allowed) == [1, 2, 3, 4, 5, 6]
    merged = MONTH.bounds(raw, overlap="merge")
    assert merged.spans == (Bound(1, 6, MONTH),)

    adjacent = [{"from": 1, "to": 4}, {"from": 5, "to": 6}]
    kept = MONTH.bounds(adjacent)
    assert len(kept.spans) == 2
    assert kept.merge().spans == (Bound(1, 6, MONTH),)


def test_spec_metaprogramming() -> None:
    class Month(Spec):
        typ = int
        lo = 1
        hi = 12

    bound = Month.parse({"from": 3, "to": 5})
    assert bound.domain.name == "month"
    assert list(Month.parse_many([{"from": 1, "to": 2}, {"from": 11, "to": 12}])) == [
        1,
        2,
        11,
        12,
    ]
    assert Month.full().width == 12


def test_custom_keys() -> None:
    hours = Domain(int, lo=0, hi=23, name="hour", keys=("start", "end"))
    bound = hours.bound({"start": 7, "end": 16})
    assert bound.as_table() == {"start": 7, "end": 16}
    with pytest.raises(TomlRangeError, match="unknown keys"):
        hours.bound({"from": 7, "to": 16})
    with pytest.raises(TomlRangeError, match="must have keys"):
        hours.bound({"start": 7})


def test_error_paths() -> None:
    with pytest.raises(TomlRangeError, match=r"months_ranges\[1\].to:") as exc:
        MONTH.bounds(
            [{"from": 1, "to": 2}, {"from": 3, "to": 13}],
            path="months_ranges",
        )
    assert exc.value.path == "months_ranges[1].to"
