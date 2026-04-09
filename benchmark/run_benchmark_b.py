"""
Benchmark B — Scaling behaviour: Q3 at increasing row limits.

Reproduces Table 6 and Figure 2 of the paper: execution time for Q3
(customer-orders-lineitem join) at row limits 5, 10, 15, 20, 25, 30.

Usage:
    python run_benchmark_b.py
    python run_benchmark_b.py --data-dir ./tpch_data/sf001
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


from src.semirings.boolean import BOOL_SR
from src.semirings.boolean_function import BOOLFUNC_SR
from src.strategies import DedupStrategy
from src.evaluator import Evaluator
from src.sql_to_ra import sql_to_ra_with_aliases
from src.parser.parser import parse
from src.io.tpch_loader import load_tpch_csvs

Q3_SQL = _load_sql("3.sql")

ROW_LIMITS = [5, 10, 15, 20, 25, 30]


def timed_evaluate(evaluator, tree, n_reps=7):
    evaluator.evaluate(tree)  # warm-up
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
    parser = argparse.ArgumentParser(description="Benchmark B: Scaling behaviour for Q3.")
    parser.add_argument("--data-dir", type=str, default=None,
                        help="Directory containing TPC-H CSVs.")
    parser.add_argument("--reps", type=int, default=7, help="Timed repetitions (default: 7).")
    args = parser.parse_args()

    data_dir = Path(args.data_dir) if args.data_dir else ROOT / "data" / "tpch"
    if not data_dir.is_dir():
        alt = ROOT / "tpch_data" / "sf001"
        if alt.is_dir():
            data_dir = alt
        else:
            print(f"ERROR: TPC-H data directory not found at {data_dir}")
            sys.exit(1)

    # Pre-parse Q3
    ra_expr, alias_map = sql_to_ra_with_aliases(Q3_SQL.strip())
    tree = parse(ra_expr)

    print(f"Benchmark B: Scaling behaviour for Q3")
    print(f"Data directory: {data_dir}")
    print(f"Repetitions: {args.reps} timed runs after 1 warm-up, GC disabled\n")

    results = []

    for limit in ROW_LIMITS:
        tables_bool = load_tpch_csvs(data_dir, BOOL_SR, limit=limit)
        eval_bool = Evaluator(tables_bool, BOOL_SR, DedupStrategy.EXISTENCE, alias_map=alias_map)
        t_bool = timed_evaluate(eval_bool, tree, args.reps)

        tables_bf = load_tpch_csvs(data_dir, BOOLFUNC_SR, limit=limit)
        eval_bf = Evaluator(tables_bf, BOOLFUNC_SR, DedupStrategy.EXISTENCE, alias_map=alias_map)
        t_bf = timed_evaluate(eval_bf, tree, args.reps)

        ratio = t_bf / t_bool if t_bool > 0 else float("inf")
        results.append((limit, t_bool * 1000, t_bf * 1000, ratio))

    # Print table
    print(f"{'Rows/Tbl':>10} {'BOOL (ms)':>12} {'BF (ms)':>12} {'Time x':>10}")
    print("-" * 48)
    for limit, t_b, t_bf, ratio in results:
        print(f"{limit:>10} {t_b:>12.3f} {t_bf:>12.3f} {ratio:>9.2f}x")

    # Generate chart if matplotlib is available
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        limits = [r[0] for r in results]
        bool_times = [r[1] for r in results]
        bf_times = [r[2] for r in results]

        fig, ax = plt.subplots(figsize=(7, 4.5))
        ax.plot(limits, bool_times, "bs-", linewidth=2, markersize=6, label="BOOL (baseline)")
        ax.plot(limits, bf_times, "r^-", linewidth=2, markersize=6, label="BOOLFUNC (provenance)")
        ax.set_xlabel("Rows per table")
        ax.set_ylabel("Time (ms)")
        ax.set_xticks(limits)
        ax.set_ylim(bottom=0)
        ax.legend(loc="upper left")
        ax.grid(True, alpha=0.3)
        ax.set_title("Benchmark B: Scaling of Q3 execution time")

        out_path = ROOT / "benchmark" / "benchmark_b_scaling.png"
        fig.savefig(out_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        print(f"\nChart saved to {out_path}")
    except ImportError:
        print("\nmatplotlib not available — skipping chart generation.")

    print("\nBenchmark B complete.")


if __name__ == "__main__":
    main()
