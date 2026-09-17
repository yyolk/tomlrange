"""Parse and validate `{ from = …, to = … }` tables from decoded TOML."""

from tomlrange.bound import Bound, Bounds
from tomlrange.domain import Domain, Spec
from tomlrange.error import TomlRangeError

__all__ = [
    "Bound",
    "Bounds",
    "Domain",
    "Spec",
    "TomlRangeError",
]
__version__ = "0.2.0"
