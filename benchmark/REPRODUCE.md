# Replication Guide

## Provenance-Aware Relational Algebra Evaluator — Benchmark Reproduction

This guide walks through reproducing all benchmark results from the paper
_"Provenance-Aware Relational Algebra Evaluator over Semiring-Annotated K-Relations"_.

> All benchmarks use median-of-7 timed repetitions after 1 warm-up run, with garbage collection disabled during timing.

---

## Prerequisites

| Requirement        | Details                                          |
| ------------------ | ------------------------------------------------ |
| **Python**         | 3.12 or higher (`python3 --version`)             |
| **OS**             | Tested on macOS (Apple M1) with CPython 3.12     |
| **Disk space**     | ~10 MB for TPC-H data at all three scale factors |
| **Project folder** | Already cloned/open locally                      |

---

## Step 1 — Set up the environment

```bash
bash benchmark/setup.sh
source venv/bin/activate
```

This creates a Python virtual environment, installs all dependencies
(pytest, duckdb, matplotlib), and confirms the setup.

---

## Step 2 — Generate TPC-H data

Generate specification-conformant TPC-H data at three scale factors using DuckDB's
built-in generator:

```bash
python benchmark/generate_tpch_data.py --sf 0.01 --output-dir ./benchmark/tpch_data/sf001
python benchmark/generate_tpch_data.py --sf 0.05 --output-dir ./benchmark/tpch_data/sf005
python benchmark/generate_tpch_data.py --sf 0.1  --output-dir ./benchmark/tpch_data/sf010
```

### Expected row counts

| Table        | SF 0.01 | SF 0.05 | SF 0.1 |
| ------------ | ------- | ------- | ------ |
| **nation**   | 25      | 25      | 25     |
| **region**   | 5       | 5       | 5      |
| **supplier** | 100     | 500     | 1,000  |
| **customer** | 1,500   | 7,500   | 15,000 |
| **orders**   | 150     | 750     | 1,500  |
| **lineitem** | 600     | 3,000   | 6,000  |
| **part**     | 200     | 1,000   | 2,000  |
| **partsupp** | 800     | 4,000   | 8,000  |

Each CSV file has the format: type hints (line 1), column names (line 2), data (line 3+).

---

## Step 3 — Run individual benchmarks

> All results referenced in the paper are produced using the default configuration of each benchmark script (i.e. without overriding any flags).

### Benchmark A — Per-query comparison (Table 5)

Compares `BooleanSemiring` (baseline) against `BoolFuncSemiring` (provenance) on 8 adapted TPC-H queries (Q3, Q5, Q7, Q10, Q11, Q16, Q18, Q19) with Existence deduplication. Measures per-query wall-clock time and overhead ratio.

```bash
python benchmark/run_benchmark_a.py --data-dir ./benchmark/tpch_data/sf001
```

| Parameter      | Flag          | Default      |
| -------------- | ------------- | ------------ |
| Row limit      | `--row-limit` | 10           |
| Data directory | `--data-dir`  | `data/tpch/` |
| Repetitions    | `--reps`      | 7            |

**Paper reference**: Table 5 — provenance overhead is consistent at 1.4–1.8× across all queries.

### Benchmark B — Scaling behaviour (Table 6 / Figure 2)

Runs Q3 (customer–orders–lineitem join) at row limits 5, 10, 15, 20, 25, 30 to measure how overhead scales with data size. Generates `benchmark_b_scaling.png` if `matplotlib` is installed.

```bash
python benchmark/run_benchmark_b.py --data-dir ./benchmark/tpch_data/sf001
```

| Parameter      | Flag         | Default      |
| -------------- | ------------ | ------------ |
| Data directory | `--data-dir` | `data/tpch/` |
| Repetitions    | `--reps`     | 7            |

**Paper reference**: Table 6 and Figure 2 — overhead ratio stabilises at 1.4x–1.6x. as both configurations scale super-linearly.

### Benchmark C — Per-operator microbenchmarks (Table 7)

Isolates provenance overhead for each operator individually (σ, π, ×, ⊎, δ∃, δhow). Baseline: `BOOL_SR` (Boolean semiring); provenance: `BOOLFUNC_SR`.

```bash
python benchmark/run_benchmark_c.py
```

| Parameter   | Flag     | Default |
| ----------- | -------- | ------- |
| Repetitions | `--reps` | 7       |

