"""Parse and validate `{ from = …, to = … }` tables from decoded TOML."""

from importlib.metadata import PackageNotFoundError, version

from tomlrange.bound import Bound, Bounds
from tomlrange.color import ROYGBIV, Color
from tomlrange.domain import Domain, Spec
from tomlrange.error import TomlRangeError
from tomlrange.weekday import Weekday

try:
    __version__ = version("tomlrange")
except PackageNotFoundError:
    __version__ = "unknown"

__all__ = [
    "ROYGBIV",
    "Bound",
    "Bounds",
    "Color",
    "Domain",
    "Spec",
    "TomlRangeError",
    "Weekday",
]
