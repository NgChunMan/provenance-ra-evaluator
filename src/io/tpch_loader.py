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

Column schemas and type hints follow the TPC-H specification (v2.18.0).
Integer columns are parsed as ``int``; dates are ISO-format strings;
decimal monetary columns are kept as ``str`` (not used in predicates).
"""

from __future__ import annotations

import csv
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from src.semirings.base import Semiring
from src.relation.k_relation import KRelation


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
        ("s_acctbal", "STR"),  # decimal — kept as string
        ("s_comment", "STR"),
    ],
    "customer": [
        ("c_custkey", "INT"),
        ("c_name", "STR"),
        ("c_address", "STR"),
        ("c_nationkey", "INT"),
        ("c_phone", "STR"),
        ("c_acctbal", "STR"),  # decimal
        ("c_mktsegment", "STR"),
        ("c_comment", "STR"),
    ],
    "orders": [
        ("o_orderkey", "INT"),
        ("o_custkey", "INT"),
        ("o_orderstatus", "STR"),
        ("o_totalprice", "STR"),  # decimal
        ("o_orderdate", "STR"),  # date as string YYYY-MM-DD
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
        ("l_quantity", "INT"),
        ("l_extendedprice", "STR"),  # decimal
        ("l_discount", "STR"),  # decimal
        ("l_tax", "STR"),  # decimal
        ("l_returnflag", "STR"),
        ("l_linestatus", "STR"),
        ("l_shipdate", "STR"),  # date
        ("l_commitdate", "STR"),  # date
        ("l_receiptdate", "STR"),  # date
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
        ("p_retailprice", "STR"),  # decimal
        ("p_comment", "STR"),
    ],
    "partsupp": [
        ("ps_partkey", "INT"),
        ("ps_suppkey", "INT"),
        ("ps_availqty", "INT"),
        ("ps_supplycost", "STR"),  # decimal
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
    # - BIGINT / INTEGER → already int
    # - DECIMAL → int (for INT-typed columns) or str (for STR-typed)
    # - DATE   → ISO-format string 'YYYY-MM-DD' (for evaluator comparisons)
    # - VARCHAR → str (already)

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
                    row[col_name] = ""
                elif isinstance(raw_val, date):
                    # DATE columns → 'YYYY-MM-DD' string for predicate comparison
                    row[col_name] = raw_val.isoformat()
                elif isinstance(raw_val, Decimal):
                    if hint == "INT":
                        row[col_name] = int(raw_val)
                    else:
                        row[col_name] = str(raw_val)
                elif hint == "INT" and not isinstance(raw_val, int):
                    row[col_name] = int(raw_val)
                elif hint == "STR" and not isinstance(raw_val, str):
                    row[col_name] = str(raw_val)
                else:
                    row[col_name] = raw_val
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
                    row[col] = int(val) if hint == "INT" else val
                rel.insert(row)
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
