"""
Tests for date arithmetic in the SQL translator and the TPC-H data loader.
"""

from pathlib import Path

import pytest

from src.sql_to_ra import sql_to_ra, sql_to_ra_with_aliases, SQLTranslationError
from src.parser import parse
from src.semirings import BOOL_SR, BOOLFUNC_SR, BoolFunc
from src.io.tpch_loader import (
    SCHEMAS,
    generate_tpch_csvs,
    load_tpch_csvs,
)


# ══════════════════════════════════════════════════════════════════════
# Date arithmetic tests
# ══════════════════════════════════════════════════════════════════════

class TestDateArithmetic:

    def test_date_plus_year(self):
        """date '1994-01-01' + interval '1' year → '1995-01-01'"""
        ra = sql_to_ra(
            "SELECT * FROM orders "
            "WHERE o_orderdate < date '1994-01-01' + interval '1' year"
        )
        assert "'1995-01-01'" in ra

    def test_date_plus_month(self):
        """date '1993-10-01' + interval '3' month → '1994-01-01'"""
        ra = sql_to_ra(
            "SELECT * FROM orders "
            "WHERE o_orderdate < date '1993-10-01' + interval '3' month"
        )
        assert "'1994-01-01'" in ra

    def test_date_plus_day(self):
        """date '1994-01-01' + interval '10' day → '1994-01-11'"""
        ra = sql_to_ra(
            "SELECT * FROM orders "
            "WHERE o_orderdate < date '1994-01-01' + interval '10' day"
        )
        assert "'1994-01-11'" in ra

    def test_date_minus_year(self):
        """date '1995-01-01' - interval '1' year → '1994-01-01'"""
        # We need to handle MINUS as a negative interval
        ra = sql_to_ra(
            "SELECT * FROM orders "
            "WHERE o_orderdate >= date '1995-01-01' - interval '1' year"
        )
        assert "'1994-01-01'" in ra

    def test_date_month_overflow(self):
        """date '1994-11-01' + interval '3' month → '1995-02-01'"""
        ra = sql_to_ra(
            "SELECT * FROM orders "
            "WHERE o_orderdate < date '1994-11-01' + interval '3' month"
        )
        assert "'1995-02-01'" in ra

    def test_date_arithmetic_parseable(self):
        """Result of date arithmetic is parseable."""
        ra = sql_to_ra(
            "SELECT * FROM orders "
            "WHERE o_orderdate >= date '1994-01-01' "
            "AND o_orderdate < date '1994-01-01' + interval '1' year"
        )
        ast = parse(ra)
        assert ast is not None

    def test_between_with_date_arithmetic(self):
        """BETWEEN with computed dates."""
        ra = sql_to_ra(
            "SELECT * FROM lineitem "
            "WHERE l_shipdate >= date '1995-01-01' "
            "AND l_shipdate <= date '1995-01-01' + interval '1' year"
        )
        assert "'1996-01-01'" in ra

    def test_no_interval_raises(self):
        """+ without INTERVAL after date should raise."""
        with pytest.raises(SQLTranslationError, match="INTERVAL"):
            sql_to_ra(
                "SELECT * FROM orders "
                "WHERE o_orderdate < date '1994-01-01' + 1"
            )


# ══════════════════════════════════════════════════════════════════════
# DuckDB TPC-H generator tests
# ══════════════════════════════════════════════════════════════════════

