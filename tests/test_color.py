import tomllib

import pytest

from tomlrange import ROYGBIV, Bound, Color, TomlRangeError
from tomlrange.color import ALIASES

VISIBLE = 'visible = { from = "red", to = "violet" }\n'
BAND = 'band = { from = "orange", to = "green" }\n'
STANDARD = """
[visible]
from = "red"
to = "violet"
"""


def test_color_spec_is_linear_roygbiv() -> None:
    assert Color.members == (
        "red",
        "orange",
        "yellow",
        "green",
        "blue",
        "indigo",
        "violet",
    )
    assert Color.wrap is False
    assert Color.aliases is ALIASES
    assert Color.domain is ROYGBIV
    assert Color.domain.members == Color.members
    assert Color.domain.wrap is False
    assert Color.domain.aliases == ALIASES
    assert Color.domain.name == "color"


def test_inline_and_standard_tables_parse() -> None:
    visible = Color.parse(tomllib.loads(VISIBLE)["visible"])
    standard = Color.parse(tomllib.loads(STANDARD)["visible"])
    band = Color.parse(tomllib.loads(BAND)["band"])
    assert visible == standard
    assert list(visible) == [
        "red",
        "orange",
        "yellow",
        "green",
        "blue",
        "indigo",
        "violet",
    ]
    assert visible.width == 7
    assert list(band) == ["orange", "yellow", "green"]
    assert band.as_tuple() == ("orange", "green")


def test_letter_and_full_name_aliases() -> None:
    letters = Color.parse({"from": "r", "to": "v"})
    assert letters.as_tuple() == ("red", "violet")
    assert list(letters) == list(Color.full())
    mixed = Color.parse({"from": "o", "to": "green"})
    assert list(mixed) == ["orange", "yellow", "green"]
    names = Color.parse({"from": "yellow", "to": "indigo"})
    assert list(names) == ["yellow", "green", "blue", "indigo"]
    assert Color.parse({"from": "i", "to": "i"}).as_tuple() == ("indigo", "indigo")
    assert Color.parse({"from": "R", "to": "V"}).as_tuple() == ("red", "violet")
    assert Color.parse({"from": "Orange", "to": "GREEN"}).as_tuple() == (
        "orange",
        "green",
    )


def test_inverted_violet_to_red_errors_like_ints() -> None:
    with pytest.raises(TomlRangeError, match="from \\(violet\\) is after to \\(red\\)"):
        Color.parse({"from": "violet", "to": "red"})
    with pytest.raises(TomlRangeError, match="from \\(violet\\) is after to \\(red\\)"):
        Color.parse({"from": "v", "to": "r"})


def test_unknown_name() -> None:
    with pytest.raises(TomlRangeError, match="unknown color 'purple'") as exc:
        Color.parse({"from": "red", "to": "purple"})
    assert exc.value.path == "to"
    with pytest.raises(TomlRangeError, match="unknown color 'x'") as from_exc:
        Color.parse({"from": "x", "to": "blue"})
    assert from_exc.value.path == "from"


def test_full_singleton_contains() -> None:
    assert Color.full().as_tuple() == ("red", "violet")
    assert Color.full().width == 7
    one = Color.parse({"from": "blue", "to": "blue"})
    assert list(one) == ["blue"]
    assert "blue" in one
    assert "green" not in one
    assert "indigo" not in one
    assert "b" not in one


def test_parse_many_and_domain_bound() -> None:
    spans = Color.parse_many(
        [{"from": "red", "to": "yellow"}, {"from": "blue", "to": "violet"}]
    )
    assert list(spans) == [
        "red",
        "orange",
        "yellow",
        "blue",
        "indigo",
        "violet",
    ]
    assert ROYGBIV.bound({"from": "g", "to": "b"}) == Bound("green", "blue", ROYGBIV)


def test_no_spectrum_module() -> None:
    with pytest.raises(ModuleNotFoundError):
        __import__("tomlrange.spectrum")
