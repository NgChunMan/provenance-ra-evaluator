"""
TPC-H data loader: generates and loads specification-conformant TPC-H data.

This module provides:
- load_tpch_from_duckdb() — generate TPC-H data in-memory via DuckDB
- generate_tpch_csvs() — generate TPC-H data and write to CSV files
- load_tpch_csvs() — load pre-generated TPC-H CSV files into KRelations

DuckDB bundles a built-in TPC-H generator conforming to the TPC-H specification:

    from src.io.tpch_loader import load_tpch_from_duckdb
    from src.semirings import BOOL_SR

    # SF 0.001 ≈ 60 lineitems, SF 0.01 ≈ 600, SF 0.1 ≈ 6000
    tables = load_tpch_from_duckdb(sf=0.01, semiring=BOOL_SR)

Column schemas and type hints follow the TPC-H specification.
Integer columns are parsed as ``int``; dates as ``datetime.date``;
decimal columns (including ``l_quantity``) as ``Decimal``.
"""

from __future__ import annotations

import csv
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from src.semirings.base import Semiring
from src.relation.k_relation import KRelation

# Recognised type hints for column schemas.
# INT    → int
# STR    → str
# DATE   → datetime.date
# DECIMAL → decimal.Decimal
_VALID_HINTS = frozenset({"INT", "STR", "DATE", "DECIMAL"})


# ── TPC-H table schemas ──────────────────────────────────────────────
# Each entry: (column_name, type_hint)  where type_hint is "INT" or "STR".
# Order must match the column order produced by dbgen.

SCHEMAS: Dict[str, List[Tuple[str, str]]] = {
    "nation": [
        ("n_nationkey", "INT"),
        ("n_name", "STR"),
        ("n_regionkey", "INT"),
        ("n_comment", "STR"),
    ],
    "region": [
        ("r_regionkey", "INT"),
        ("r_name", "STR"),
        ("r_comment", "STR"),
    ],
    "supplier": [
        ("s_suppkey", "INT"),
        ("s_name", "STR"),
        ("s_address", "STR"),
        ("s_nationkey", "INT"),
        ("s_phone", "STR"),
        ("s_acctbal", "DECIMAL"),
        ("s_comment", "STR"),
    ],
    "customer": [
        ("c_custkey", "INT"),
        ("c_name", "STR"),
        ("c_address", "STR"),
        ("c_nationkey", "INT"),
        ("c_phone", "STR"),
        ("c_acctbal", "DECIMAL"),
        ("c_mktsegment", "STR"),
        ("c_comment", "STR"),
    ],
    "orders": [
        ("o_orderkey", "INT"),
        ("o_custkey", "INT"),
        ("o_orderstatus", "STR"),
        ("o_totalprice", "DECIMAL"),
        ("o_orderdate", "DATE"),
        ("o_orderpriority", "STR"),
        ("o_clerk", "STR"),
        ("o_shippriority", "INT"),
        ("o_comment", "STR"),
    ],
    "lineitem": [
        ("l_orderkey", "INT"),
        ("l_partkey", "INT"),
        ("l_suppkey", "INT"),
        ("l_linenumber", "INT"),
        ("l_quantity", "DECIMAL"),
        ("l_extendedprice", "DECIMAL"),
        ("l_discount", "DECIMAL"),
        ("l_tax", "DECIMAL"),
        ("l_returnflag", "STR"),
        ("l_linestatus", "STR"),
        ("l_shipdate", "DATE"),
        ("l_commitdate", "DATE"),
        ("l_receiptdate", "DATE"),
        ("l_shipinstruct", "STR"),
        ("l_shipmode", "STR"),
        ("l_comment", "STR"),
    ],
    "part": [
        ("p_partkey", "INT"),
        ("p_name", "STR"),
        ("p_mfgr", "STR"),
        ("p_brand", "STR"),
        ("p_type", "STR"),
        ("p_size", "INT"),
        ("p_container", "STR"),
        ("p_retailprice", "DECIMAL"),
        ("p_comment", "STR"),
    ],
    "partsupp": [
        ("ps_partkey", "INT"),
        ("ps_suppkey", "INT"),
        ("ps_availqty", "INT"),
        ("ps_supplycost", "DECIMAL"),
        ("ps_comment", "STR"),
    ],
}


