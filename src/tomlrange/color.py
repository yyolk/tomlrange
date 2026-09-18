"""Discrete Roy G. Biv color domain — linear, no wrap.

Canonical members are the seven rainbow names. Letter aliases (`r`…`v`)
and the full names live on `aliases`, the same Spec/Domain field as
`Weekday`.
"""

from tomlrange.domain import Spec

MEMBERS = ("red", "orange", "yellow", "green", "blue", "indigo", "violet")

_LETTERS = {
    "r": "red",
    "o": "orange",
    "y": "yellow",
    "g": "green",
    "b": "blue",
    "i": "indigo",
    "v": "violet",
}

ALIASES: dict[str, str] = {**{m: m for m in MEMBERS}, **_LETTERS}


class Color(Spec):
    typ = str
    members = MEMBERS
    wrap = False
    aliases = ALIASES


ROYGBIV = Color.domain
