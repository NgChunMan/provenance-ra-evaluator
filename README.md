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
python -m benchmarks.bench_pipeline --mode all
```

The benchmark harness has four layers, corresponding to the benchmarks described in the paper:

- **Benchmark C — Per-operator microbenchmarks:** six isolated workloads (σ, π, ×, ⊎, δ × 2 strategies) comparing BOOL_SR versus BOOLFUNC_SR on a small synthetic K-relation; completes in seconds
- **Benchmark D — Provenance overhead microbenchmarks:** synthetic workloads that isolate add-heavy and mul-heavy provenance choke-points; includes two paired deduplication workloads (`dedup_existence_downstream` / `dedup_howprov_downstream`) that demonstrate the downstream cost of retaining provenance formulas through δ HOW_PROVENANCE versus discarding them with δ EXISTENCE
- **Benchmark E — TPC-H macrobenchmarks:** curated TPC-H pipelines where the timed region excludes CSV loading and tuple-variable assignment, so the comparison focuses on relational execution with and without provenance
- **Benchmarks A & B — Per-query comparison and scaling:** opt-in translated SQL benchmarks over the simplified TPC-H query scripts in test_sql_script/, comparing plain Boolean annotations against BoolFunc provenance with translation and parsing excluded from timing

Macro stress runs can take a long time. The harness now prints cache preparation, source loading, and per-workload and per-sample progress so long runs do not look stalled. This matters for `BOOLFUNC_SR` with `--macro-suite stress`, because the evaluator materializes cross products before filtering and symbolic formulas can grow quickly.

The translated SQL layer is opt-in because the evaluator has no join optimizer. Those runs are still useful, but they measure the cost of symbolic provenance on the exact simplified SQL plans rather than the pushdown-heavy curated macro pipelines.

## Benchmark workflows

Use the following commands depending on what you want to measure. The benchmark labels (A–E) refer to the corresponding sections in the paper.

Run the full default harness (Benchmarks C + D + E):

```bash
python -m benchmarks.bench_pipeline --mode all
```

This runs per-operator (C), synthetic micro (D), and TPC-H macro (E) benchmarks on the committed CSV snapshot in `data/tpch/`.

Run only the per-operator benchmarks (Benchmark C — per-operator isolation):

```bash
python -m benchmarks.bench_pipeline --mode operator
```

This runs six isolated operator workloads (σ, π, ×, ⊎, δ × 2 strategies) comparing BOOL_SR versus BOOLFUNC_SR and completes in seconds. Use `--operator-size` to control the relation size (default: 10, matching the paper's Table 3).

Run only the synthetic microbenchmarks (Benchmark D — provenance overhead):

```bash
python -m benchmarks.bench_pipeline --mode micro
```

This is the fastest way to isolate provenance overhead in projection, union, and cross-product choke points without involving TPC-H CSV loading.

Run only the standard macro suite on the committed TPC-H CSVs (Benchmark E — TPC-H macrobenchmarks):

```bash
python -m benchmarks.bench_pipeline --mode macro --macro-suite standard
```

This is the safest macro entry point. It uses the committed `SF≈0.01` CSVs and avoids the heaviest stress workloads.

Run the translated SQL semiring benchmarks on the committed query scripts (Benchmarks A & B — per-query comparison and scaling):

```bash
python -m benchmarks.bench_pipeline --mode sql --sql-workloads q3
```

This benchmarks one simplified TPC-H SQL query from `test_sql_script/` using `BOOL_SR` versus `BOOLFUNC_SR`. SQL comment stripping, translation, and RA parsing happen outside the timed region. If `--tpch-limit` is omitted, SQL mode automatically applies a conservative per-workload row cap so the naive translated cross-product plans stay runnable.

Run the SQL layer one script at a time for publication-quality reproduction (Benchmark A):

```bash
python -m benchmarks.bench_pipeline --mode sql --sql-workloads q11
python -m benchmarks.bench_pipeline --mode sql --sql-workloads q16
python -m benchmarks.bench_pipeline --mode sql --sql-workloads q19
```

This is now the intended SQL workflow. Running one workload per command is easier to reproduce, easier to resume if one query is slow, and a better fit for publication-quality reporting.

Raise or lower the automatic SQL cap:

```bash
python -m benchmarks.bench_pipeline --mode sql --sql-max-cross-product 2000000 --repeat 1 --warmup 0
```

This controls the automatic per-workload cap used only when `--tpch-limit` is not set. Higher values benchmark larger translated SQL intermediates but can become slow or get killed on the heaviest 6-table queries.

Run every layer, including translated SQL, in one command (Benchmarks A + B + C + D + E):

```bash
python -m benchmarks.bench_pipeline --mode full --sql-workloads q3
```

This keeps the original `--mode all` behavior intact for the lighter default run while still allowing one publication-quality SQL workload to be included explicitly.

Run the stress suite on generated cached CSV snapshots (Benchmark E at multiple scale factors):

```bash
python -m benchmarks.bench_pipeline --mode macro --macro-suite stress --tpch-sf 0.01 0.05 0.1
```

The first run generates CSV snapshots under `.bench_cache/tpch/`. Later runs reuse those cached files. This command can take a long time with `BOOLFUNC_SR`, especially for `sf=0.1`.

Run a quick smoke test before attempting a long sweep:

```bash
python -m benchmarks.bench_pipeline --mode macro --macro-suite stress --tpch-sf 0.01 --repeat 1 --warmup 0 --tpch-limit 5000
```

This keeps the data size and repetition count small so you can confirm the workload shape and runtime first.

Split the stress suite into one workload per command so each result returns separately:

```bash
python -m benchmarks.bench_pipeline --mode macro --macro-suite stress --tpch-sf 0.1 --macro-workloads orders_lineitem_shipmode --repeat 1 --warmup 0
python -m benchmarks.bench_pipeline --mode macro --macro-suite stress --tpch-sf 0.1 --macro-workloads asia_lineitem_supplier_singleton --repeat 1 --warmup 0
```

This is the most practical way to benchmark the expensive stress workloads. If one workload takes several minutes, you still get the completed result for the other one immediately.

Use the faster deduplication strategy when you only need existence semantics after `DISTINCT`:

```bash
python -m benchmarks.bench_pipeline --mode macro --macro-suite stress --tpch-sf 0.1 --macro-strategy existence --repeat 1 --warmup 0
```

`HOW_PROVENANCE` preserves full annotations through deduplication and is much more expensive on low-cardinality outputs. `EXISTENCE` collapses each surviving annotation to `one()`.

Store generated CSV snapshots in a custom cache directory:

```bash
python -m benchmarks.bench_pipeline --mode macro --macro-suite stress --tpch-sf 0.01 0.05 --tpch-cache-dir /path/to/tpch-cache
```

This is useful if you want to keep large generated snapshots outside the repository root.

## How to get results back

For long Benchmark E macro stress runs, do not start with the full sweep and default repeat count.

1. Start with `--repeat 1 --warmup 0` to measure one sample per workload.
2. Add `--tpch-limit` for a bounded smoke run if you are unsure how large the intermediates will be.
3. Use `--macro-workloads` to run one workload at a time.
4. Add scale factors one by one instead of sweeping `0.01 0.05 0.1` immediately.
5. Increase `--repeat` only after the runtime is acceptable for one complete pass.

This staged approach is important because the Benchmark E stress suite uses explicit cross products followed by selections. On larger TPC-H snapshots, a single `BOOLFUNC_SR` sample can take minutes.

## Benchmark CLI options

The benchmark harness is driven by `benchmarks/bench_pipeline.py`.

| Option                                        | Meaning                                                                  | Typical use                                                                                                              |
| --------------------------------------------- | ------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------ |
| `--mode {all,operator,micro,macro,sql,full}`  | Choose which benchmark layer(s) to run.                                  | `operator` runs Benchmark C alone; `all` runs C+D+E; `sql` runs Benchmarks A & B; `full` runs every layer.               |
| `--operator-size INT`                         | Rows per relation in Benchmark C per-operator workloads.                 | Default 10 matches the paper's Table 3 (10 rows/table); increase for more stable μs measurements.                        |
| `--size INT`                                  | Row count for linear micro workloads (Benchmark D).                      | Increase when stress-testing projection and selection microbenchmarks.                                                   |
| `--cross-size INT`                            | Rows per side for synthetic dense cross products (Benchmark D).          | Increase when studying cartesian-product overhead in microbenchmarks.                                                    |
| `--formula-width INT`                         | Clause width for one-row symbolic micro stress cases (Benchmark D).      | Increase when measuring DNF growth in `union_wide_formulas`, `symbolic_mul_choke_point`, and `dedup_howprov_downstream`. |
| `--repeat INT`                                | Number of timed repetitions per workload.                                | Use `1` for quick runs, then increase for more stable medians.                                                           |
| `--warmup INT`                                | Number of untimed warm-up executions per workload.                       | Set to `0` for a quick smoke run.                                                                                        |
| `--tpch-csv-dir PATH`                         | Directory containing committed or pre-generated TPC-H CSVs.              | Point at `data/tpch/` or another CSV snapshot.                                                                           |
| `--tpch-cache-dir PATH`                       | Cache directory for generated `--tpch-sf` snapshots.                     | Move large generated CSVs outside the repo root if needed.                                                               |
| `--tpch-sf FLOAT [FLOAT ...]`                 | Generate and benchmark one or more TPC-H scale factors as CSV snapshots. | Example: `--tpch-sf 0.01 0.05 0.1`.                                                                                      |
| `--tpch-limit INT`                            | Cap rows loaded from each TPC-H table.                                   | Use for smoke tests and conservative higher-SF runs.                                                                     |
| `--macro-suite {standard,stress,both}`        | Select which curated TPC-H workload set to run (Benchmark E).            | Start with `standard`; use `stress` only when you want the heavy provenance cases.                                       |
| `--macro-workloads NAME [NAME ...]`           | Run only selected workload names from the chosen suite.                  | Split heavy stress workloads into separate commands.                                                                     |
| `--macro-strategy {existence,how_provenance}` | Choose how deduplication behaves in macro workloads.                     | `existence` is faster; `how_provenance` preserves full annotations.                                                      |
| `--sql-dir PATH`                              | Directory containing simplified SQL workload files.                      | Defaults to `test_sql_script/`; point elsewhere if you add more translated workloads.                                    |
| `--sql-workloads NAME`                        | Run exactly one selected SQL workload from the SQL directory.            | Example: `--sql-workloads q3` or `--sql-workloads 19`.                                                                   |
| `--sql-strategy {existence,how_provenance}`   | Choose how deduplication behaves in SQL workloads.                       | `how_provenance` is the most informative BoolFunc comparison; `existence` is the lighter control.                        |
| `--sql-max-cross-product INT`                 | Automatic SQL safety cap when `--tpch-limit` is omitted.                 | Keeps naive translated SQL plans runnable by bounding the implied cartesian-product size per workload.                   |

Available macro workload names are:

- `nation_region_lookup`
- `supplier_region_collapse`
- `building_segment_singleton`
- `orders_lineitem_shipmode`
- `asia_lineitem_supplier_singleton`

Available SQL workload names are:

- `q3`
- `q5`
- `q7`
- `q10`
- `q11`
- `q16`
- `q18`
- `q19`

You can always inspect the current CLI help directly:

```bash
python -m benchmarks.bench_pipeline --help
```

## Paper replication

For paper replication, do not require the replicating reader to regenerate the heavy TPC-H cache locally. Instead, publish the pre-generated cache as a GitHub Release asset and keep the repository itself focused on source code and the smaller committed `data/tpch/` snapshot.

The repository can generate a local release-preparation bundle under `artifacts/paper-replication/`. Generate or refresh it with:

```bash
source venv/bin/activate
python scripts/prepare_paper_replication_bundle.py
```

This prepares:

- `provenance-ra-bench-cache-sf-0.01-0.05-0.1.tar.gz`
- `SHA256SUMS.txt`
- `ENVIRONMENT.md`
- `pip-freeze.txt`
- `COMMANDS.md`
- `RESULTS.md`
- raw benchmark logs under `artifacts/paper-replication/raw-outputs/`

When creating the paper replication release, upload those files as GitHub Release assets. The recommended release asset set is the cache archive, checksum file, commands file, results file, environment file, and raw output logs.

After downloading the release assets, a reader can restore the pre-generated cache like this from the repository root:

```bash
curl -L -o provenance-ra-bench-cache-sf-0.01-0.05-0.1.tar.gz <release-asset-url>
curl -L -o SHA256SUMS.txt <release-checksum-url>
shasum -a 256 provenance-ra-bench-cache-sf-0.01-0.05-0.1.tar.gz
tar -xzf provenance-ra-bench-cache-sf-0.01-0.05-0.1.tar.gz
```

Compare the printed SHA-256 digest with `SHA256SUMS.txt`. Extracting the archive at the repository root restores `.bench_cache/tpch/`, so the heavy macro benchmarks can run without DuckDB cache generation.

The exact paper-replication benchmark commands and the recorded outputs from this machine are documented in `artifacts/paper-replication/COMMANDS.md` and `artifacts/paper-replication/RESULTS.md`. The bundled commands intentionally split the stress suite into one workload per command and use `--repeat 1 --warmup 0`, because that is the most practical way for a project supervisor to reproduce the heavy cases without waiting for a monolithic run.

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
│   ├── test_sql_to_ra.py
│   ├── test_date_and_loader.py
│   ├── test_bench_pipeline.py
│   ├── test_operator_benchmark.py
│   └── test_micro_benchmark.py  # Benchmark D dedup downstream workload contracts
└── integration/
    ├── test_parser.py
    └── test_pipeline.py     # End-to-end: query string → KRelation result

benchmarks/
├── __init__.py          # package marker
├── bench_pipeline.py    # thin CLI entry point (main() + argparse only)
├── _common.py           # dataclasses, shared utilities, path constants
├── _tpch.py             # TPC-H source resolution + annotation factory
├── _operator.py         # per-operator benchmark layer (Benchmark C)
├── _micro.py            # micro benchmark layer (Benchmark D)
├── _macro.py            # macro benchmark layer (Benchmark E)
└── _sql.py              # SQL benchmark layer (Benchmarks A & B)

main.py          # Worked example + inline tests + benchmarks
README.md
requirements.txt
```

---

## References

- Green, Karvounarakis & Tannen. _Provenance Semirings._ PODS 2007.