# ── DuckDB-based generator (recommended) ─────────────────────────────

def load_tpch_from_duckdb(
    sf: float,
    semiring: Semiring,
    tables: Optional[List[str]] = None,
    limit: Optional[int] = None,
) -> Dict[str, KRelation]:
    """
    Generate TPC-H data at any scale factor using DuckDB and load into KRelations.

    Scale factor guidelines
    -----------------------
    +---------+-----------+-----------+-----------+
    | SF      | lineitem  | orders    | customer  |
    +=========+===========+===========+===========+
    | 0.001   |   ~60     |   ~150    |    ~150   |
    | 0.01    |   ~600    |   1 500   |    1 500  |
    | 0.1     |   ~6 000  |  15 000   |   15 000  |
    | 1       |   6 M     |   1.5 M   |  150 000  |
    +---------+-----------+-----------+-----------+

    Parameters
    ----------
    sf : float
        TPC-H scale factor (e.g. 0.01 for ~600 lineitem rows).
    semiring : Semiring
        The semiring to annotate tuples with.
    tables : list of str, optional
        Load only these tables. If omitted, all 8 tables are loaded.
    limit : int, optional
        Cap each table at this many rows (useful for quick smoke tests).

    Returns
    -------
    Dict[str, KRelation]
        Mapping from table name to loaded KRelation.

    Raises
    ------
    ImportError
        If ``duckdb`` is not installed.
    """
    # DuckDB column-type conversion rules:
    # - BIGINT / INTEGER → int
    # - DECIMAL → Decimal (for DECIMAL-typed), int (for INT-typed)
    # - DATE   → datetime.date
    # - VARCHAR → str

    try:
        import duckdb
    except ImportError:
        raise ImportError("DuckDB not installed; run `pip install duckdb` to use TPC-H data generation")

    con = duckdb.connect()
    con.install_extension("tpch")
    con.load_extension("tpch")
    con.execute(f"CALL dbgen(sf={sf})")

    table_names = list(SCHEMAS.keys()) if tables is None else [t.lower() for t in tables]
    result: Dict[str, KRelation] = {}

    for table_name in table_names:
        if table_name not in SCHEMAS:
            raise ValueError(
                f"Unknown TPC-H table '{table_name}'. "
                f"Known tables: {', '.join(sorted(SCHEMAS))}"
            )
        col_defs = SCHEMAS[table_name]
        schema = [name for name, _ in col_defs]
        type_hints = {name: hint for name, hint in col_defs}

        sql = f"SELECT {', '.join(schema)} FROM {table_name}"
        if limit is not None:
            sql += f" LIMIT {limit}"

        raw_rows = con.execute(sql).fetchall()

        rel = KRelation(schema, semiring)
        for raw_row in raw_rows:
            row: Dict[str, Any] = {}
            for col_name, raw_val in zip(schema, raw_row):
                hint = type_hints[col_name]
                if raw_val is None:
                    row[col_name] = None
                elif hint == "DATE":
                    # Preserve as datetime.date
                    if isinstance(raw_val, date):
                        row[col_name] = raw_val
                    else:
                        row[col_name] = date.fromisoformat(str(raw_val))
                elif hint == "DECIMAL":
                    # Preserve as Decimal
                    if isinstance(raw_val, Decimal):
                        row[col_name] = raw_val
                    else:
                        row[col_name] = Decimal(str(raw_val))
                elif hint == "INT":
                    row[col_name] = int(raw_val)
                else:
                    row[col_name] = str(raw_val) if not isinstance(raw_val, str) else raw_val
            rel.insert(row)

        result[table_name] = rel

    return result


