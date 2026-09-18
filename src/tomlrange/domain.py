from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from tomlrange.error import TomlRangeError

if TYPE_CHECKING:
    from collections.abc import Iterator

    from tomlrange.bound import Bound, Bounds
    from tomlrange.paths import Overlap

_FROM = "from"
_TO = "to"


@dataclass(frozen=True, slots=True)
class Domain[T]:
    """Closed interval domain for a `{ from, to }` table.

    `typ` is matched with `type(raw) is typ` — `bool` is not an `int`,
    and a TOML float is not an `int`.

    Optional `members` is a named discrete order. Optional `wrap` is a
    cyclic topology: linear domains still reject inverted tables; with
    wrap, `from` after `to` walks across the seam. Cyclic `from == to`
    is a singleton — full coverage is `full()`.

    Optional `aliases` maps extra spellings onto a member before the
    exact-type and membership checks. Keys may be another type (ISO
    weekday `1` → `"mon"`). String keys also match case-insensitively.
    """

    typ: type[T]
    lo: T | None = None
    hi: T | None = None
    name: str = "value"
    keys: tuple[str, str] = (_FROM, _TO)
    members: tuple[T, ...] | None = None
    wrap: bool = False
    aliases: Mapping[Any, T] | None = None

    def __post_init__(self) -> None:
        if len(self.keys) != 2 or self.keys[0] == self.keys[1]:
            raise ValueError("keys must be two distinct TOML key names")
        if type(self.wrap) is not bool:
            raise TypeError("wrap must be bool")
        if self.members is not None:
            members = tuple(self.members)
            if not members:
                raise ValueError("members must be non-empty")
            seen: set[T] = set()
            for member in members:
                if type(member) is not self.typ:
                    raise TypeError(f"members must be {self.typ.__name__}")
                if member in seen:
                    raise ValueError("members must be unique")
                seen.add(member)
            object.__setattr__(self, "members", members)
        if self.lo is not None and type(self.lo) is not self.typ:
            raise TypeError(f"lo must be {self.typ.__name__}")
        if self.hi is not None and type(self.hi) is not self.typ:
            raise TypeError(f"hi must be {self.typ.__name__}")
        if self.members is not None:
            if self.lo is not None and self.lo not in self.members:
                raise ValueError("lo must be a member")
            if self.hi is not None and self.hi not in self.members:
                raise ValueError("hi must be a member")
            if (
                self.lo is not None
                and self.hi is not None
                and self.index(self.lo) > self.index(self.hi)
            ):
                raise ValueError("domain lo is after hi")
        elif self.lo is not None and self.hi is not None and self.lo > self.hi:  # type: ignore[operator]
            raise ValueError("domain lo is after hi")
        if self.aliases is not None:
            table = dict(self.aliases)
            for value in table.values():
                if type(value) is not self.typ:
                    raise TypeError(f"alias targets must be {self.typ.__name__}")
                if self.members is not None and value not in self.members:
                    raise ValueError("alias target must be a member")
            object.__setattr__(self, "aliases", table)

    @property
    def start_key(self) -> str:
        return self.keys[0]

    @property
    def stop_key(self) -> str:
        return self.keys[1]

    def _canonicalize(self, raw: Any) -> Any:
        if not self.aliases:
            return raw
        mapped = self.aliases.get(raw)
        if mapped is None and type(raw) is str:
            mapped = self.aliases.get(raw.lower())
        return raw if mapped is None else mapped

    def convert(self, raw: Any, *, path: str) -> T:
        raw = self._canonicalize(raw)
        if type(raw) is not self.typ:
            raise TomlRangeError(
                path,
                f"expected {self.typ.__name__}, got {type(raw).__name__}",
                raw,
            )
        if self.members is not None:
            if raw not in self.members:
                raise TomlRangeError(
                    path,
                    f"unknown {self.name} {raw!r}",
                    raw,
                )
            if self.lo is not None and self.index(raw) < self.index(self.lo):
                raise TomlRangeError(
                    path,
                    f"{raw!r} is below {self.name} {self.lo}",
                    raw,
                )
            if self.hi is not None and self.index(raw) > self.index(self.hi):
                raise TomlRangeError(
                    path,
                    f"{raw!r} is above {self.name} {self.hi}",
                    raw,
                )
            return raw
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

    def index(self, member: T) -> int:
        if self.members is None:
            if type(member) is int:
                return member
            raise TypeError(f"{self.name} has no member index")
        try:
            return self.members.index(member)
        except ValueError:
            raise TomlRangeError(
                ".",
                f"unknown {self.name} {member!r}",
                member,
            ) from None

    def successor(self, member: T) -> T | None:
        if self.members is not None:
            nxt = self.index(member) + 1
            if nxt < len(self.members):
                return self.members[nxt]
            if self.wrap:
                return self.members[0]
            return None
        if type(member) is int:
            return member + 1  # type: ignore[return-value]
        return None

    def walk(self, start: T, stop: T) -> Iterator[T]:
        if self.members is not None:
            i = self.index(start)
            j = self.index(stop)
            if i <= j:
                yield from self.members[i : j + 1]
                return
            if self.wrap:
                yield from self.members[i:]
                yield from self.members[: j + 1]
                return
            raise TypeError(f"{self.name} width is only defined for int")
        if type(start) is int and type(stop) is int:
            yield from range(start, stop + 1)
            return
        raise TypeError(f"{self.name} width is only defined for int")

    def width(self, start: T, stop: T) -> int:
        if self.members is not None:
            i = self.index(start)
            j = self.index(stop)
            if i <= j:
                return j - i + 1
            if self.wrap:
                return len(self.members) - i + j + 1
            raise TypeError(f"{self.name} width is only defined for int")
        if type(start) is int and type(stop) is int:
            return stop - start + 1
        raise TypeError(f"{self.name} width is only defined for int")

    def bound(self, raw: Any, *, path: str = ".") -> Bound[T]:
        from tomlrange.bound import Bound  # cycle: Domain ↔ Bound

        return Bound.parse(raw, self, path=path)

    def bounds(
        self,
        raw: Any,
        *,
        path: str = ".",
        overlap: Overlap = "reject",
    ) -> Bounds[T]:
        from tomlrange.bound import Bounds  # cycle: Domain ↔ Bound

        return Bounds.parse(raw, self, path=path, overlap=overlap)

    def full(self) -> Bound[T]:
        from tomlrange.bound import Bound  # cycle: Domain ↔ Bound

        if self.members is not None and (self.lo is None or self.hi is None):
            return Bound(self.members[0], self.members[-1], self)
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
    members: tuple[Any, ...] | None = None
    wrap: bool = False
    aliases: Mapping[Any, Any] | None = None
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
            members=cls.members,
            wrap=cls.wrap,
            aliases=cls.aliases,
        )

    @classmethod
    def parse(cls, raw: Any, *, path: str = ".") -> Bound[Any]:
        from tomlrange.bound import Bound  # cycle: Domain ↔ Bound

        return Bound.parse(raw, cls.domain, path=path)

    @classmethod
    def parse_many(
        cls,
        raw: Any,
        *,
        path: str = ".",
        overlap: Overlap | None = None,
    ) -> Bounds[Any]:
        from tomlrange.bound import Bounds  # cycle: Domain ↔ Bound

        return Bounds.parse(
            raw,
            cls.domain,
            path=path,
            overlap=cls.overlap if overlap is None else overlap,
        )

    @classmethod
    def full(cls) -> Bound[Any]:
        return cls.domain.full()
