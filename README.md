# Provenance-Aware Relational Algebra Evaluator over Semiring-Annotated K-Relations

A standalone, engine-independent relational algebra evaluator that tracks data provenance via the K-Relations framework, parameterised over four commutative semirings.

---

## Overview

This system implements the K-Relations framework introduced by Green, Karvounarakis, and Tannen (2007), in which every tuple in a relation carries an annotation from a commutative semiring $(K, +, \cdot, 0, 1)$. By changing the semiring, the same evaluator produces different semantics: the Boolean semiring $\mathbb{B}$ recovers standard set semantics, the Counting semiring $\mathbb{N}$ gives bag semantics with integer multiplicities, the Boolean Function semiring $\mathbb{B}[X]$ annotates each tuple with a positive Boolean formula encoding lineage for probabilistic databases, and the Polynomial semiring $\mathbb{N}[X]$ provides full how-provenance via polynomial annotations recording every derivation path.

The evaluator implements five relational algebra operators — selection ($\sigma$), projection ($\pi$), cross product ($\times$), multiset sum ($\uplus$), and deduplication ($\delta$) — all defined purely in terms of semiring operations. Because $\delta$ requires a zero-test and cannot be a semiring homomorphism, the system formalises two deduplication strategies: **Existence** (collapse any nonzero annotation to $1_K$) and **How-Provenance** (pass the annotation through unchanged). A SQL-to-relational-algebra translator supports `SELECT [DISTINCT]`, multi-table `FROM` clauses, `WHERE` with `AND`/`OR`/`NOT`/`IN`/`LIKE`/`BETWEEN`, `DATE` literals with interval arithmetic, and `UNION`/`UNION ALL`.

Benchmarks on eight adapted TPC-H queries demonstrate that provenance tracking via Boolean functions incurs a consistent 1.4–1.8× overhead for typical multi-table queries, with the cross product operator as the dominant cost contributor. Catastrophic overhead arises only in pathological projection-collapse patterns where many tuples collapse to a single output key.

---

## Repository Structure

```
.
├── README.md
├── LICENSE                            # Project licence
├── requirements.txt                   # Python dependencies
│
├── benchmark/                         # Entry point — all five benchmarks (A–E) from the paper
│   ├── setup.sh                       # Environment setup: venv creation & dependency install
│   ├── generate_tpch_data.py          # TPC-H data generator (DuckDB-based, three scale factors)
│   ├── REPRODUCE.md                   # Step-by-step guide to reproduce all paper results
│   ├── run_benchmark_a.py             # Benchmark A: per-query BOOL vs BOOLFUNC comparison
│   ├── run_benchmark_b.py             # Benchmark B: scaling behaviour for Q3 across row limits
│   ├── run_benchmark_c.py             # Benchmark C: per-operator microbenchmarks
│   ├── run_benchmark_d.py             # Benchmark D: synthetic stress tests (8 workloads)
│   └── run_benchmark_e.py             # Benchmark E: TPC-H macrobenchmarks at SF 0.01/0.05/0.1
│
├── src/                               # Core library
│   ├── __init__.py
│   ├── evaluator.py                   # AST walker — dispatches nodes to operator functions
│   ├── sql_to_ra.py                   # SQL-to-RA translator (recursive-descent parser)
│   ├── strategies.py                  # DedupStrategy enum: EXISTENCE and HOW_PROVENANCE
│   │
│   ├── operators/                     # Pure implementations of the five RA operators
│   │   ├── __init__.py
│   │   ├── selection.py               # σ — filter tuples by predicate, copy annotation
│   │   ├── projection.py              # π — project onto attributes, accumulate via add()
│   │   ├── cross_product.py           # × — all tuple pairs, multiply annotations via mul()
│   │   ├── multiset_sum.py            # ⊎ — merge two relations, sum overlapping via add()
│   │   └── deduplication.py           # δ — collapse duplicates via zero-test + strategy
│   │
│   ├── parser/                        # Relational algebra expression parser
│   │   ├── __init__.py
│   │   ├── grammar.py                 # AST node classes (Alg, Cond, Atom subclasses)
│   │   └── parser.py                  # Tokeniser and recursive-descent parser for RA strings
│   │
│   ├── relation/                      # K-Relation data structure
│   │   ├── __init__.py
│   │   └── k_relation.py              # KRelation class: schema + dict[tuple → annotation]
│   │
│   ├── semirings/                     # Four commutative semiring implementations
│   │   ├── __init__.py
│   │   ├── base.py                    # Abstract Semiring interface (zero, one, add, mul, is_zero)
│   │   ├── boolean.py                 # 𝔹 — BooleanSemiring (set semantics)
│   │   ├── boolean_function.py        # 𝔹[X] — BoolFuncSemiring (positive Boolean formulas)
│   │   ├── counting.py                # ℕ — CountingSemiring (bag semantics)
│   │   └── polynomial.py              # ℕ[X] — PolynomialSemiring (full how-provenance)
│   │
│   └── io/                            # Data loading utilities
│       ├── __init__.py
│       └── tpch_loader.py             # TPC-H CSV/DuckDB loader → KRelation objects
│
├── test_sql_script/                   # Adapted TPC-H SQL queries (Q3, Q5, Q7, Q10, Q11, Q16, Q18, Q19)
│   ├── 3.sql
│   ├── 5.sql
│   ├── 7.sql
│   ├── 10.sql
│   ├── 11.sql
│   ├── 16.sql
│   ├── 18.sql
│   └── 19.sql
│
├── tests/                             # Test suite (unit + integration)
│   ├── __init__.py
│   ├── unit/                          # Unit tests for individual operators, semirings, etc.
│   │   ├── test_cross_product.py
│   │   ├── test_date_and_loader.py
│   │   ├── test_deduplication.py
│   │   ├── test_k_relation.py
│   │   ├── test_multiset_sum.py
│   │   ├── test_new_predicates.py
│   │   ├── test_projection.py
│   │   ├── test_selection.py
│   │   ├── test_semirings.py
│   │   └── test_sql_to_ra.py
│   └── integration/                   # Integration tests for parser and full pipeline
│       ├── test_parser.py
│       └── test_pipeline.py
│
└── report/
    └── paper.tex                      # Research paper (Springer LNCS format)
```

