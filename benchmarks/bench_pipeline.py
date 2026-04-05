"""
Performance benchmarks for the full multi-operator query pipeline.

What is measured
----------------
The end-to-end cost of evaluating TPC-H queries through the
provenance-aware RA evaluator, comparing:

    BOOL - BooleanSemiring + EXISTENCE
    Baseline: no provenance tracked (just TRUE/FALSE).

    BOOLFUNC - BoolFuncSemiring + EXISTENCE
    Provenance: positive Boolean formulas in DNF.
    Each output tuple carries a formula explaining which input tuple
    combinations produce it.

Both elapsed time (time.perf_counter) and peak memory (tracemalloc)
are reported. The overhead column shows BOOLFUNC / BOOL ratio.

Data source
-----------
Pre-generated TPC-H CSV files in `data/tpch/`.

Query input
-----------
Queries are read from `test_sql_script/*.sql` (SQL). The SQL
translator converts them to RA, then the evaluator executes them.
"""

import argparse
import gc
import sys
import time
import tracemalloc
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.semirings import BOOL_SR, BOOLFUNC_SR
from src.semirings.base import Semiring
from src.relation.k_relation import KRelation
from src.strategies import DedupStrategy
from src.parser import parse
from src.evaluator import Evaluator
from src.sql_to_ra import sql_to_ra_with_aliases, SQLTranslationError
from src.io.tpch_loader import load_tpch_csvs

_ROOT = Path(__file__).resolve().parent.parent
_SQL_DIR = _ROOT / "test_sql_script"
_TPCH_CSV_DIR = _ROOT / "data" / "tpch"


# ──────────────────────────────────────────────────────────────────────
# Data loading
# ──────────────────────────────────────────────────────────────────────

def _load_tables(
    csv_dir: Path,
    semiring: Semiring,
    limit: Optional[int] = None,
) -> Dict[str, KRelation]:
    """Load TPC-H tables from pre-generated CSV files."""
    return load_tpch_csvs(csv_dir, semiring, limit=limit)


# ──────────────────────────────────────────────────────────────────────
# SQL query loading
# ──────────────────────────────────────────────────────────────────────

def _load_sql_queries(sql_dir: Path) -> Dict[str, str]:
    """
    Load all .sql files from the given directory.
    Returns a dict of {label: sql_text}.
    """
    queries: Dict[str, str] = {}
    if not sql_dir.is_dir():
        return queries
    for sql_file in sorted(sql_dir.glob("*.sql")):
        label = f"Q{sql_file.stem}"
        sql_text = sql_file.read_text(encoding="utf-8")
        # Strip SQL comments (lines starting with --)
        lines = [l for l in sql_text.splitlines() if not l.strip().startswith("--")]
        queries[label] = "\n".join(lines).strip()
    return queries


def _translate_sql(sql: str) -> Tuple[str, Dict[str, str]]:
    """Translate a SQL query to RA expression + alias map."""
    return sql_to_ra_with_aliases(sql)


# ──────────────────────────────────────────────────────────────────────
# Measurement helper
# ──────────────────────────────────────────────────────────────────────

def _measure(fn, *args) -> Tuple[float, int]:
    """
    Execute fn(*args) once.
    Returns (elapsed_seconds, peak_bytes_new_allocations).
    """
    gc.collect()
    tracemalloc.start()
    t0 = time.perf_counter()
    result = fn(*args)
    elapsed = time.perf_counter() - t0
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return elapsed, peak


def _run_query_ra(tables: Dict[str, KRelation], semiring: Semiring,
                  ra_expr: str, alias_map: Dict[str, str]) -> KRelation:
    """Parse and evaluate a pre-built RA expression."""
    ast = parse(ra_expr)
    ev = Evaluator(tables, semiring, DedupStrategy.EXISTENCE, alias_map)
    return ev.evaluate(ast)


# ──────────────────────────────────────────────────────────────────────
# Benchmark A: per-query comparison (BOOL vs BOOLFUNC)
# ──────────────────────────────────────────────────────────────────────

