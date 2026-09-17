from typing import Any


class TomlRangeError(ValueError):
    """A `{ from, to }` table failed to parse or validate."""

    def __init__(self, path: str, message: str, value: Any = None) -> None:
        self.path = path
        self.message = message
        self.value = value
        loc = path if path not in {"", "."} else "range"
        super().__init__(f"{loc}: {message}")
