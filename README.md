# tomlrange

[![PyPI version](https://img.shields.io/pypi/v/tomlrange.svg)](https://pypi.org/project/tomlrange/)
[![Python versions](https://img.shields.io/pypi/pyversions/tomlrange.svg)](https://pypi.org/project/tomlrange/)
[![CI](https://img.shields.io/github/actions/workflow/status/yyolk/tomlrange/ci.yml?branch=main)](https://github.com/yyolk/tomlrange/actions/workflows/ci.yml)
[![License](https://img.shields.io/github/license/yyolk/tomlrange)](https://github.com/yyolk/tomlrange/blob/main/LICENSE)
[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/yyolk/tomlrange/main.svg)](https://results.pre-commit.ci/latest/github/yyolk/tomlrange/main)

Parse and validate `{ from = …, to = … }` tables. Not a TOML parser —
feed it the dicts `tomllib` already produced.

The four spellings below are alternatives, not one document — a
`[table]` header owns every following key until the next header.
After `tomllib`, they collapse to two Python values. `Bound` accepts
a single table. `Bounds` accepts a table or a list of tables.

```toml
# one table
months = { from = 1, to = 12 }

[months]
from = 1
to = 12

# many tables
windows = [
    { from = 1, to = 4 },
    { from = 6, to = 10 },
]

[[windows]]
from = 1
to = 4

[[windows]]
from = 6
to = 10
```

```python
import tomllib
from tomlrange import Domain

Month = Domain(int, lo=1, hi=12, name="month")

data = tomllib.loads(config)
year = Month.bound(data["months"])  # 1..12
windows = Month.bounds(data["windows"])  # 1..4 and 6..10

assert list(year) == list(range(1, 13))
assert 5 not in windows
```

No runtime dependencies. Endpoints stay the type `tomllib` gave you.

## Domain as schema

A `Domain` is the constraint object. `Bound` / `Bounds` are the values.

```python
from tomlrange import Domain

Hour = Domain(int, lo=0, hi=23, name="hour")
Hour.bound({"from": 7, "to": 16})
Hour.full()  # requires lo and hi
```

Or name the domain by subclassing `Spec` — the class body is the schema:

```python
from tomlrange import Spec


class Month(Spec):
    typ = int
    lo = 1
    hi = 12


Month.parse({"from": 1, "to": 4})
Month.parse_many([{"from": 1, "to": 4}, {"from": 6, "to": 10}])
```

Named discrete order is `members`. `wrap=True` is a cyclic topology — `from`
after `to` walks across the seam. `from == to` stays a singleton; the full
cycle is `full()`. `aliases` canonicalize extra spellings (any key type)
onto a member.

The built-in `Weekday` is that schema: `mon`…`sun`, `wrap=True`, plus long
names, two-letter shorts, and ISO weekday numbers 1–7.

```python
from tomlrange import Weekday

list(Weekday.parse({"from": "sat", "to": "mon"}))  # sat, sun, mon
list(Weekday.parse({"from": "friday", "to": "sat"}))  # fri, sat
list(Weekday.parse({"from": 1, "to": 3}))  # mon, tue, wed
```

Built-in `Color` is the linear Roy G. Biv rainbow (`wrap=False`). Letter
and full-name aliases (`r`, `o`, `y`, `g`, `b`, `i`, `v` plus names) use
the same `aliases=` field as `Weekday`. Inverted tables error the same
way inverted ints do.

```python
from tomlrange import Color

list(Color.parse({"from": "red", "to": "violet"}))
list(Color.parse({"from": "o", "to": "g"}))  # orange, yellow, green
```

## Validation

On one table:

- value is a mapping
- keys are exactly `from` and `to` (override with `Domain(..., keys=("start", "end"))`)
- each endpoint is `type(raw) is domain.typ` (so `1.0` and `True` are not `int`)
- endpoints sit inside `lo` / `hi` when those are set
- when `members` is set, each endpoint is a member or an `aliases` spelling
  (unknown → error at `from` / `to`)
- `from <= to` in domain order (a singleton is `{ from = 3, to = 3 }`); with
  `wrap=True`, `from` after `to` is a seam walk, not an error

On a list, `overlap=` is `"reject"` (default), `"allow"`, or `"merge"`.
Reject treats a shared endpoint as overlap (`1–4` and `4–6` fail).
Adjacent integers (`1–4` then `5–8`) are fine; `merge()` will coalesce them.
Member domains overlap and merge on member identity, not string order.

`list()`, `len()`, and `width` work for `int` and for `members`. `as_range()`
is int-only. Other ordered `typ`s raise `TypeError`
(`"{name} width is only defined for int"`). Membership, `as_tuple()`, and
`as_table()` work for any ordered `typ`.

Errors carry a path:

```
months_ranges[1].to: 13 is above month 12
```

## What this is not

- Not a file loader. Call `tomllib` yourself.
- Not string ranges (`"1-12"`, `"Jan–Apr"`).
- Not a two-element array (`[1, 12]`). After TOML decode that is a list, not a table.
- Not wrap-around unless the domain sets `wrap=True`.
- Not `step`. A range table is a closed interval.
- Not a free-for-all `str` domain. Names need `members`.
- Not iteration over a non-int domain without `members`. Walk dates yourself.

## Install

```
pip install tomlrange
```

Python 3.14+.