def generate_tpch_csvs(
    sf: float,
    output_dir: Union[str, Path],
    limit: Optional[int] = None,
) -> List[str]:
    """
    Generate TPC-H data via DuckDB and write CSV files to output_dir.
    - Line 1: type hints (``INT`` or ``STR`` per column)
    - Line 2: column names
    - Line 3+: data rows

    Parameters
    ----------
    sf : float
        TPC-H scale factor (e.g. 0.01 for ~600 lineitem rows).
    output_dir : str or Path
        Directory to write the CSV files to. Created if it does not exist.
    limit : int, optional
        Cap each table at this many rows.

    Returns
    -------
    List[str]
        Names of tables written (e.g. ``['nation', 'region', ...]``).

    Raises
    ------
    ImportError
        If ``duckdb`` is not installed.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        import duckdb
    except ImportError:
        raise ImportError("DuckDB not installed; run `pip install duckdb` to use TPC-H data generation")

    con = duckdb.connect()
    con.install_extension("tpch")
    con.load_extension("tpch")
    con.execute(f"CALL dbgen(sf={sf})")

    written: List[str] = []

    for table_name, col_defs in SCHEMAS.items():
        schema = [name for name, _ in col_defs]
        type_hints = [hint for _, hint in col_defs]
        hint_map = dict(col_defs)

        sql = f"SELECT {', '.join(schema)} FROM {table_name}"
        if limit is not None:
            sql += f" LIMIT {limit}"

        raw_rows = con.execute(sql).fetchall()

        csv_path = output_dir / f"{table_name}.csv"
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(type_hints)
            writer.writerow(schema)
            for raw_row in raw_rows:
                vals: List[str] = []
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

    return written


def load_tpch_csvs(
    csv_dir: Union[str, Path],
    semiring: Semiring,
    tables: Optional[List[str]] = None,
    limit: Optional[int] = None,
    annotation_factory: Optional[Callable[[str, int, Dict[str, Any]], Any]] = None,
) -> Dict[str, KRelation]:
    """
    Load TPC-H CSV files into KRelations.

    Parameters
    ----------
    csv_dir : str or Path
        Directory containing the CSV files (e.g. ``data/tpch/``).
    semiring : Semiring
        The semiring to annotate tuples with.
    tables : list of str, optional
        Load only these tables.  If omitted, all available CSVs are loaded.
    limit : int, optional
        Cap each table at this many rows.
    annotation_factory : callable, optional
        If provided, called as ``annotation_factory(table_name, row_index, row)``
        for each loaded row. Its return value is used as the tuple annotation.
        When omitted, rows receive ``semiring.one()`` via ``KRelation.insert``.

    Returns
    -------
    Dict[str, KRelation]
        Mapping from table name to loaded KRelation.

    Raises
    ------
    FileNotFoundError
        If csv_dir does not exist or contains no TPC-H CSV files.
    """
    csv_dir = Path(csv_dir)
    if not csv_dir.is_dir():
        raise FileNotFoundError(f"TPC-H CSV directory not found: {csv_dir}")

    table_names = (
        [t.lower() for t in tables] if tables is not None
        else list(SCHEMAS.keys())
    )

    result: Dict[str, KRelation] = {}
    for table_name in table_names:
        csv_path = csv_dir / f"{table_name}.csv"
        if not csv_path.exists():
            continue

        col_defs = SCHEMAS[table_name]
        schema = [name for name, _ in col_defs]
        types = [hint for _, hint in col_defs]

        rel = KRelation(schema, semiring)
        with open(csv_path, "r", encoding="utf-8", newline="") as f:
            reader = csv.reader(f)
            next(reader)  # skip type-hints row
            next(reader)  # skip header row
            count = 0
            for values in reader:
                if not values:
                    continue
                row: Dict[str, Any] = {}
                for col, val, hint in zip(schema, values, types):
                    if not val:
                        row[col] = None
                    elif hint == "INT":
                        row[col] = int(val)
                    elif hint == "DATE":
                        row[col] = date.fromisoformat(val)
                    elif hint == "DECIMAL":
                        row[col] = Decimal(val)
                    else:
                        row[col] = val
                annotation = (
                    annotation_factory(table_name, count + 1, row)
                    if annotation_factory is not None
                    else None
                )
                rel.insert(row, annotation)
                count += 1
                if limit is not None and count >= limit:
                    break
        result[table_name] = rel

    if not result:
        raise FileNotFoundError(
            f"No TPC-H CSV files found in {csv_dir}. "
            f"Generate them with: python -m scripts.generate_tpch_data"
        )

    return result
