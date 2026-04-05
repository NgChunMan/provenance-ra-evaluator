"""
Generate TPC-H benchmark data as CSV files under data/tpch/.

The generated CSVs are committed to the repository so that benchmarks
are reproducible without requiring DuckDB at runtime.

Usage
-----
    python -m scripts.generate_tpch_data  # default SF 0.01
    python -m scripts.generate_tpch_data --sf 0.01
    python -m scripts.generate_tpch_data --sf 0.001 --limit 50

Requires: pip install duckdb
"""

from __future__ import annotations

import argparse
from pathlib import Path

from src.io.tpch_loader import generate_tpch_csvs


_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_OUTPUT = _ROOT / "data" / "tpch"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate TPC-H CSV data via DuckDB for reproducible benchmarks.",
    )
    parser.add_argument(
        "--sf", type=float, default=0.01,
        help="TPC-H scale factor (default: 0.01 ≈ 600 lineitem rows).",
    )
    parser.add_argument(
        "--output", type=Path, default=_DEFAULT_OUTPUT,
        help=f"Output directory (default: {_DEFAULT_OUTPUT}).",
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Cap each table at this many rows.",
    )
    args = parser.parse_args()

    print(f"Generating TPC-H data (SF={args.sf}) → {args.output}/")
    if args.limit:
        print(f"  Row limit per table: {args.limit}")

    written = generate_tpch_csvs(args.sf, args.output, limit=args.limit)

    print(f"  Written {len(written)} tables: {', '.join(written)}")
    print("Done. Commit the CSV files to version control for reproducibility.")


if __name__ == "__main__":
    main()
