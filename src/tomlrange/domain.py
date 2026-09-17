from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from tomlrange.error import TomlRangeError

if TYPE_CHECKING:
    from tomlrange.bound import Bound, Bounds
    from tomlrange.paths import Overlap

_FROM = "from"
_TO = "to"


@dataclass(frozen=True, slots=True)
class Domain[T]:
    """Closed interval domain for a `{ from, to }` table.

    `typ` is matched with `type(raw) is typ` — `bool` is not an `int`,
    and a TOML float is not an `int`.
    """

    typ: type[T]
    lo: T | None = None
    hi: T | None = None
    name: str = "value"
    keys: tuple[str, str] = (_FROM, _TO)

    def __post_init__(self) -> None:
        if len(self.keys) != 2 or self.keys[0] == self.keys[1]:
            raise ValueError("keys must be two distinct TOML key names")
        if self.lo is not None and type(self.lo) is not self.typ:
            raise TypeError(f"lo must be {self.typ.__name__}")
        if self.hi is not None and type(self.hi) is not self.typ:
            raise TypeError(f"hi must be {self.typ.__name__}")
        if self.lo is not None and self.hi is not None and self.lo > self.hi:  # type: ignore[operator]
            raise ValueError("domain lo is after hi")

    @property
    def start_key(self) -> str:
        return self.keys[0]

    @property
    def stop_key(self) -> str:
        return self.keys[1]

    def convert(self, raw: Any, *, path: str) -> T:
        if type(raw) is not self.typ:
            raise TomlRangeError(
                path,
                f"expected {self.typ.__name__}, got {type(raw).__name__}",
                raw,
            )
        if self.lo is not None and raw < self.lo:  # type: ignore[operator]
            raise TomlRangeError(
                path,
                f"{raw!r} is below {self.name} {self.lo}",
                raw,
            )
        if self.hi is not None and raw > self.hi:  # type: ignore[operator]
            raise TomlRangeError(
                path,
                f"{raw!r} is above {self.name} {self.hi}",
                raw,
            )
        return raw

    def bound(self, raw: Any, *, path: str = ".") -> Bound[T]:
        from tomlrange.bound import Bound

        return Bound.parse(raw, self, path=path)

    def bounds(
        self,
        raw: Any,
        *,
        path: str = ".",
        overlap: Overlap = "reject",
    ) -> Bounds[T]:
        from tomlrange.bound import Bounds

        return Bounds.parse(raw, self, path=path, overlap=overlap)

    def full(self) -> Bound[T]:
        from tomlrange.bound import Bound

        if self.lo is None or self.hi is None:
            raise TomlRangeError(".", f"{self.name} domain has no closed lo/hi")
        return Bound(self.lo, self.hi, self)


class Spec:
    """Subclass to name a domain. The class body is the schema.

    ```
    class Month(Spec):
        typ = int
        lo = 1
        hi = 12

    Month.parse({"from": 1, "to": 4})
    Month.parse_many([{ "from": 1, "to": 4 }, { "from": 6, "to": 10 }])
    ```
    """

    typ: type = int
    lo: Any = None
    hi: Any = None
    name: str | None = None
    keys: tuple[str, str] = (_FROM, _TO)
    overlap: Overlap = "reject"
    domain: Domain[Any]

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        name = cls.name
        if name is None:
            name = cls.__name__
            for suffix in ("Bounds", "Range", "Spec"):
                if name.endswith(suffix) and name != suffix:
                    name = name[: -len(suffix)]
                    break
            name = name.lower()
        cls.domain = Domain(
            typ=cls.typ,
            lo=cls.lo,
            hi=cls.hi,
            name=name,
            keys=cls.keys,
        )

    @classmethod
    def parse(cls, raw: Any, *, path: str = ".") -> Bound[Any]:
        from tomlrange.bound import Bound

        return Bound.parse(raw, cls.domain, path=path)

    @classmethod
    def parse_many(
        cls,
        raw: Any,
        *,
        path: str = ".",
        overlap: Overlap | None = None,
    ) -> Bounds[Any]:
        from tomlrange.bound import Bounds

        return Bounds.parse(
            raw,
            cls.domain,
            path=path,
            overlap=cls.overlap if overlap is None else overlap,
        )

    @classmethod
    def full(cls) -> Bound[Any]:
        return cls.domain.full()