**Paper reference**: Table 7 — cross product is the dominant overhead source (6.0×); selection is virtually free (1.1×).

### Benchmark D — Synthetic stress tests (Table 8)

Eight synthetic workloads targeting specific bottlenecks: formula accumulation (`add`), formula multiplication (`mul`), and deduplication downstream cost. Baseline: `CountingSemiring` (`NAT_SR`); provenance: `BoolFuncSemiring` (`BOOLFUNC_SR`).

```bash
python benchmark/run_benchmark_d.py
```

| Parameter     | Flag              | Default |
| ------------- | ----------------- | ------- |
| Input size    | `--size`          | 128     |
| Cross size    | `--cross-size`    | 48      |
| Formula width | `--formula-width` | 48      |
| Repetitions   | `--reps`          | 7       |

> **Note**: The `symbolic_mul_choke_point` workload may take up to 60 seconds — this is expected.

**Paper reference**: Table 8 — projection-after-cross-product is the critical bottleneck (up to ~1.3×10⁶× on worst cases).

### Benchmark E — TPC-H macrobenchmarks at multiple scale factors (Table 9)

Five curated operator pipelines on TPC-H data at SF 0.01, 0.05, and 0.1. Uses How-Provenance deduplication. Baseline: `CountingSemiring` (`NAT_SR`); provenance: `BoolFuncSemiring` (`BOOLFUNC_SR`).

```bash
python benchmark/run_benchmark_e.py --sf 0.01 --data-dir ./benchmark/tpch_data/sf001
python benchmark/run_benchmark_e.py --sf 0.05 --data-dir ./benchmark/tpch_data/sf005
python benchmark/run_benchmark_e.py --sf 0.1  --data-dir ./benchmark/tpch_data/sf010
```

| Parameter      | Flag         | Default         |
| -------------- | ------------ | --------------- |
| Scale factor   | `--sf`       | 0.01 (or `all`) |
| Data directory | `--data-dir` | auto-detected   |
| Repetitions    | `--reps`     | 7               |

**Paper reference**: Table 9 — overhead ranges from 1.7× (stable workloads) to 17.7× (`asia_lineitem_supplier_singleton` at SF 0.1).

---

## Step 4 — Interpreting the results

### What should match vs. what may differ

| Metric                    | Expected match                 | Notes                                       |
| ------------------------- | ------------------------------ | ------------------------------------------- |
| **Overhead ratios**       | Within ±10–15% of paper values | Ratios are hardware-independent             |
| **Absolute times**        | Will differ                    | Depend on CPU speed, memory, OS scheduler   |
| **Output row counts**     | Exact match                    | Deterministic computation                   |
| **Clause/literal counts** | Exact match                    | Deterministic formula structure             |
| **Ranking order**         | Should match                   | Which queries/workloads are fastest/slowest |

### Paper table correspondence

| Benchmark | Paper Table        | What it demonstrates                                   |
| --------- | ------------------ | ------------------------------------------------------ |
| **A**     | Table 5            | Per-query provenance overhead (1.4–1.8×)               |
| **B**     | Table 6 / Figure 2 | Overhead stability across scale (converges to ~1.6×)   |
| **C**     | Table 7            | Per-operator overhead breakdown (× dominates)          |
| **D**     | Table 8            | Synthetic worst cases (projection-collapse bottleneck) |
| **E**     | Table 9            | Realistic TPC-H validation across scale factors        |

---

## Troubleshooting

### Import errors

Confirm the virtual environment is activated:

```bash
which python  # should point to venv/bin/python
source venv/bin/activate
```

### TPC-H CSVs not found by Benchmark E

Re-generate the data and confirm the `--data-dir` argument matches:

```bash
python benchmark/generate_tpch_data.py --sf 0.01 --output-dir ./benchmark/tpch_data/sf001
python benchmark/run_benchmark_e.py --sf 0.01 --data-dir ./benchmark/tpch_data/sf001
```

### DuckDB installation fails

DuckDB is required only for data generation. If it fails to install:

```bash
pip install duckdb --no-cache-dir
```

On Apple Silicon Macs, ensure you're using a native ARM Python, not Rosetta.

### Benchmark B chart not generated

Install matplotlib:

```bash
pip install matplotlib
```

The benchmark still runs and prints the table without matplotlib; only the
PNG chart is skipped.
