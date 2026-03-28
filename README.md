# provenance-dedup

A Python library that implements the **deduplication operator (δ)** from provenance-aware relational algebra. It lets you deduplicate annotated relations (K-relations) while choosing how much provenance information to retain.

---

## What is this?

In standard databases, `SELECT DISTINCT` simply removes duplicate rows. In **provenance-aware** databases, every row carries an annotation (drawn from a semiring) that tracks _how_ and _how many times_ it was derived. Naively deduplicating discards that information.

This library implements two strategies that let you control the trade-off:

| Strategy    | What the annotation becomes           | Provenance kept                                   |
| ----------- | ------------------------------------- | ------------------------------------------------- |
| `EXISTENCE` | `1` (semiring identity)               | None — only presence recorded                     |
| `LINEAGE`   | `frozenset` of contributing tuple IDs | Which input tuples contributed (_why-provenance_) |

**Supported semirings:**

| Semiring          | Python type  | Meaning                                                |
| ----------------- | ------------ | ------------------------------------------------------ |
| Boolean `𝔹`       | `bool`       | Set semantics — is the tuple present?                  |
| Counting `ℕ`      | `int`        | Bag semantics — how many times does it appear?         |
| Polynomial `K[x]` | `Polynomial` | Full provenance — tracks derivation paths symbolically |

---

## Quick start

**Prerequisites:** Python 3.9+

```bash
# Clone the repository
git clone https://github.com/your-username/provenance-dedup.git
cd provenance-dedup

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate        # macOS/Linux
# venv\Scripts\activate         # Windows

# Install dependencies
pip install -r requirements.txt
```

Run the full worked example, correctness tests, and benchmarks:

```bash
python main.py
```

Run only the test suite:

```bash
python -m pytest tests/ -v
```

Run only the benchmarks:

```bash
python -m benchmarks.bench_deduplication
```

---

## Usage example

```python
from provenance_dedup.semirings import POLY_SR
from provenance_dedup.semirings.polynomial import Polynomial
from provenance_dedup.relation.k_relation import KRelation
from provenance_dedup.operators.deduplication import deduplication
from provenance_dedup.strategies import DedupStrategy

# Build an annotated relation where each tuple has a polynomial annotation.
# This annotation might come from a prior join or projection.
rel = KRelation(["Name"], POLY_SR)
t1, t2 = Polynomial.from_var("t1"), Polynomial.from_var("t2")
rel._set_raw(("Alice",), t1.multiply(t1).add(t2))  # Alice → t1² + t2

# EXISTENCE: forget provenance, just record that Alice is present
out_existence = deduplication(rel, DedupStrategy.EXISTENCE)
# Alice → Polynomial.one()  (i.e. 1)

# LINEAGE: record which input tuple IDs contributed
out_lineage = deduplication(rel, DedupStrategy.LINEAGE)
# Alice → frozenset({'t1', 't2'})
```

---

## Project layout

```
provenance_dedup/
├── semirings/
│   ├── base.py         # Abstract Semiring interface
│   ├── boolean.py      # Boolean semiring  (𝔹, ∨, ∧, False, True)
│   ├── counting.py     # Counting semiring (ℕ, +, ×, 0, 1)
│   └── polynomial.py   # Polynomial semiring + Monomial/Polynomial types
├── relation/
│   └── k_relation.py   # KRelation — an annotated table
├── operators/
│   └── deduplication.py  # δ operator implementation
└── strategies.py       # DedupStrategy enum (EXISTENCE, LINEAGE)

tests/
└── test_deduplication.py   # 9 correctness tests, 19 assertions

benchmarks/
└── bench_deduplication.py  # Time and memory benchmarks

main.py          # Worked example + inline tests + benchmarks
README.md
requirements.txt
```

---

## Key concepts

- **K-relation:** A relation where every tuple is annotated with an element from a semiring K, generalising both set and bag semantics.
- **Semiring:** An algebraic structure `(K, +, ·, 0, 1)` — addition models union/projection, multiplication models joins.
- **δ (deduplication):** Maps a K-relation to one where each present tuple's annotation is replaced according to the chosen strategy.

---

## Running tests

```bash
python -m pytest tests/ -v
```

9 tests cover: polynomial annotations, Boolean semiring, counting semiring, zero-annotation exclusion, idempotence, and error handling.
