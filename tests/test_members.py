import pytest

from tomlrange import Bound, Domain, Spec, TomlRangeError

COLORS = Domain(
    str,
    members=("red", "orange", "yellow", "green", "blue"),
    name="color",
)
DAYS = Domain(
    str,
    members=("mon", "tue", "wed", "thu", "fri", "sat", "sun"),
    wrap=True,
    name="weekday",
)


def test_members_linear_walk_contains_width() -> None:
    bound = COLORS.bound({"from": "orange", "to": "green"})
    assert list(bound) == ["orange", "yellow", "green"]
    assert bound.width == 3
    assert len(bound) == 3
    assert "orange" in bound
    assert "yellow" in bound
    assert "green" in bound
    assert "red" not in bound
    assert "blue" not in bound
    assert 1 not in bound
    assert COLORS.full().as_tuple() == ("red", "blue")
    assert list(COLORS.full()) == ["red", "orange", "yellow", "green", "blue"]


def test_members_wrap_across_seam() -> None:
    bound = DAYS.bound({"from": "sat", "to": "mon"})
    assert list(bound) == ["sat", "sun", "mon"]
    assert bound.width == 3
    assert "sat" in bound
    assert "sun" in bound
    assert "mon" in bound
    assert "fri" not in bound
    assert "tue" not in bound
    assert "wed" not in bound


def test_members_cyclic_singleton_is_not_full_cycle() -> None:
    one = DAYS.bound({"from": "sun", "to": "sun"})
    assert list(one) == ["sun"]
    assert one.width == 1
    assert "sat" not in one
    assert "mon" not in one
    assert list(DAYS.full()) == ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    assert DAYS.full().width == 7


def test_members_inverted_linear_errors() -> None:
    with pytest.raises(TomlRangeError, match="from \\(green\\) is after to \\(red\\)"):
        COLORS.bound({"from": "green", "to": "red"})


def test_members_unknown_member() -> None:
    with pytest.raises(TomlRangeError, match="unknown color 'purple'") as exc:
        COLORS.bound({"from": "red", "to": "purple"})
    assert exc.value.path == "to"
    with pytest.raises(TomlRangeError, match="unknown weekday 'Monday'") as from_exc:
        DAYS.bound({"from": "Monday", "to": "tue"})
    assert from_exc.value.path == "from"


def test_members_overlap_merge_on_identity() -> None:
    overlapping = [{"from": "red", "to": "yellow"}, {"from": "yellow", "to": "blue"}]
    with pytest.raises(TomlRangeError, match="overlaps"):
        COLORS.bounds(overlapping)
    allowed = COLORS.bounds(overlapping, overlap="allow")
    assert list(allowed) == ["red", "orange", "yellow", "green", "blue"]
    merged = COLORS.bounds(overlapping, overlap="merge")
    assert merged.spans == (Bound("red", "blue", COLORS),)

    adjacent = [{"from": "red", "to": "yellow"}, {"from": "green", "to": "blue"}]
    kept = COLORS.bounds(adjacent)
    assert len(kept.spans) == 2
    assert kept.merge().spans == (Bound("red", "blue", COLORS),)


def test_members_wrap_overlap_and_cycle_adjacency() -> None:
    wrapping = [{"from": "sat", "to": "mon"}, {"from": "mon", "to": "tue"}]
    with pytest.raises(TomlRangeError, match="overlaps"):
        DAYS.bounds(wrapping)
    assert DAYS.bounds(wrapping, overlap="merge").spans == (Bound("sat", "tue", DAYS),)

    cycle_adj = [{"from": "fri", "to": "sat"}, {"from": "sun", "to": "mon"}]
    kept = DAYS.bounds(cycle_adj)
    assert len(kept.spans) == 2
    assert kept.merge().spans == (Bound("fri", "mon", DAYS),)

    not_adj = [{"from": "fri", "to": "sat"}, {"from": "mon", "to": "tue"}]
    skipped = DAYS.bounds(not_adj)
    assert skipped.merge().spans == (
        Bound("mon", "tue", DAYS),
        Bound("fri", "sat", DAYS),
    )


def test_spec_members_and_wrap() -> None:
    class Weekday(Spec):
        typ = str
        members = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
        wrap = True

    assert Weekday.domain.members == DAYS.members
    assert Weekday.domain.wrap is True
    assert list(Weekday.parse({"from": "sat", "to": "mon"})) == ["sat", "sun", "mon"]
    assert Weekday.full().width == 7


def test_aliases_canonicalize_before_members() -> None:
    days = Domain(
        str,
        members=("mon", "tue", "wed"),
        aliases={"monday": "mon", 1: "mon", "mo": "mon"},
        name="weekday",
    )
    assert days.bound({"from": "monday", "to": "wed"}).as_tuple() == ("mon", "wed")
    assert days.bound({"from": "Monday", "to": "tue"}).as_tuple() == ("mon", "tue")
    assert days.bound({"from": 1, "to": "tue"}).as_tuple() == ("mon", "tue")
    assert days.bound({"from": "MO", "to": "tue"}).as_tuple() == ("mon", "tue")


def test_aliases_constructor_guards() -> None:
    with pytest.raises(TypeError, match="alias targets must be str"):
        Domain(str, members=("mon",), aliases={1: 1}, name="weekday")
    with pytest.raises(ValueError, match="alias target must be a member"):
        Domain(str, members=("mon",), aliases={"monday": "tue"}, name="weekday")


def test_members_constructor_guards() -> None:
    with pytest.raises(ValueError, match="members must be non-empty"):
        Domain(str, members=(), name="color")
    with pytest.raises(ValueError, match="members must be unique"):
        Domain(str, members=("red", "red"), name="color")
    with pytest.raises(TypeError, match="members must be str"):
        Domain(str, members=("red", 1), name="color")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="lo must be a member"):
        Domain(str, members=("red", "blue"), lo="green", name="color")
    with pytest.raises(ValueError, match="domain lo is after hi"):
        Domain(str, members=("red", "blue"), lo="blue", hi="red", name="color")
