"""
Entry point: worked example  →  correctness tests  →  benchmarks.

Run with no arguments to execute the built-in demo and correctness suite.
Run with --query to evaluate a relational algebra expression against
tables loaded from CSV files.
Run with --sql to evaluate a SQL SELECT query (translated to RA first).

Usage examples
--------------
  # Built-in demo
  python main.py

  # Evaluate an RA expression against CSV tables
  python main.py --query "δ(π[Name](σ[Dept == 'Eng'](R)))" \\
                 --table R data/employees.csv \\
                 --semiring bool

  # Evaluate a SQL query against CSV tables
  python main.py --sql "SELECT DISTINCT Name FROM R WHERE Dept = 'Eng'" \\
                 --table R data/employees.csv \\
                 --semiring bool
"""

import sys
import argparse

from src.semirings import BOOL_SR, NAT_SR, POLY_SR, Polynomial
from src.relation  import KRelation
from src.operators.deduplication import deduplication
from src.strategies import DedupStrategy
from src.parser import parse
from src.evaluator import Evaluator, UnsupportedOperatorError
from src.io.csv_loader import load_csv
from src.sql_to_ra import sql_to_ra, SQLTranslationError
from benchmarks.bench_deduplication import main as run_benchmarks


_SEMIRINGS = {
    "bool": BOOL_SR,
    "nat": NAT_SR,
    "poly": POLY_SR,
}

_STRATEGIES = {
    "existence": DedupStrategy.EXISTENCE,
    "how_provenance": DedupStrategy.HOW_PROVENANCE,
}


def _run_query(
    query: str,
    table_args: list[tuple[str, str]],
    semiring_name: str,
    strategy_name: str,
    original_sql: str | None = None,
) -> None:
    """Load tables from CSV files, evaluate the query, and print the result."""
    semiring = _SEMIRINGS[semiring_name]
    strategy = _STRATEGIES[strategy_name]

    tables = {}
    for name, filepath in table_args:
        try:
            tables[name] = load_csv(filepath, semiring)
            print(f"  Loaded table '{name}' from {filepath} "
                  f"({tables[name].support_size()} rows)")
        except FileNotFoundError as e:
            print(f"  ERROR: {e}", file=sys.stderr)
            sys.exit(1)
        except ValueError as e:
            print(f"  ERROR loading '{name}': {e}", file=sys.stderr)
            sys.exit(1)

    if original_sql:
        print(f"\n  SQL      : {original_sql}")
        print(f"  RA       : {query}")
    else:
        print(f"\n  Query    : {query}")
    print(f"  Semiring : {semiring_name}")
    print(f"  Strategy : {strategy_name}")
    print()

    try:
        tree = parse(query)
        ev = Evaluator(tables, semiring, strategy)
        result = ev.evaluate(tree)
        print(result.pretty("Result"))
    except UnsupportedOperatorError as e:
        print(f"  ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"  ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"  ERROR: {e}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Provenance-aware relational algebra evaluator.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  # Evaluate an RA expression
  python main.py --query "δ(π[Name](σ[Dept == 'Eng'](R)))" \\
                 --table R data/employees.csv \\
                 --semiring bool --strategy existence

  # Evaluate a SQL query (translated to RA automatically)
  python main.py --sql "SELECT DISTINCT Name FROM R WHERE Dept = 'Eng'" \\
                 --table R data/employees.csv \\
                 --semiring bool
        """,
    )
    parser.add_argument(
        "--query", "-q",
        metavar="EXPR",
        help="Relational algebra expression to evaluate (e.g. \"δ(π[A](R))\").",
    )
    parser.add_argument(
        "--sql",
        metavar="SQL",
        help="SQL SELECT query to translate and evaluate "
             "(e.g. \"SELECT DISTINCT Name FROM R WHERE Dept = 'Eng'\").",
    )
    parser.add_argument(
        "--table", "-t",
        metavar=("NAME", "FILE"),
        nargs=2,
        action="append",
        default=[],
        help="Load a CSV file as a named table. Repeatable.",
    )
    parser.add_argument(
        "--semiring", "-s",
        choices=list(_SEMIRINGS),
        default="bool",
        help="Semiring to use for annotations (default: bool).",
    )
    parser.add_argument(
        "--strategy",
        choices=list(_STRATEGIES),
        default="existence",
        help="Deduplication strategy for δ nodes (default: existence).",
    )

    args = parser.parse_args()

    if args.query and args.sql:
        print("ERROR: --query and --sql are mutually exclusive.", file=sys.stderr)
        sys.exit(1)

    if args.sql:
        # ── SQL mode ───────────────────────────────────────────────────
        print("Provenance-Aware Relational Algebra — SQL Mode")
        print("Python", sys.version.split()[0])
        try:
            ra_expr = sql_to_ra(args.sql)
        except SQLTranslationError as e:
            print(f"  SQL translation error: {e}", file=sys.stderr)
            sys.exit(1)
        _run_query(ra_expr, args.table, args.semiring, args.strategy,
                   original_sql=args.sql)

    elif args.query:
        # ── RA query mode ──────────────────────────────────────────────
        print("Provenance-Aware Relational Algebra — Query Mode")
        print("Python", sys.version.split()[0])
        _run_query(args.query, args.table, args.semiring, args.strategy)
    else:
        # ── Demo mode (original behaviour) ─────────────────────────────
        print("Provenance-Aware Relational Algebra — Deduplication Module")
        print("Python", sys.version.split()[0])
        _run_worked_example()
        failures = _run_correctness_tests()
        run_benchmarks()
        sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
