from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from tomlrange.domain import Domain
from tomlrange.error import TomlRangeError
from tomlrange.paths import index_path, join_path

if TYPE_CHECKING:
    from tomlrange.paths import Overlap


def _as_table(
    raw: Any, *, path: str, keys: tuple[str, str]
) -> Mapping[str, Any]:
    if isinstance(raw, Mapping):
        return raw
    start_key, stop_key = keys
    raise TomlRangeError(
        path,
        f"expected a table {{ {start_key} = …, {stop_key} = … }}",
        raw,
    )


@dataclass(frozen=True, slots=True)
class Bound[T]:
    """One inclusive interval parsed from a `{ from, to }` table."""

    start: T
    stop: T
    domain: Domain[T]

    @classmethod
    def parse(cls, raw: Any, domain: Domain[T], *, path: str = ".") -> Bound[T]:
        start_key, stop_key = domain.keys
        table = _as_table(raw, path=path, keys=domain.keys)
        extra = set(table) - {start_key, stop_key}
        if extra:
            raise TomlRangeError(
                path,
                f"unknown keys {sorted(extra)}",
                raw,
            )
        if start_key not in table or stop_key not in table:
            raise TomlRangeError(
                path,
                f"table must have keys {start_key!r} and {stop_key!r}",
                raw,
            )
        start = domain.convert(table[start_key], path=join_path(path, start_key))
        stop = domain.convert(table[stop_key], path=join_path(path, stop_key))
        if start > stop:  # type: ignore[operator]
            raise TomlRangeError(
                path,
                f"{start_key} ({start}) is after {stop_key} ({stop})",
                raw,
            )
        return cls(start, stop, domain)

    def _require_int(self) -> None:
        if type(self.start) is not int or type(self.stop) is not int:
            raise TypeError(f"{self.domain.name} width is only defined for int")

    @property
    def width(self) -> int:
        self._require_int()
        return self.stop - self.start + 1  # type: ignore[operator]

    def as_range(self) -> range:
        self._require_int()
        return range(self.start, self.stop + 1)  # type: ignore[arg-type]

    def as_tuple(self) -> tuple[T, T]:
        return (self.start, self.stop)

    def as_table(self) -> dict[str, T]:
        start_key, stop_key = self.domain.keys
        return {start_key: self.start, stop_key: self.stop}

    def __contains__(self, item: object) -> bool:
        if type(item) is not self.domain.typ:
            return False
        return self.start <= item <= self.stop  # type: ignore[operator]

    def __iter__(self) -> Iterator[T]:
        self._require_int()
        yield from self.as_range()  # type: ignore[misc]

    def __len__(self) -> int:
        self._require_int()
        return self.width

    def overlaps(self, other: Bound[T]) -> bool:
        return self.start <= other.stop and other.start <= self.stop  # type: ignore[operator]

    def adjacent_to(self, other: Bound[T]) -> bool:
        if self.domain.typ is not int:
            return False
        return self.stop + 1 == other.start or other.stop + 1 == self.start  # type: ignore[operator, return-value]

    def __repr__(self) -> str:
        return f"Bound({self.start!r}, {self.stop!r}, {self.domain.name})"


@dataclass(frozen=True, slots=True)
class Bounds[T]:
    """One table or an array of `{ from, to }` tables."""

    spans: tuple[Bound[T], ...]
    domain: Domain[T]

    @classmethod
    def parse(
        cls,
        raw: Any,
        domain: Domain[T],
        *,
        path: str = ".",
        overlap: Overlap = "reject",
    ) -> Bounds[T]:
        if isinstance(raw, Mapping):
            return cls((Bound.parse(raw, domain, path=path),), domain)
        if isinstance(raw, list):
            spans = tuple(
                Bound.parse(item, domain, path=index_path(path, i))
                for i, item in enumerate(raw)
            )
            return cls._apply_overlap(spans, domain, path=path, overlap=overlap)
        raise TomlRangeError(path, "expected a table or an array of tables", raw)

    @classmethod
    def _apply_overlap(
        cls,
        spans: tuple[Bound[T], ...],
        domain: Domain[T],
        *,
        path: str,
        overlap: Overlap,
    ) -> Bounds[T]:
        if overlap == "allow":
            return cls(spans, domain)
        if overlap == "merge":
            return cls(_coalesce(spans, domain), domain)
        if overlap != "reject":
            raise ValueError(f"unknown overlap policy {overlap!r}")
        for i, left in enumerate(spans):
            for j, right in enumerate(spans):
                if j <= i:
                    continue
                if left.overlaps(right):
                    raise TomlRangeError(
                        path,
                        f"{index_path(path, i)} overlaps {index_path(path, j)}",
                        (left.as_tuple(), right.as_tuple()),
                    )
        return cls(spans, domain)

    def merge(self) -> Bounds[T]:
        return Bounds(_coalesce(self.spans, self.domain), self.domain)

    def _require_int(self) -> None:
        if self.domain.typ is not int:
            raise TypeError(f"{self.domain.name} width is only defined for int")

    def covers(self, item: object) -> bool:
        return any(item in span for span in self.spans)

    def __contains__(self, item: object) -> bool:
        return self.covers(item)

    def __iter__(self) -> Iterator[T]:
        self._require_int()
        seen: set[T] = set()
        for span in self.spans:
            for item in span:
                if item in seen:
                    continue
                seen.add(item)
                yield item

    def __len__(self) -> int:
        self._require_int()
        return sum(1 for _ in self)

    def __repr__(self) -> str:
        inner = ", ".join(f"{s.start!r}..{s.stop!r}" for s in self.spans)
        return f"Bounds({inner}, {self.domain.name})"


def _coalesce[T](
    spans: tuple[Bound[T], ...], domain: Domain[T]
) -> tuple[Bound[T], ...]:
    if not spans:
        return ()
    ordered = sorted(spans, key=lambda s: (s.start, s.stop))
    out = [ordered[0]]
    for cur in ordered[1:]:
        prev = out[-1]
        if prev.overlaps(cur) or prev.adjacent_to(cur):
            stop = prev.stop if prev.stop >= cur.stop else cur.stop  # type: ignore[operator]
            out[-1] = Bound(prev.start, stop, domain)
        else:
            out.append(cur)
    return tuple(out)
