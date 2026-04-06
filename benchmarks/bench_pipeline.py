"""
Benchmark harness entry point for provenance-aware relational algebra evaluation.

The harness has three benchmark layers:

1. Microbenchmarks on synthetic K-relations (--mode micro).
    See benchmarks/_micro.py.

2. Macrobenchmarks on real TPC-H CSV data (--mode macro).
    See benchmarks/_macro.py.

3. Opt-in SQL benchmarks on the simplified TPC-H queries (--mode sql).
    See benchmarks/_sql.py.

Usage (run from the project root):

    python -m benchmarks.bench_pipeline [options]
"""

from __future__ import annotations

import argparse
from pathlib import Path

from src.strategies import DedupStrategy

from ._common import _DEFAULT_SQL_DIR, _DEFAULT_TPCH_CACHE_DIR, _DEFAULT_TPCH_DIR
from ._macro import (
    _benchmark_macro_workloads,
    _print_macro_benchmark_rows,
    _select_macro_workloads,
)
from ._micro import _benchmark_micro_workloads, _print_micro_benchmark_rows
from ._operator import _benchmark_operator_workloads, _print_operator_benchmark_rows
from ._sql import (
    _benchmark_sql_workloads,
    _load_sql_workloads,
    _print_sql_benchmark_rows,
    _validate_sql_cli_workloads,
)
from ._tpch import _resolve_tpch_sources


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Micro, macro, and opt-in SQL benchmarks for provenance-aware relational algebra.",
    )
    parser.add_argument(
        "--mode",
        choices=["all", "operator", "micro", "macro", "sql", "full"],
        default="all",
        help=(
            "Which benchmark layer(s) to run. "
            "'operator' runs Benchmark C (per-operator isolation); "
            "'micro' runs Benchmark D (synthetic workloads); "
            "'macro' runs Benchmark E (TPC-H pipelines); "
            "'sql' runs Benchmarks A & B (translated SQL queries); "
            "'all' runs C+D+E (default); "
            "'full' runs every layer including SQL (default: all)."
        ),
    )
    parser.add_argument(
        "--operator-size",
        type=int,
        default=10,
        help="Number of rows per relation in per-operator benchmarks (Benchmark C). Default 10 matches the paper's Table 3 (10 rows/table).",
    )
    parser.add_argument(
        "--size",
        type=int,
        default=256,
        help="Row count for linear micro workloads such as selection and projection collisions (default: 256).",
    )
    parser.add_argument(
        "--cross-size",
        type=int,
        default=48,
        help="Rows per side for dense synthetic cross-product workloads (default: 48).",
    )
    parser.add_argument(
        "--formula-width",
        type=int,
        default=48,
        help="Clause width for one-row symbolic micro stress cases (default: 48).",
    )
    parser.add_argument(
        "--repeat",
        type=int,
        default=7,
        help="Timed repetitions per workload (default: 7).",
    )
    parser.add_argument(
        "--warmup",
        type=int,
        default=1,
        help="Warm-up executions per workload before timing (default: 1).",
    )
    parser.add_argument(
        "--tpch-csv-dir",
        type=Path,
        default=_DEFAULT_TPCH_DIR,
        help=f"Directory containing committed TPC-H CSVs (default: {_DEFAULT_TPCH_DIR}).",
    )
    parser.add_argument(
        "--tpch-cache-dir",
        type=Path,
        default=_DEFAULT_TPCH_CACHE_DIR,
        help=f"Cache directory for generated higher-SF TPC-H CSVs (default: {_DEFAULT_TPCH_CACHE_DIR}).",
    )
    parser.add_argument(
        "--tpch-sf",
        type=float,
        nargs="*",
        default=None,
        help="Optional TPC-H scale factors to generate and benchmark as CSV snapshots (example: 0.01 0.05 0.1).",
    )
    parser.add_argument(
        "--tpch-limit",
        type=int,
        default=None,
        help="Optional row cap per loaded table, useful for quick smoke runs or conservative higher-SF sweeps.",
    )
    parser.add_argument(
        "--macro-suite",
        choices=["standard", "stress", "both"],
        default="standard",
        help="Which curated TPC-H workload set to run (default: standard).",
    )
    parser.add_argument(
        "--macro-workloads",
        nargs="*",
        default=None,
        help="Run only the named macro workloads from the selected suite.",
    )
    parser.add_argument(
        "--macro-strategy",
        choices=["existence", "how_provenance"],
        default="how_provenance",
        help="Deduplication strategy for macrobench workloads (default: how_provenance).",
    )
    parser.add_argument(
        "--sql-dir",
        type=Path,
        default=_DEFAULT_SQL_DIR,
        help=f"Directory containing simplified SQL workloads to translate and benchmark (default: {_DEFAULT_SQL_DIR}).",
    )
    parser.add_argument(
        "--sql-workloads",
        nargs="+",
        default=None,
        help="Run exactly one named SQL workload from the SQL directory (for example: q3 or 3).",
    )
    parser.add_argument(
        "--sql-strategy",
        choices=["existence", "how_provenance"],
        default="how_provenance",
        help="Deduplication strategy for SQL workloads (default: how_provenance).",
    )
    parser.add_argument(
        "--sql-max-cross-product",
        type=int,
        default=1_000_000,
        help="When --tpch-limit is omitted in SQL mode, cap each workload so its naive table-count cross-product stays within roughly this many combinations (default: 1000000).",
    )
    args = parser.parse_args()

    if args.mode in {"all", "operator", "full"}:
        operator_rows = _benchmark_operator_workloads(
            operator_size=args.operator_size,
            repeat=args.repeat,
            warmup=args.warmup,
        )
        _print_operator_benchmark_rows(operator_rows, repeat=args.repeat, warmup=args.warmup)

    if args.mode in {"all", "micro", "full"}:
        micro_rows = _benchmark_micro_workloads(
            size=args.size,
            cross_size=args.cross_size,
            formula_width=args.formula_width,
            repeat=args.repeat,
            warmup=args.warmup,
        )
        _print_micro_benchmark_rows(micro_rows)

    if args.mode in {"all", "macro", "full"}:
        strategy = (
            DedupStrategy.EXISTENCE
            if args.macro_strategy == "existence"
            else DedupStrategy.HOW_PROVENANCE
        )
        workloads = _select_macro_workloads(
            suite=args.macro_suite,
            selected_names=args.macro_workloads,
        )
        sources = _resolve_tpch_sources(
            csv_dir=args.tpch_csv_dir,
            cache_dir=args.tpch_cache_dir,
            scale_factors=args.tpch_sf,
            limit=args.tpch_limit,
        )
        macro_rows = _benchmark_macro_workloads(
            workloads=workloads,
            sources=sources,
            strategy=strategy,
            repeat=args.repeat,
            warmup=args.warmup,
            limit=args.tpch_limit,
        )
        _print_macro_benchmark_rows(macro_rows, strategy=strategy)

    if args.mode in {"sql", "full"}:
        try:
            selected_sql_workloads = _validate_sql_cli_workloads(args.sql_workloads)
        except ValueError as exc:
            parser.error(str(exc))
        strategy = (
            DedupStrategy.EXISTENCE
            if args.sql_strategy == "existence"
            else DedupStrategy.HOW_PROVENANCE
        )
        workloads = _load_sql_workloads(
            sql_dir=args.sql_dir,
            selected_names=selected_sql_workloads,
        )
        sources = _resolve_tpch_sources(
            csv_dir=args.tpch_csv_dir,
            cache_dir=args.tpch_cache_dir,
            scale_factors=args.tpch_sf,
            limit=args.tpch_limit,
        )
        sql_rows = _benchmark_sql_workloads(
            workloads=workloads,
            sources=sources,
            strategy=strategy,
            repeat=args.repeat,
            warmup=args.warmup,
            limit=args.tpch_limit,
            max_cross_product=args.sql_max_cross_product,
        )
        _print_sql_benchmark_rows(sql_rows, strategy=strategy)


if __name__ == "__main__":
    main()