class TestDuckDBLoader:
    """Tests for load_tpch_from_duckdb() using the DuckDB TPC-H extension."""

    pytest.importorskip("duckdb", reason="duckdb not installed")

    def test_all_tables_loaded(self):
        """All 8 tables are generated at SF 0.001."""
        from src.io.tpch_loader import load_tpch_from_duckdb
        tables = load_tpch_from_duckdb(sf=0.001, semiring=BOOL_SR)
        expected = {'nation', 'region', 'supplier', 'customer',
                    'orders', 'lineitem', 'part', 'partsupp'}
        assert set(tables.keys()) == expected

    def test_fixed_size_tables(self):
        """nation=25, region=5 regardless of scale factor (TPC-H spec)."""
        from src.io.tpch_loader import load_tpch_from_duckdb
        tables = load_tpch_from_duckdb(sf=0.001, semiring=BOOL_SR)
        assert tables['nation'].support_size() == 25
        assert tables['region'].support_size() == 5

    def test_date_columns_are_dates(self):
        """Date columns (l_shipdate, o_orderdate) are datetime.date objects."""
        from src.io.tpch_loader import load_tpch_from_duckdb
        tables = load_tpch_from_duckdb(sf=0.001, semiring=BOOL_SR, limit=1)
        orders = tables['orders']
        first = next(iter(orders._data))
        row = dict(zip(orders.schema, first))
        from datetime import date
        assert isinstance(row['o_orderdate'], date), "o_orderdate should be a datetime.date"

    def test_integer_columns_typed(self):
        """Key and linenumber columns are Python int; l_quantity is Decimal."""
        from src.io.tpch_loader import load_tpch_from_duckdb
        from decimal import Decimal
        tables = load_tpch_from_duckdb(sf=0.001, semiring=BOOL_SR, limit=1)
        li = tables['lineitem']
        first = next(iter(li._data))
        row = dict(zip(li.schema, first))
        assert isinstance(row['l_orderkey'], int)
        assert isinstance(row['l_quantity'], Decimal)
        assert isinstance(row['l_partkey'], int)

    def test_decimal_monetary_columns_are_decimals(self):
        """Monetary DECIMAL columns (extendedprice, discount) are Decimal."""
        from src.io.tpch_loader import load_tpch_from_duckdb
        from decimal import Decimal
        tables = load_tpch_from_duckdb(sf=0.001, semiring=BOOL_SR, limit=1)
        li = tables['lineitem']
        first = next(iter(li._data))
        row = dict(zip(li.schema, first))
        assert isinstance(row['l_extendedprice'], Decimal)
        assert isinstance(row['l_discount'], Decimal)

    def test_limit_parameter(self):
        """limit= caps rows per table."""
        from src.io.tpch_loader import load_tpch_from_duckdb
        tables = load_tpch_from_duckdb(sf=0.01, semiring=BOOL_SR, limit=10)
        # lineitem would normally have ~600 rows at SF 0.01
        assert tables['lineitem'].support_size() <= 10

    def test_subset_of_tables(self):
        """tables= parameter loads only specified tables."""
        from src.io.tpch_loader import load_tpch_from_duckdb
        tables = load_tpch_from_duckdb(
            sf=0.001, semiring=BOOL_SR, tables=['nation', 'region']
        )
        assert set(tables.keys()) == {'nation', 'region'}

    def test_no_duckdb_raises(self, monkeypatch):
        """ImportError raised if duckdb not available."""
        import builtins

        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == 'duckdb':
                raise ImportError("no module named duckdb")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, '__import__', mock_import)

        from src.io.tpch_loader import load_tpch_from_duckdb
        with pytest.raises(ImportError, match="pip install duckdb"):
            load_tpch_from_duckdb(sf=0.001, semiring=BOOL_SR)


# ══════════════════════════════════════════════════════════════════════
# SQL script translation tests (test all 8 scripts translate + parse)
# ══════════════════════════════════════════════════════════════════════

_SQL_DIR = Path(__file__).resolve().parent.parent.parent / "test_sql_script"


@pytest.mark.parametrize("sql_file", sorted(_SQL_DIR.glob("*.sql")) if _SQL_DIR.is_dir() else [])
def test_sql_script_translates(sql_file):
    """Each .sql script in test_sql_script/ translates to parseable RA."""
    sql_text = sql_file.read_text(encoding="utf-8")
    # Strip comment lines
    lines = [l for l in sql_text.splitlines() if not l.strip().startswith("--")]
    sql = "\n".join(lines).strip()

    ra_expr, alias_map = sql_to_ra_with_aliases(sql)
    assert ra_expr, f"Empty RA expression for {sql_file.name}"

    ast = parse(ra_expr)
    assert ast is not None, f"Failed to parse RA for {sql_file.name}"


# ══════════════════════════════════════════════════════════════════════
# TPC-H CSV generation + loading round-trip tests
# ══════════════════════════════════════════════════════════════════════