---

## Requirements and Installation

| Requirement    | Version                                   |
| -------------- | ----------------------------------------- |
| **Python**     | 3.12 or higher                            |
| **pytest**     | ≥ 7.0                                     |
| **duckdb**     | latest                                    |
| **matplotlib** | latest (optional — for Benchmark B chart) |

### Quick setup

```bash
# Option A: Automated setup (creates venv, installs dependencies)
bash benchmark/setup.sh
source venv/bin/activate

# Option B: Manual setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## Reproducing paper results

See [benchmark/REPRODUCE.md](benchmark/REPRODUCE.md) for the full step-by-step
instructions to reproduce all benchmark tables and figures from the paper.

---

## Semirings and Configuration

### Supported semirings

| Semiring        | Class name           | Singleton     | Semantics                                                                      |
| --------------- | -------------------- | ------------- | ------------------------------------------------------------------------------ |
| $\mathbb{B}$    | `BooleanSemiring`    | `BOOL_SR`     | Standard set semantics: a tuple is present ($\top$) or absent ($\bot$)         |
| $\mathbb{B}[X]$ | `BoolFuncSemiring`   | `BOOLFUNC_SR` | Positive Boolean formula annotations encoding sufficient witnesses for lineage |
| $\mathbb{N}$    | `CountingSemiring`   | `NAT_SR`      | Bag semantics with integer multiplicities                                      |
| $\mathbb{N}[X]$ | `PolynomialSemiring` | `POLY_SR`     | Full how-provenance via polynomial annotations recording every derivation path |

### Deduplication strategies

| Strategy           | Enum value                     | Formal rule                              | Semantics                                                    |
| ------------------ | ------------------------------ | ---------------------------------------- | ------------------------------------------------------------ |
| **Existence**      | `DedupStrategy.EXISTENCE`      | $\delta(R)(t) = 1_K$ if $R(t) \neq 0_K$  | Discards all annotation content; records only tuple presence |
| **How-Provenance** | `DedupStrategy.HOW_PROVENANCE` | $\delta(R)(t) = R(t)$ if $R(t) \neq 0_K$ | Preserves the complete annotation through deduplication      |

---

## Operators

| Operator      | Symbol          | Function          | Semiring operation | Complexity     | Description                                                             |
| ------------- | --------------- | ----------------- | ------------------ | -------------- | ----------------------------------------------------------------------- |
| Selection     | $\sigma_\theta$ | `selection()`     | identity (copy)    | $O(n)$         | Retain tuples satisfying predicate $\theta$; annotation unchanged       |
| Projection    | $\pi_A$         | `projection()`    | $+$ (`add`)        | $O(n)$         | Project onto attributes $A$; accumulate annotations of colliding tuples |
| Cross Product | $\times$        | `cross_product()` | $\cdot$ (`mul`)    | $O(n \cdot m)$ | Form all tuple pairs; multiply annotations                              |
| Multiset Sum  | $\uplus$        | `multiset_sum()`  | $+$ (`add`)        | $O(n + m)$     | Merge two relations; sum overlapping annotations                        |
| Deduplication | $\delta$        | `deduplication()` | zero-test; $f$     | $O(n)$         | Collapse duplicates; apply strategy $f$                                 |

---

## Running the Tests

The test suite is organised into unit tests (individual operators, semirings, K-Relations, predicates, SQL translator) and integration tests (parser round-trips, full SQL-to-result pipelines across all four semirings).

```bash
# Run the full test suite
pytest

# Run only unit tests
pytest tests/unit/

# Run only integration tests
pytest tests/integration/

# Run a specific test file
pytest tests/unit/test_selection.py

# Verbose output with individual test names
pytest -v
```

All tests are deterministic and require no external data or network access.
