from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import TYPE_CHECKING, Any

from tomlrange.clock import seconds_since_midnight
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

    When `typ is time`, endpoints are clock *position* (not duration).
    `index` is seconds since midnight. Optional `step` (default one
    minute) drives `walk` / `width` / `successor`. `wrap=True` allows
    overnight `from` after `to`.
    """

    typ: type[T]
    lo: T | None = None
    hi: T | None = None
    name: str = "value"
    keys: tuple[str, str] = (_FROM, _TO)
    members: tuple[T, ...] | None = None
    wrap: bool = False
    step: Any = None

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
        if self.typ is time and self.members is None and self.step is None:
            object.__setattr__(self, "step", timedelta(minutes=1))
        if self.step is not None:
            if type(self.step) is not timedelta:
                raise TypeError("step must be timedelta")
            if self.step <= timedelta(0) or self.step >= timedelta(days=1):
                raise ValueError(
                    "step must be a positive interval shorter than one day"
                )

    @property
    def start_key(self) -> str:
        return self.keys[0]

    @property
    def stop_key(self) -> str:
        return self.keys[1]

    def convert(self, raw: Any, *, path: str) -> T:
        if self.typ is time and self.members is None:
            return self._convert_clock(raw, path=path)  # type: ignore[return-value]
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

    def _convert_clock(self, raw: Any, *, path: str) -> time:
        # Position on the 24h line. Do not read time as since-midnight duration.
        if type(raw) is time:
            if raw.tzinfo is not None:
                raise TomlRangeError(
                    path,
                    f"aware time is not a local {self.name}",
                    raw,
                )
            value = raw
        else:
            raise TomlRangeError(
                path,
                f"expected {self.typ.__name__}, got {type(raw).__name__}",
                raw,
            )
        if self.lo is not None and value < self.lo:  # type: ignore[operator]
            raise TomlRangeError(
                path,
                f"{value!r} is below {self.name} {self.lo}",
                raw,
            )
        if self.hi is not None and value > self.hi:  # type: ignore[operator]
            raise TomlRangeError(
                path,
                f"{value!r} is above {self.name} {self.hi}",
                raw,
            )
        return value

    def index(self, member: T) -> int:
        if self.members is None:
            if type(member) is time and self.typ is time:
                return seconds_since_midnight(member)
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

    def successor(self, member: T, step: Any = None) -> T | None:
        tick = self.step if step is None else step
        if self.members is not None:
            nxt = self.index(member) + 1
            if nxt < len(self.members):
                return self.members[nxt]
            if self.wrap:
                return self.members[0]
            return None
        if self.typ is time and self.members is None and type(member) is time:
            nxt = datetime.combine(date.min, member) + tick
            if nxt.date() != date.min:
                return nxt.time() if self.wrap else None  # type: ignore[return-value]
            return nxt.time()  # type: ignore[return-value]
        if type(member) is int:
            stride = tick if type(tick) is int else 1
            return member + stride  # type: ignore[return-value]
        return None

    def walk(self, start: T, stop: T, step: Any = None) -> Iterator[T]:
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
        if self.typ is time and type(start) is time and type(stop) is time:
            yield from self._walk_clock(start, stop, step=step)  # type: ignore[misc]
            return
        if type(start) is int and type(stop) is int:
            stride = step if type(step) is int else 1
            yield from range(start, stop + 1, stride)
            return
        raise TypeError(f"{self.name} width is only defined for int")

    def _walk_clock(self, start: time, stop: time, step: Any = None) -> Iterator[time]:
        tick = self.step if step is None else step
        wrapping = self.index(start) > self.index(stop)  # type: ignore[arg-type]
        if wrapping and not self.wrap:
            raise TypeError(f"{self.name} width is only defined for int")
        cur = start
        crossed = False
        while True:
            yield cur
            nxt = self.successor(cur, step=tick)  # type: ignore[arg-type]
            if nxt is None:
                return
            nxt_dt = datetime.combine(date.min, cur) + tick
            if nxt_dt.date() != date.min:
                crossed = True
                if not wrapping:
                    return
            if wrapping:
                if crossed and self.index(nxt) > self.index(stop):  # type: ignore[arg-type]
                    return
            elif self.index(nxt) > self.index(stop):  # type: ignore[arg-type]
                return
            cur = nxt  # type: ignore[assignment]

    def width(self, start: T, stop: T, step: Any = None) -> int:
        if self.members is not None:
            i = self.index(start)
            j = self.index(stop)
            if i <= j:
                return j - i + 1
            if self.wrap:
                return len(self.members) - i + j + 1
            raise TypeError(f"{self.name} width is only defined for int")
        if self.typ is time and type(start) is time and type(stop) is time:
            return sum(1 for _ in self._walk_clock(start, stop, step=step))
        if type(start) is int and type(stop) is int:
            stride = step if type(step) is int else 1
            return (stop - start) // stride + 1
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
    step: Any = None
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
            step=cls.step,
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


class Clock(Spec):
    """Time-of-day position on the 24h line. Not duration."""

    typ = time
    lo = time(0, 0)
    hi = time(23, 59, 59)
    name = "time"
    wrap = False
