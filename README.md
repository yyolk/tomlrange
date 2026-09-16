# tomlrange

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
year = Month.bound(data["months"])       # 1..12
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
Month.parse_many([{ "from": 1, "to": 4 }, { "from": 6, "to": 10 }])
```

## Validation

On one table:

- value is a mapping
- keys are exactly `from` and `to` (override with `Domain(..., keys=("start", "end"))`)
- each endpoint is `type(raw) is domain.typ` (so `1.0` and `True` are not `int`)
- endpoints sit inside `lo` / `hi` when those are set
- `from <= to` (a singleton is `{ from = 3, to = 3 }`)

On a list, `overlap=` is `"reject"` (default), `"allow"`, or `"merge"`.
Reject treats a shared endpoint as overlap (`1–4` and `4–6` fail).
Adjacent integers (`1–4` then `5–8`) are fine; `merge()` will coalesce them.

Errors carry a path:

```
months_ranges[1].to: 13 is above month 12
```

## What this is not

- Not a file loader. Call `tomllib` yourself.
- Not string ranges (`"1-12"`, `"Jan–Apr"`).
- Not a two-element array (`[1, 12]`). After TOML decode that is a list, not a table.
- Not wrap-around (`from = 11, to = 2`). Write two spans.
- Not `step`. A range table is a closed interval.

## Install

```
pip install tomlrange
```

Python 3.12+.