def bench_sql_queries(
    queries: Dict[str, str],
    csv_dir: Path,
    limit: Optional[int],
) -> None:
    """
    For each SQL query, compare Boolean (no provenance) vs BoolFunc (provenance)
    semirings.
    """
    print(f"\n  Data: TPC-H CSVs from {csv_dir} (limit={limit})")
    print("  " + "─" * 100)

    header = (
        f"  {'Query':<12}"
        f"{'SQL→RA':>8}  "
        f"{'BOOL (s)':>10}  "
        f"{'BOOLFUNC (s)':>12}  "
        f"{'Overhead':>10}  "
        f"{'BOOL KB':>10}  "
        f"{'BF KB':>10}  "
        f"{'Rows':>6}"
    )
    print(header)
    print("  " + "─" * 100)

    for label, sql in queries.items():
        try:
            t0 = time.perf_counter()
            ra_expr, alias_map = _translate_sql(sql)
            t_translate = time.perf_counter() - t0
        except SQLTranslationError as e:
            print(f"  {label:<12}  SKIP (translation error: {e})")
            continue

        bool_tables = _load_tables(csv_dir, BOOL_SR, limit=limit)
        bf_tables = _load_tables(csv_dir, BOOLFUNC_SR, limit=limit)

        try:
            t_bool, mem_bool = _measure(
                _run_query_ra, bool_tables, BOOL_SR, ra_expr, alias_map
            )
            t_bf, mem_bf = _measure(
                _run_query_ra, bf_tables, BOOLFUNC_SR, ra_expr, alias_map
            )
            result = _run_query_ra(bool_tables, BOOL_SR, ra_expr, alias_map)
            n_rows = result.support_size()

            overhead = f"{t_bf / t_bool:.1f}x" if t_bool > 1e-9 else "n/a"
            print(
                f"  {label:<12}"
                f"{t_translate:>8.4f}  "
                f"{t_bool:>10.4f}  "
                f"{t_bf:>12.4f}  "
                f"{overhead:>10}  "
                f"{mem_bool / 1024:>10.1f}  "
                f"{mem_bf / 1024:>10.1f}  "
                f"{n_rows:>6}"
            )
        except Exception as e:
            print(f"  {label:<12}  ERROR: {e}")


# ──────────────────────────────────────────────────────────────────────
# Benchmark B: scaling behaviour (single query, increasing row limits)
# ──────────────────────────────────────────────────────────────────────

