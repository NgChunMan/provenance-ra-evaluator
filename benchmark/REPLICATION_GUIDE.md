# Replication Guide

## Provenance-Aware Relational Algebra Evaluator — Benchmark Reproduction

This guide walks through reproducing all benchmark results from the paper
_"Provenance-Aware Relational Algebra Evaluator over Semiring-Annotated K-Relations"_.

---

## Prerequisites

| Requirement        | Details                                                                                       |
| ------------------ | --------------------------------------------------------------------------------------------- |
| **Python**         | 3.12 or higher (`python3 --version`)                                                          |
| **OS**             | Tested on macOS (Apple M1) with CPython 3.12; Linux should work; Windows users should use WSL |
| **Disk space**     | ~500 MB for TPC-H data at all three scale factors                                             |
| **Project folder** | Already cloned/open locally                                                                   |

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

### Benchmark A — Per-query comparison

```bash
python benchmark/run_benchmark_a.py --data-dir ./benchmark/tpch_data/sf001
```

Corresponds to **Table 5** in the paper. Runs 8 adapted TPC-H queries (Q3, Q5, Q7,
Q10, Q11, Q16, Q18, Q19) under Boolean (baseline) and Boolean Function (provenance)
semirings, both with Existence deduplication. Reports median wall-clock time and
overhead ratio.

**Key finding**: Provenance overhead is consistent at 1.4–1.8× for typical queries.

### Benchmark B — Scaling behaviour

```bash
python benchmark/run_benchmark_b.py --data-dir ./benchmark/tpch_data/sf001
```

Corresponds to **Table 6 and Figure 2** in the paper. Runs Q3 at row limits
5, 10, 15, 20, 25, 30. Also generates `benchmark_b_scaling.png` if matplotlib
is installed.

**Key finding**: Both configurations scale super-linearly (O(n³) cross product),
but the overhead ratio stabilises at 1.4–1.6x.

### Benchmark C — Per-operator microbenchmarks

```bash
python benchmark/run_benchmark_c.py
```

Corresponds to **Table 7** in the paper. Isolates provenance overhead for each
operator individually (σ, π, ×, ⊎, δ∃, δhow). Baseline: `BOOL_SR`
(Boolean semiring); provenance: `BOOLFUNC_SR`.

**Key finding**: Cross product is the dominant overhead source (6.0×); selection
is virtually free (1.1×).

### Benchmark D — Synthetic stress tests

```bash
python benchmark/run_benchmark_d.py
```

Corresponds to **Table 8** in the paper. Runs 8 synthetic workloads targeting
specific bottlenecks: formula accumulation, formula multiplication, tuple
materialisation, and deduplication downstream cost. Baseline: `NAT_SR`
(counting semiring); provenance: `BOOLFUNC_SR`.

**Key finding**: The projection-after-cross-product pattern causes catastrophic
overhead (up to ~1.3×10⁶× on artificial worst cases). The `symbolic_mul_choke_point`
workload may take up to 60 seconds — this is expected behaviour.

### Benchmark E — TPC-H macrobenchmarks (~3 minutes at SF 0.05, ~12 minutes at SF 0.1)

```bash
python benchmark/run_benchmark_e.py --sf 0.01 --data-dir ./benchmark/tpch_data/sf001
python benchmark/run_benchmark_e.py --sf 0.05 --data-dir ./benchmark/tpch_data/sf005
python benchmark/run_benchmark_e.py --sf 0.1  --data-dir ./benchmark/tpch_data/sf010
```

Corresponds to **Table 9** in the paper. Runs 5 curated operator pipelines
across scale factors, using How-Provenance deduplication. Baseline: `NAT_SR`
(counting semiring); provenance: `BOOLFUNC_SR`.

**Key finding**: Workloads with high output-tuple concentration exhibit
super-linear provenance growth; the `asia_lineitem_supplier_singleton`
pipeline reaches 17.7× overhead at SF 0.1.

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
