"""Built-in cyclic weekday domain.

Canonical members are the three-letter English names `mon`…`sun`.
Aliases live here: long names, two-letter shorts, and ISO weekday
numbers 1-7 (Monday=1). `datetime.weekday()` Monday=0 is not a TOML
spelling.
"""

from tomlrange.domain import Spec

MEMBERS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

_LONG = {
    "monday": "mon",
    "tuesday": "tue",
    "wednesday": "wed",
    "thursday": "thu",
    "friday": "fri",
    "saturday": "sat",
    "sunday": "sun",
}
_SHORT = {
    "mo": "mon",
    "tu": "tue",
    "we": "wed",
    "th": "thu",
    "fr": "fri",
    "sa": "sat",
    "su": "sun",
}
_ISO = {1: "mon", 2: "tue", 3: "wed", 4: "thu", 5: "fri", 6: "sat", 7: "sun"}

ALIASES: dict[int | str, str] = {**{m: m for m in MEMBERS}, **_LONG, **_SHORT, **_ISO}


class Weekday(Spec):
    typ = str
    members = MEMBERS
    wrap = True
    aliases = ALIASES
