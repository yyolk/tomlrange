from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from tomlrange.domain import Domain
from tomlrange.error import TomlRangeError
from tomlrange.paths import index_path, join_path

if TYPE_CHECKING:
    from tomlrange.paths import Overlap


def _as_table(raw: Any, *, path: str, keys: tuple[str, str]) -> Mapping[str, Any]:
    if isinstance(raw, Mapping):
        return raw
    start_key, stop_key = keys
    raise TomlRangeError(
        path,
        f"expected a table {{ {start_key} = …, {stop_key} = … }}",
        raw,
    )


def _hook(domain: object, name: str) -> Any:
    return getattr(domain, name, None)


def _wraps(domain: object) -> bool:
    """Cyclic walk: named members, or a stepped clock (not int wrap)."""
    return bool(_hook(domain, "wrap")) and (
        _hook(domain, "members") is not None or _hook(domain, "step") is not None
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
        if _inverted(domain, start, stop) and not _wraps(domain):
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
        hook = _hook(self.domain, "width")
        if callable(hook):
            return hook(self.start, self.stop)
        self._require_int()
        return self.stop - self.start + 1  # type: ignore[operator]

    def as_range(self) -> range:
        self._require_int()
        if _hook(self.domain, "members") is not None:
            raise TypeError(f"{self.domain.name} width is only defined for int")
        return range(self.start, self.stop + 1)  # type: ignore[arg-type]

    def as_tuple(self) -> tuple[T, T]:
        return (self.start, self.stop)

    def as_table(self) -> dict[str, T]:
        start_key, stop_key = self.domain.keys
        return {start_key: self.start, stop_key: self.stop}

    def __contains__(self, item: object) -> bool:
        if type(item) is not self.domain.typ:
            return False
        members = _hook(self.domain, "members")
        index = _hook(self.domain, "index")
        if members is not None and callable(index):
            if item not in members:
                return False
            i = index(self.start)
            j = index(self.stop)
            k = index(item)
            if i <= j:
                return i <= k <= j
            if _hook(self.domain, "wrap"):
                return k >= i or k <= j
            return False
        if _wraps(self.domain) and _inverted(self.domain, self.start, self.stop):
            return self.start <= item or item <= self.stop  # type: ignore[operator]
        return self.start <= item <= self.stop  # type: ignore[operator]

    def __iter__(self) -> Iterator[T]:
        walk = _hook(self.domain, "walk")
        if callable(walk):
            yield from walk(self.start, self.stop)
            return
        self._require_int()
        yield from self.as_range()  # type: ignore[misc]

    def __len__(self) -> int:
        return self.width

    def overlaps(self, other: Bound[T]) -> bool:
        walk = _hook(self.domain, "walk")
        if callable(walk) and (
            _hook(self.domain, "members") is not None
            or (
                _wraps(self.domain)
                and (
                    _inverted(self.domain, self.start, self.stop)
                    or _inverted(self.domain, other.start, other.stop)
                )
            )
        ):
            return bool(
                set(walk(self.start, self.stop)) & set(walk(other.start, other.stop))
            )
        return self.start <= other.stop and other.start <= self.stop  # type: ignore[operator]

    def adjacent_to(self, other: Bound[T]) -> bool:
        succ = _hook(self.domain, "successor")
        if callable(succ):
            return succ(self.stop) == other.start or succ(other.stop) == self.start
        return False

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

    def covers(self, item: object) -> bool:
        return any(item in span for span in self.spans)

    def __contains__(self, item: object) -> bool:
        return self.covers(item)

    def __iter__(self) -> Iterator[T]:
        seen: set[T] = set()
        for span in self.spans:
            for item in span:
                if item in seen:
                    continue
                seen.add(item)
                yield item

    def __len__(self) -> int:
        return sum(1 for _ in self)

    def __repr__(self) -> str:
        inner = ", ".join(f"{s.start!r}..{s.stop!r}" for s in self.spans)
        return f"Bounds({inner}, {self.domain.name})"


def _inverted(domain: Domain[Any], start: Any, stop: Any) -> bool:
    members = _hook(domain, "members")
    index = _hook(domain, "index")
    if members is not None and callable(index):
        return index(start) > index(stop)
    return start > stop


def _coalesce[T](
    spans: tuple[Bound[T], ...], domain: Domain[T]
) -> tuple[Bound[T], ...]:
    if not spans:
        return ()
    if _hook(domain, "members") is not None:
        return _coalesce_members(spans, domain)
    if _wraps(domain):
        return _coalesce_circular(spans, domain)
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


def _coalesce_members[T](
    spans: tuple[Bound[T], ...], domain: Domain[T]
) -> tuple[Bound[T], ...]:
    groups: list[set[T]] = [set(domain.walk(span.start, span.stop)) for span in spans]
    changed = True
    while changed:
        changed = False
        out: list[set[T]] = []
        used = [False] * len(groups)
        for i, group in enumerate(groups):
            if used[i]:
                continue
            acc = set(group)
            used[i] = True
            grew = True
            while grew:
                grew = False
                for j, other in enumerate(groups):
                    if used[j]:
                        continue
                    if acc & other or _sets_adjacent(acc, other, domain):
                        acc |= other
                        used[j] = True
                        grew = True
                        changed = True
            out.append(acc)
        groups = out
    bounds = [_bound_from_members(group, domain) for group in groups if group]
    bounds.sort(key=lambda span: domain.index(span.start))
    return tuple(bounds)


def _coalesce_circular[T](
    spans: tuple[Bound[T], ...], domain: Domain[T]
) -> tuple[Bound[T], ...]:
    groups: list[set[T]] = [set(domain.walk(span.start, span.stop)) for span in spans]
    changed = True
    while changed:
        changed = False
        out: list[set[T]] = []
        used = [False] * len(groups)
        for i, group in enumerate(groups):
            if used[i]:
                continue
            acc = set(group)
            used[i] = True
            grew = True
            while grew:
                grew = False
                for j, other in enumerate(groups):
                    if used[j]:
                        continue
                    if acc & other or _sets_adjacent(acc, other, domain):
                        acc |= other
                        used[j] = True
                        grew = True
                        changed = True
            out.append(acc)
        groups = out
    bounds = [_bound_from_ticks(group, domain) for group in groups if group]
    bounds.sort(key=lambda span: domain.index(span.start))
    return tuple(bounds)


def _bound_from_ticks[T](ticks: set[T], domain: Domain[T]) -> Bound[T]:
    ordered = sorted(ticks, key=domain.index)
    if len(ordered) == 1:
        return Bound(ordered[0], ordered[0], domain)
    succ = _hook(domain, "successor")
    gaps = [
        i
        for i in range(len(ordered) - 1)
        if not callable(succ) or succ(ordered[i]) != ordered[i + 1]
    ]
    if not gaps:
        return Bound(ordered[0], ordered[-1], domain)
    if _hook(domain, "wrap") and len(gaps) == 1:
        gap = gaps[0]
        return Bound(ordered[gap + 1], ordered[gap], domain)
    return Bound(ordered[0], ordered[-1], domain)


def _sets_adjacent[T](left: set[T], right: set[T], domain: Domain[T]) -> bool:
    succ = _hook(domain, "successor")
    if not callable(succ):
        return False
    return any(succ(item) in right for item in left) or any(
        succ(item) in left for item in right
    )


def _bound_from_members[T](members: set[T], domain: Domain[T]) -> Bound[T]:
    order = domain.members
    assert order is not None
    flags = [item in members for item in order]
    if all(flags):
        return Bound(order[0], order[-1], domain)
    n = len(flags)
    wrap = bool(_hook(domain, "wrap"))
    if wrap and flags[0] and flags[-1]:
        start_i = next(i for i in range(n) if flags[i] and not flags[(i - 1) % n])
        stop_i = next(i for i in range(n) if flags[i] and not flags[(i + 1) % n])
        return Bound(order[start_i], order[stop_i], domain)
    idxs = [i for i, flag in enumerate(flags) if flag]
    return Bound(order[idxs[0]], order[idxs[-1]], domain)
