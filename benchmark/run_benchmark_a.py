"""
Benchmark A — Per-query comparison: BOOL vs BOOLFUNC on 8 adapted TPC-H queries.

Reproduces Table 5 of the paper: per-query wall-clock time and overhead ratio
at a configurable row limit per table (default: 10).

Usage:
    python run_benchmark_a.py
    python run_benchmark_a.py --row-limit 5
    python run_benchmark_a.py --data-dir ./tpch_data/sf001
"""

from __future__ import annotations

import argparse
import gc
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SQL_DIR = ROOT / "test_sql_script"


def _load_sql(filename: str) -> str:
    """Load SQL from file, stripping comment lines."""
    lines = (SQL_DIR / filename).read_text(encoding="utf-8").splitlines()
    return "\n".join(l for l in lines if not l.strip().startswith("--")).strip()


from src.semirings.boolean import BooleanSemiring, BOOL_SR
from src.semirings.boolean_function import BoolFuncSemiring, BoolFunc, BOOLFUNC_SR
from src.strategies import DedupStrategy
from src.evaluator import Evaluator
from src.sql_to_ra import sql_to_ra_with_aliases
from src.parser.parser import parse
from src.io.tpch_loader import load_tpch_csvs

# ── Adapted TPC-H queries (loaded from test_sql_script/) ─────────────

QUERIES = {
    f"Q{stem}": _load_sql(f"{stem}.sql")
    for stem in ["3", "5", "7", "10", "11", "16", "18", "19"]
}

# Table count per query (for display)
TABLE_COUNTS = {
    "Q3": 3, "Q5": 6, "Q7": 6, "Q10": 4,
    "Q11": 3, "Q16": 3, "Q18": 3, "Q19": 2,
}

# Display order matching Table 5 (sorted by time ascending)
DISPLAY_ORDER = ["Q19", "Q11", "Q16", "Q18", "Q3", "Q10", "Q5", "Q7"]


def load_tables(data_dir: Path, semiring, limit: int):
    """Load TPC-H tables with a row limit."""
    return load_tpch_csvs(data_dir, semiring, limit=limit)


def prepare_query(sql: str):
    """Pre-translate and parse a SQL query (excluded from timing)."""
    ra_expr, alias_map = sql_to_ra_with_aliases(sql.strip())
    tree = parse(ra_expr)
    return tree, alias_map


def timed_evaluate(evaluator: Evaluator, tree, n_reps: int = 7) -> float:
    """Run evaluate n_reps+1 times (1 warmup), return median of timed runs in seconds."""
    # Warm-up
    evaluator.evaluate(tree)

    times = []
    for _ in range(n_reps):
        gc.disable()
        t0 = time.perf_counter()
        evaluator.evaluate(tree)
        t1 = time.perf_counter()
        gc.enable()
        times.append(t1 - t0)

    return statistics.median(times)


def main():
    parser = argparse.ArgumentParser(description="Benchmark A: Per-query BOOL vs BOOLFUNC comparison.")
    parser.add_argument("--row-limit", type=int, default=10, help="Row limit per table (default: 10).")
    parser.add_argument("--data-dir", type=str, default=None,
                        help="Directory containing TPC-H CSVs (default: data/tpch/).")
    parser.add_argument("--reps", type=int, default=7, help="Number of timed repetitions (default: 7).")
    args = parser.parse_args()

    data_dir = Path(args.data_dir) if args.data_dir else ROOT / "data" / "tpch"
    if not data_dir.is_dir():
        # Fallback: try tpch_data/sf001
        alt = ROOT / "tpch_data" / "sf001"
        if alt.is_dir():
            data_dir = alt
        else:
            print(f"ERROR: TPC-H data directory not found at {data_dir}")
            print("Run: python generate_tpch_data.py --sf 0.01")
            sys.exit(1)

    print(f"Benchmark A: Per-query comparison (row limit = {args.row_limit})")
    print(f"Data directory: {data_dir}")
    print(f"Repetitions: {args.reps} timed runs after 1 warm-up, GC disabled\n")

    # Pre-translate and parse all queries (excluded from timing)
    parsed_queries = {}
    for qname, sql in QUERIES.items():
        try:
            parsed_queries[qname] = prepare_query(sql)
        except Exception as e:
            print(f"  WARNING: Failed to parse {qname}: {e}")

    results = []

    for qname in DISPLAY_ORDER:
        if qname not in parsed_queries:
            continue

        tree, alias_map = parsed_queries[qname]
        ntbl = TABLE_COUNTS[qname]

        # Load tables for BOOL
        tables_bool = load_tables(data_dir, BOOL_SR, args.row_limit)
        eval_bool = Evaluator(tables_bool, BOOL_SR, DedupStrategy.EXISTENCE, alias_map=alias_map)
        t_bool = timed_evaluate(eval_bool, tree, args.reps)

        # Load tables for BOOLFUNC
        tables_bf = load_tables(data_dir, BOOLFUNC_SR, args.row_limit)
        eval_bf = Evaluator(tables_bf, BOOLFUNC_SR, DedupStrategy.EXISTENCE, alias_map=alias_map)
        t_bf = timed_evaluate(eval_bf, tree, args.reps)

        ratio = t_bf / t_bool if t_bool > 0 else float("inf")
        results.append((qname, ntbl, t_bool * 1000, t_bf * 1000, ratio))

    # Print table
    print(f"{'Query':<8} {'#Tbl':<6} {'BOOL (ms)':>12} {'BF (ms)':>12} {'Time x':>10}")
    print("-" * 52)
    for qname, ntbl, t_b, t_bf, ratio in results:
        print(f"{qname:<8} {ntbl:<6} {t_b:>12.3f} {t_bf:>12.3f} {ratio:>9.2f}x")

    print("\nBenchmark A complete.")


if __name__ == "__main__":
    main()