class TestTpchCsvRoundTrip:
    """Tests for generate_tpch_csvs() and load_tpch_csvs()."""

    pytest.importorskip("duckdb", reason="duckdb not installed")

    def test_generate_creates_all_csvs(self, tmp_path):
        """generate_tpch_csvs writes one CSV per TPC-H table."""
        written = generate_tpch_csvs(sf=0.001, output_dir=tmp_path)
        assert set(written) == set(SCHEMAS.keys())
        for table_name in SCHEMAS:
            assert (tmp_path / f"{table_name}.csv").exists()

    def test_csv_format_has_type_and_header_rows(self, tmp_path):
        """Each CSV starts with type hints, then column names."""
        generate_tpch_csvs(sf=0.001, output_dir=tmp_path, limit=5)
        lines = (tmp_path / "nation.csv").read_text().strip().splitlines()
        assert lines[0] == "INT,STR,INT,STR"  # type hints for nation
        assert lines[1] == "n_nationkey,n_name,n_regionkey,n_comment"

    def test_round_trip_preserves_data(self, tmp_path):
        """Data survives generate → load round-trip."""
        generate_tpch_csvs(sf=0.001, output_dir=tmp_path, limit=10)
        tables = load_tpch_csvs(tmp_path, BOOL_SR)
        assert tables['nation'].support_size() == 10
        assert tables['region'].support_size() == 5  # only 5 regions in TPC-H

    def test_load_with_limit(self, tmp_path):
        """load_tpch_csvs respects the limit parameter."""
        generate_tpch_csvs(sf=0.001, output_dir=tmp_path)
        tables = load_tpch_csvs(tmp_path, BOOL_SR, limit=3)
        assert tables['nation'].support_size() == 3

    def test_load_subset_of_tables(self, tmp_path):
        """tables= parameter loads only the requested tables."""
        generate_tpch_csvs(sf=0.001, output_dir=tmp_path, limit=5)
        tables = load_tpch_csvs(tmp_path, BOOL_SR, tables=['nation', 'region'])
        assert set(tables.keys()) == {'nation', 'region'}

    def test_load_missing_dir_raises(self):
        """FileNotFoundError when CSV directory does not exist."""
        with pytest.raises(FileNotFoundError):
            load_tpch_csvs("/nonexistent/dir", BOOL_SR)

    def test_integer_columns_typed_after_round_trip(self, tmp_path):
        """Integer columns remain int after CSV round-trip."""
        generate_tpch_csvs(sf=0.001, output_dir=tmp_path, limit=1)
        tables = load_tpch_csvs(tmp_path, BOOL_SR)
        nation = tables['nation']
        first = next(iter(nation._data))
        row = dict(zip(nation.schema, first))
        assert isinstance(row['n_nationkey'], int)
        assert isinstance(row['n_regionkey'], int)

    def test_load_tpch_csvs_annotation_factory_assigns_tuple_variables(self, tmp_path):
        """annotation_factory can attach deterministic provenance variables per row."""
        generate_tpch_csvs(sf=0.001, output_dir=tmp_path, limit=2)
        tables = load_tpch_csvs(
            tmp_path,
            BOOLFUNC_SR,
            tables=['nation'],
            limit=2,
            annotation_factory=lambda table_name, row_index, row: BoolFunc.var(
                f"{table_name}_{row_index}"
            ),
        )

        annotations = list(tables['nation']._data.values())
        assert annotations == [
            BoolFunc.var('nation_1'),
            BoolFunc.var('nation_2'),
        ]

    def test_generate_with_limit(self, tmp_path):
        """limit= caps rows in the generated CSV."""
        generate_tpch_csvs(sf=0.001, output_dir=tmp_path, limit=3)
        lines = (tmp_path / "nation.csv").read_text().strip().splitlines()
        # 2 header lines + 3 data lines
        assert len(lines) == 5

    def test_schema_coverage(self):
        """All 8 TPC-H tables have schema definitions."""
        expected = {'nation', 'region', 'supplier', 'customer',
                    'orders', 'lineitem', 'part', 'partsupp'}
        assert set(SCHEMAS.keys()) == expected
