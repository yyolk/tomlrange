"""Parse and validate `{ from = …, to = … }` tables from decoded TOML."""

from importlib.metadata import PackageNotFoundError, version

from tomlrange.bound import Bound, Bounds
from tomlrange.domain import Clock, Domain, Spec
from tomlrange.error import TomlRangeError

try:
    __version__ = version("tomlrange")
except PackageNotFoundError:
    __version__ = "unknown"

__all__ = [
    "Bound",
    "Bounds",
    "Clock",
    "Domain",
    "Spec",
    "TomlRangeError",
]