def bench_scaling(
    label: str,
    sql: str,
    limits: List[int],
    csv_dir: Path,
) -> None:
    """
    Run a single SQL query at increasing row-per-table limits to show
    how provenance overhead scales with data size.
    """
    try:
        ra_expr, alias_map = _translate_sql(sql)
    except SQLTranslationError as e:
        print(f"  SKIP {label}: {e}")
        return

    print(f"\n  Query: {label}")
    print("  " + "─" * 80)
    header = (
        f"  {'Limit':>6}  "
        f"{'BOOL (s)':>10}  "
        f"{'BOOLFUNC (s)':>12}  "
        f"{'Overhead':>10}  "
        f"{'BF mem KB':>10}  "
        f"{'Result rows':>12}"
    )
    print(header)
    print("  " + "─" * 80)

    for lim in limits:
        bool_tables = _load_tables(csv_dir, BOOL_SR, limit=lim)
        bf_tables = _load_tables(csv_dir, BOOLFUNC_SR, limit=lim)

        try:
            t_bool, _ = _measure(
                _run_query_ra, bool_tables, BOOL_SR, ra_expr, alias_map
            )
            t_bf, mem_bf = _measure(
                _run_query_ra, bf_tables, BOOLFUNC_SR, ra_expr, alias_map
            )
            result = _run_query_ra(bool_tables, BOOL_SR, ra_expr, alias_map)
            n_rows = result.support_size()
            overhead = f"{t_bf / t_bool:.1f}x" if t_bool > 1e-9 else "n/a"

            print(
                f"  {lim:>6}  "
                f"{t_bool:>10.4f}  "
                f"{t_bf:>12.4f}  "
                f"{overhead:>10}  "
                f"{mem_bf / 1024:>10.1f}  "
                f"{n_rows:>12}"
            )
        except Exception as e:
            print(f"  {lim:>6}  ERROR: {e}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark TPC-H queries across semirings.",
    )
    parser.add_argument(
        "--csv-dir", type=Path, default=_TPCH_CSV_DIR,
        help=f"Directory with TPC-H CSV files (default: {_TPCH_CSV_DIR}). "
             "Generate with: python -m scripts.generate_tpch_data",
    )
    parser.add_argument(
        "--sql-dir", type=Path, default=_SQL_DIR,
        help=f"Directory with .sql query files (default: {_SQL_DIR})",
    )
    parser.add_argument(
        "--limit", type=int, default=10,
        help="Max rows per table (default: 10). Controls cross-product size: "
             "10 rows/table → 10^N for N-table joins.",
    )
    parser.add_argument(
        "--queries", type=str, nargs="*", default=None,
        help="Run only these queries (e.g. Q3 Q11). Default: all.",
    )
    parser.add_argument(
        "--scaling-limits", type=int, nargs="*", default=[5, 10, 20, 30],
        help="Row limits for Benchmark B scaling (default: 5 10 20 30).",
    )
    args = parser.parse_args()

    print("\n" + "═" * 70)
    print("PERFORMANCE BENCHMARKS — full query pipeline")
    print("═" * 70)
    print("""
Semiring comparison
───────────────────
BOOL       BooleanSemiring + EXISTENCE   (no provenance — baseline)
BOOLFUNC   BoolFuncSemiring + EXISTENCE  (provenance: positive Boolean
           formulas in DNF tracking which input tuples produce each output)

Input: SQL queries from test_sql_script/*.sql
Pipeline: SQL → RA translation → parse → evaluate
""")

    # Verify data exists
    if not args.csv_dir.is_dir():
        print(f"  ERROR: TPC-H CSV directory not found: {args.csv_dir}")
        print("  Generate it with: python -m scripts.generate_tpch_data")
        sys.exit(1)

    # Load SQL queries
    all_queries = _load_sql_queries(args.sql_dir)
    if not all_queries:
        print(f"  No .sql files found in {args.sql_dir}")
        sys.exit(1)

    # Filter if --queries specified
    if args.queries:
        filtered = {k: v for k, v in all_queries.items() if k in args.queries}
        if not filtered:
            print(f"  No matching queries. Available: {', '.join(all_queries)}")
            sys.exit(1)
        queries = filtered
    else:
        queries = all_queries

    print(f"  Data source: TPC-H CSVs from {args.csv_dir}")
    print(f"  Row limit per table: {args.limit}")
    print(f"  Queries: {', '.join(queries)}")

    # ── Benchmark A: all queries at fixed limit ──
    print("\n  Benchmark A — per-query comparison (BOOL vs BOOLFUNC)")
    bench_sql_queries(queries, args.csv_dir, args.limit)

    # ── Benchmark B: scaling for the first query ──
    scaling_label = next(iter(queries))
    scaling_sql = queries[scaling_label]
    print("\n\n  Benchmark B — scaling behaviour (increasing rows/table)")
    bench_scaling(scaling_label, scaling_sql, args.scaling_limits, args.csv_dir)

    print("""
Interpretation
──────────────
Benchmark A (per-query comparison)
BooleanSemiring carries trivial True/False annotations. BoolFuncSemiring
builds positive Boolean formulas in DNF, which grow with the number of
contributing input tuples. The overhead ratio measures the cost of
provenance tracking in a realistic multi-operator pipeline.

Benchmark B (scaling)
Shows how provenance overhead changes as data size grows.  Row limits
control the number of rows loaded per table from the same TPC-H dataset.
The cross product operator is O(n·m), so multi-table queries become
expensive quickly.

Practical takeaway
BooleanSemiring is suitable when only tuple existence matters.
BoolFuncSemiring is needed for probabilistic databases (Shapley values,
reliability queries) where the provenance formula feeds downstream
computation.
    """)


if __name__ == "__main__":
    main()
