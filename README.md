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
git clone https://github.com/your-username/provenance-ra.git
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
python benchmarks/bench_deduplication.py
python benchmarks/bench_pipeline.py
```

---

## Project layout

```
src/
├── semirings/
│   ├── base.py            # Abstract Semiring interface
│   ├── boolean.py         # Boolean semiring  (𝔹, ∨, ∧, False, True)
│   ├── counting.py        # Counting semiring (ℕ, +, ×, 0, 1)
│   └── polynomial.py      # Polynomial semiring + Monomial/Polynomial types
├── relation/
│   └── k_relation.py      # KRelation — an annotated table
├── operators/
│   ├── selection.py       # σ — filter rows by predicate
│   ├── projection.py      # π — drop columns, merge annotations
│   ├── cross_product.py   # × — cartesian product
│   ├── multiset_sum.py    # ⊎ — union of two K-relations
│   └── deduplication.py   # δ — collapse annotations to semiring.one()
├── parser/
│   ├── tokenizer.py       # Lexer: expression string → token list
│   ├── grammar.py         # Grammar rules and expression tree nodes
│   └── parser.py          # Token list → expression tree
├── io/
│   └── csv_loader.py      # Load CSV files into KRelation objects
├── strategies.py          # DedupStrategy enum (EXISTENCE, LINEAGE)
└── evaluator.py           # Walk expression tree, dispatch to operators

tests/
├── unit/
│   ├── test_semirings.py
│   ├── test_k_relation.py
│   ├── test_selection.py
│   ├── test_projection.py
│   ├── test_cross_product.py
│   ├── test_multiset_sum.py
│   └── test_deduplication.py
└── integration/
    ├── test_parser.py
    └── test_pipeline.py   # End-to-end: query string → KRelation result

benchmarks/
├── bench_deduplication.py # δ operator in isolation (time + memory)
└── bench_pipeline.py      # Full multi-operator pipeline benchmark

main.py          # Worked example + inline tests + benchmarks
README.md
requirements.txt
```

---

## References

- Green, Karvounarakis & Tannen. _Provenance Semirings._ PODS 2007.
