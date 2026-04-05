# provenance-ra-evaluator

A Python library implementing **provenance-aware relational algebra** using the K-relations framework. Relational operators (σ, π, ×, ⊎, δ) are evaluated over relations annotated with semiring elements, so provenance information flows automatically through query pipelines.

---

## What is this?

In standard databases, operators like `SELECT`, `PROJECT`, and `DISTINCT` discard information about _where_ results came from. In **provenance-aware** databases, every tuple carries an annotation drawn from a semiring that tracks how and how many times it was derived.

This library implements five relational algebra operators over K-relations, all parameterised by a semiring. Swapping the semiring changes the provenance semantics without touching the operator logic.

**Operators:**

| Symbol | Operator      |
| ------ | ------------- |
| σ      | Selection     |
| π      | Projection    |
| ×      | Cross product |
| ⊎      | Multiset sum  |
| δ      | Deduplication |

**Supported semirings:**

| Semiring                | Python type  | Meaning                                                          |
| ----------------------- | ------------ | ---------------------------------------------------------------- |
| Boolean `𝔹`             | `bool`       | Set semantics — is the tuple present?                            |
| Boolean Function `𝔹[X]` | `BoolFunc`   | Provenance as a Boolean formula over tuple variables             |
| Counting `ℕ`            | `int`        | Bag semantics — how many times does it appear?                   |
| Polynomial `ℕ[X]`       | `Polynomial` | Full how-provenance — tracks derivation paths and multiplicities |

> The Boolean and Boolean Function semirings are the primary focus of this project. The Counting and Polynomial semirings are explored as extensions that go beyond the project requirements, demonstrating the generality of the K-relations framework.

---

## Quick start

**Prerequisites:** Python 3.9+

```bash
# Clone the repository
git clone https://github.com/NgChunMan/provenance-ra-evaluator.git
cd provenance-ra

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
python benchmarks/bench_pipeline.py
```

---

## SQL mode

The system includes a hand-written SQL-to-relational-algebra translator that supports a subset of SQL `SELECT`:

```bash
# Evaluate a SQL query against TPC-H CSV data
python main.py --sql "SELECT DISTINCT o_orderkey, o_orderdate FROM orders WHERE o_totalprice > 1000" \
    --table orders data/tpch/orders.csv \
    --semiring bool --strategy existence
```

**Supported SQL features:** `SELECT [DISTINCT]`, `FROM` (comma-separated tables), `WHERE`, `UNION` / `UNION ALL`, `AND`, `OR`, `NOT`, `IN`, `NOT IN`, `LIKE`, `NOT LIKE`, `BETWEEN`, `%` (modulo), `DATE` literals, `DATE + INTERVAL` arithmetic, and table/column aliases with `AS`.

**Not supported:** `GROUP BY`, `HAVING`, `ORDER BY`, `LIMIT`, `JOIN...ON`, subqueries, `INTERSECT`, `EXCEPT`.

---

## Data generation (TPC-H)

The project includes a script to generate [TPC-H](http://www.tpc.org/tpch/) benchmark data using DuckDB's built-in generator. The generated CSVs are committed to the repository under `data/tpch/` so that benchmarks are reproducible without requiring DuckDB at runtime.

```bash
# Generate with default scale factor (SF 0.01 ≈ 600 lineitem rows)
python -m scripts.generate_tpch_data

# Custom scale factor and row limit
python -m scripts.generate_tpch_data --sf 0.1 --limit 1000

# Custom output directory
python -m scripts.generate_tpch_data --sf 0.01 --output /path/to/dir
```

**Scale factor guidelines:**

| SF    | lineitem | orders | customer |
| ----- | -------- | ------ | -------- |
| 0.001 | ~60      | ~150   | ~150     |
| 0.01  | ~600     | 1 500  | 1 500    |
| 0.1   | ~6 000   | 15 000 | 15 000   |
| 1     | 6 M      | 1.5 M  | 150 000  |

The loader preserves native Python types for TPC-H columns: `int` for integer columns, `datetime.date` for date columns, `Decimal` for monetary/decimal columns, and `str` for text columns.

The TPC-H loader (`src/io/tpch_loader.py`) provides three entry points:

| Function                  | Description                                     |
| ------------------------- | ----------------------------------------------- |
| `load_tpch_from_duckdb()` | Generate data in-memory via DuckDB and load     |
| `generate_tpch_csvs()`    | Generate data via DuckDB and write to CSV files |
| `load_tpch_csvs()`        | Load pre-generated CSV files into KRelations    |

---

## Project layout

```
src/
├── semirings/
│   ├── base.py              # Abstract Semiring interface
│   ├── boolean.py           # Boolean semiring  (𝔹, ∨, ∧, False, True)
│   ├── boolean_function.py  # Boolean Function semiring (𝔹[X])
│   ├── counting.py          # Counting semiring (ℕ, +, ×, 0, 1)
│   └── polynomial.py        # Polynomial semiring + Monomial/Polynomial types
├── relation/
│   └── k_relation.py        # KRelation — an annotated table
├── operators/
│   ├── selection.py         # σ — filter rows by predicate
│   ├── projection.py        # π — drop columns, merge annotations
│   ├── cross_product.py     # × — cartesian product
│   ├── multiset_sum.py      # ⊎ — union of two K-relations
│   └── deduplication.py     # δ — collapse annotations to semiring.one()
├── parser/
│   ├── grammar.py           # Grammar rules and expression tree nodes
│   └── parser.py            # Tokeniser + recursive-descent parser
├── io/
│   ├── csv_loader.py        # Load CSV files into KRelation objects
│   └── tpch_loader.py       # TPC-H data generation and loading
├── sql_to_ra.py             # SQL → relational algebra translator
├── strategies.py            # DedupStrategy enum (EXISTENCE, HOW_PROVENANCE)
└── evaluator.py             # Walk expression tree, dispatch to operators

scripts/
└── generate_tpch_data.py    # CLI to generate TPC-H CSV data via DuckDB

data/
└── tpch/                    # Pre-generated TPC-H CSV data (SF 0.01)

test_sql_script/             # Simplified TPC-H SQL queries for benchmarks

tests/
├── unit/
│   ├── test_semirings.py
│   ├── test_k_relation.py
│   ├── test_selection.py
│   ├── test_projection.py
│   ├── test_cross_product.py
│   ├── test_multiset_sum.py
│   ├── test_deduplication.py
│   ├── test_new_predicates.py
│   └── test_sql_to_ra.py
└── integration/
    ├── test_parser.py
    └── test_pipeline.py     # End-to-end: query string → KRelation result

benchmarks/
└── bench_pipeline.py        # Full multi-operator pipeline benchmark

main.py          # Worked example + inline tests + benchmarks
README.md
requirements.txt
```

---

## References

- Green, Karvounarakis & Tannen. _Provenance Semirings._ PODS 2007.
