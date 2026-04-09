#!/usr/bin/env python3
"""
generate_tpch_data.py — Synthetic TPC-H data generator.

Generates TPC-H-like CSV files for 8 tables at a given scale factor,
using DuckDB's built-in TPC-H data generator for specification-conformant data.

Usage:
    python generate_tpch_data.py --sf 0.01
    python generate_tpch_data.py --sf 0.05 --output-dir ./tpch_data/sf005
    python generate_tpch_data.py --sf 0.1  --output-dir ./tpch_data/sf010
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.io.tpch_loader import generate_tpch_csvs, SCHEMAS


# Per-table row limits at SF 0.01, derived from the TPC-H specification ratios:
#
#   lineitem  : 600   — ~4 line items per order (150 orders × ~4)
#   orders    : 150   — base workload size; controls cross-product volume
#   customer  : 1500  — FULL SF 0.01 population (10× orders); must not be
#                       truncated — the orders table references o_custkey
#                       values up to ~1 500, so a smaller limit causes FK
#                       mismatches that silently drop most joined rows
#   supplier  : 100   — ~1 supplier per nation-region combination (20 nations
#                       × 5 regions / 5 regions × 100 = proportional)
#   nation    : 25    — fixed by TPC-H spec (exactly 25 nations)
#   region    : 5     — fixed by TPC-H spec (exactly 5 regions)
#   part      : 200   — ~200 distinct parts at SF 0.01 per spec
#   partsupp  : 800   — 4 suppliers per part (200 parts × 4)
#
# All non-fixed tables scale linearly with SF (see _compute_limits).
# nation and region are always loaded in full regardless of SF.
_BASE_LIMITS = {
    "lineitem": 600,
    "orders": 150,
    "customer": 1500,
    "supplier": 100,
    "nation": 25,
    "region": 5,
    "part": 200,
    "partsupp": 800,
}


def _compute_limits(sf: float):
    """Scale row limits proportionally to scale factor (relative to SF 0.01)."""
    factor = sf / 0.01
    limits = {}
    for table, base in _BASE_LIMITS.items():
        # nation and region are fixed
        if table in ("nation", "region"):
            limits[table] = base
        else:
            limits[table] = int(base * factor)
    return limits


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate TPC-H benchmark CSV data via DuckDB.",
    )
    parser.add_argument(
        "--sf", type=float, default=0.01,
        help="TPC-H scale factor: 0.01, 0.05, or 0.1 (default: 0.01).",
    )
    parser.add_argument(
        "--output-dir", type=str, default=None,
        help="Output directory (default: ./tpch_data/sf{sf}/). "
             "Each table is written as <table>.csv.",
    )
    args = parser.parse_args()

    sf = args.sf
    if args.output_dir is None:
        sf_tag = str(sf).replace(".", "")
        output_dir = ROOT / "tpch_data" / f"sf{sf_tag}"
    else:
        output_dir = Path(args.output_dir)

    print(f"Generating TPC-H data at SF={sf}")
    print(f"Output directory: {output_dir}\n")

    # Apply per-table row limits to keep data tractable
    limits = _compute_limits(sf)
    print("Per-table row limits:")
    for t, lim in limits.items():
        print(f"  {t}: {lim}")
    print()

    # Generate each table individually with its own limit
    import csv as csv_mod
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        import duckdb
    except ImportError:
        print("ERROR: DuckDB is required. Install it with: pip install duckdb")
        sys.exit(1)

    con = duckdb.connect()
    con.install_extension("tpch")
    con.load_extension("tpch")
    con.execute(f"CALL dbgen(sf={sf})")

    from datetime import date
    from decimal import Decimal

    written = []
    for table_name, col_defs in SCHEMAS.items():
        schema = [name for name, _ in col_defs]
        type_hints = [hint for _, hint in col_defs]
        hint_map = dict(col_defs)

        table_limit = limits.get(table_name)
        sql_query = f"SELECT {', '.join(schema)} FROM {table_name}"
        if table_limit is not None:
            sql_query += f" LIMIT {table_limit}"

        raw_rows = con.execute(sql_query).fetchall()

        csv_path = output_dir / f"{table_name}.csv"
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv_mod.writer(f)
            writer.writerow(type_hints)
            writer.writerow(schema)
            for raw_row in raw_rows:
                vals = []
                for col_name, raw_val in zip(schema, raw_row):
                    hint = hint_map[col_name]
                    if raw_val is None:
                        vals.append("")
                    elif isinstance(raw_val, date):
                        vals.append(raw_val.isoformat())
                    elif isinstance(raw_val, Decimal):
                        vals.append(str(int(raw_val)) if hint == "INT" else str(raw_val))
                    elif hint == "INT" and not isinstance(raw_val, int):
                        vals.append(str(int(raw_val)))
                    else:
                        vals.append(str(raw_val))
                writer.writerow(vals)

        written.append(table_name)

    # Print summary
    print(f"\n{'Table':<12} {'Columns':<8} {'File'}")
    print("-" * 50)

    import csv
    for table_name in written:
        csv_path = output_dir / f"{table_name}.csv"
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader)  # type hints
            next(reader)  # header
            row_count = sum(1 for _ in reader)
        ncols = len(SCHEMAS[table_name])
        print(f"  {table_name:<12} {ncols:<8} {row_count} rows")

    print(f"\nDone. {len(written)} tables written to {output_dir}/")


if __name__ == "__main__":
    main()
