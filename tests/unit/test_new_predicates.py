"""
Unit tests for the new predicate operators: IN, LIKE, NOT LIKE,
BETWEEN, and modulo (%).

These tests verify the end-to-end flow: SQL → RA → parse → evaluate.

Test index
----------
TNP-1   IN list with integers
TNP-2   NOT IN list with integers
TNP-3   IN list with strings
TNP-4   LIKE with % wildcard
TNP-5   NOT LIKE with % wildcard
TNP-6   LIKE with _ wildcard
TNP-7   BETWEEN with integers
TNP-8   Modulo in condition (attr % val == 0)
TNP-9   DATE literal comparison
TNP-10  Combined predicates (IN + NOT LIKE + modulo)
TNP-11  RA parser: IN expression parsed directly
TNP-12  RA parser: LIKE expression parsed directly
TNP-13  RA parser: BETWEEN expression parsed directly
TNP-14  RA parser: modulo expression parsed directly
TNP-15  Evaluator: IN predicate filters correctly
TNP-16  Evaluator: NOT IN predicate filters correctly
TNP-17  Evaluator: LIKE predicate filters correctly
TNP-18  Evaluator: NOT LIKE predicate filters correctly
TNP-19  Evaluator: BETWEEN predicate filters correctly
TNP-20  Evaluator: modulo predicate filters correctly
"""

import pytest

from src.parser import parse
from src.sql_to_ra import sql_to_ra
from src.evaluator import Evaluator
from src.relation.k_relation import KRelation
from src.semirings.boolean import BooleanSemiring
from src.semirings.counting import CountingSemiring
from src.strategies import DedupStrategy


# ── Helpers ───────────────────────────────────────────────────────────

def _make_relation(schema, rows, semiring):
    """Create a KRelation from schema and row dicts."""
    rel = KRelation(schema, semiring)
    for row in rows:
        rel.insert(row)
    return rel


# ── Test data ─────────────────────────────────────────────────────────

@pytest.fixture
def counting():
    return CountingSemiring()


@pytest.fixture
def boolean():
    return BooleanSemiring()


@pytest.fixture
def parts_relation(counting):
    schema = ['p_partkey', 'p_brand', 'p_type', 'p_size']
    rows = [
        {'p_partkey': 64, 'p_brand': 'Brand#12', 'p_type': 'MEDIUM POLISHED STEEL', 'p_size': 5},
        {'p_partkey': 128, 'p_brand': 'Brand#45', 'p_type': 'SMALL BRUSHED TIN', 'p_size': 14},
        {'p_partkey': 192, 'p_brand': 'Brand#23', 'p_type': 'LARGE BURNISHED COPPER', 'p_size': 49},
        {'p_partkey': 256, 'p_brand': 'Brand#34', 'p_type': 'MEDIUM POLISHED BRASS', 'p_size': 3},
        {'p_partkey': 100, 'p_brand': 'Brand#12', 'p_type': 'SMALL PLATED STEEL', 'p_size': 9},
    ]
    return _make_relation(schema, rows, counting)


@pytest.fixture
def dates_relation(counting):
    schema = ['id', 'shipdate', 'quantity']
    rows = [
        {'id': 1, 'shipdate': '1994-06-15', 'quantity': 5},
        {'id': 2, 'shipdate': '1995-03-20', 'quantity': 12},
        {'id': 3, 'shipdate': '1995-12-01', 'quantity': 25},
        {'id': 4, 'shipdate': '1993-01-10', 'quantity': 8},
    ]
    return _make_relation(schema, rows, counting)


# ── SQL translation tests ────────────────────────────────────────────

class TestSQLTranslation:
    """Tests that SQL constructs translate to correct RA strings."""

    def test_in_integers(self):
        """TNP-1: IN list with integers."""
        ra = sql_to_ra("SELECT * FROM R WHERE A IN (1, 2, 3)")
        assert "A IN (1, 2, 3)" in ra

    def test_not_in_integers(self):
        """TNP-2: NOT IN list with integers."""
        ra = sql_to_ra("SELECT * FROM R WHERE A NOT IN (1, 2)")
        assert "A NOT IN (1, 2)" in ra

    def test_in_strings(self):
        """TNP-3: IN list with strings."""
        ra = sql_to_ra("SELECT * FROM R WHERE name IN ('foo', 'bar')")
        assert "IN" in ra

    def test_like_percent(self):
        """TNP-4: LIKE with % wildcard."""
        ra = sql_to_ra("SELECT * FROM R WHERE name LIKE 'MEDIUM%'")
        assert "name LIKE 'MEDIUM%'" in ra

    def test_not_like(self):
        """TNP-5: NOT LIKE with % wildcard."""
        ra = sql_to_ra("SELECT * FROM R WHERE name NOT LIKE 'MEDIUM%'")
        assert "name NOT LIKE 'MEDIUM%'" in ra

    def test_between(self):
        """TNP-7: BETWEEN with integers."""
        ra = sql_to_ra("SELECT * FROM R WHERE A BETWEEN 1 AND 10")
        assert "A BETWEEN 1 AND 10" in ra

    def test_modulo(self):
        """TNP-8: Modulo in WHERE condition."""
        ra = sql_to_ra("SELECT * FROM R WHERE A%64 = 0")
        assert "A % 64" in ra

    def test_date_literal(self):
        """TNP-9: DATE literal becomes string literal."""
        ra = sql_to_ra("SELECT * FROM R WHERE d < date '1995-03-15'")
        assert "'1995-03-15'" in ra
        assert "DATE" not in ra.upper().replace("'1995-03-15'", "")


# ── RA parser tests ──────────────────────────────────────────────────

class TestRAParsing:
    """Tests that RA expressions with new operators parse correctly."""

    def test_parse_in(self):
        """TNP-11: IN expression parsed directly."""
        ast = parse("σ[A IN (1, 2, 3)](R)")
        assert ast is not None

    def test_parse_not_in(self):
        """TNP-11b: NOT IN expression parsed directly."""
        ast = parse("σ[A NOT IN (1, 2)](R)")
        assert ast is not None

    def test_parse_like(self):
        """TNP-12: LIKE expression parsed directly."""
        ast = parse("σ[name LIKE 'MEDIUM%'](R)")
        assert ast is not None

    def test_parse_not_like(self):
        """TNP-12b: NOT LIKE expression parsed directly."""
        ast = parse("σ[name NOT LIKE 'MEDIUM%'](R)")
        assert ast is not None

    def test_parse_between(self):
        """TNP-13: BETWEEN expression parsed directly."""
        ast = parse("σ[A BETWEEN 1 AND 10](R)")
        assert ast is not None

    def test_parse_modulo(self):
        """TNP-14: Modulo expression parsed directly."""
        ast = parse("σ[A % 64 == 0](R)")
        assert ast is not None


# ── Evaluator tests ──────────────────────────────────────────────────

class TestEvaluator:
    """Tests that new predicates correctly filter K-relations."""

    def test_in_predicate(self, parts_relation, counting):
        """TNP-15: IN predicate filters to matching rows."""
        tables = {'part': parts_relation}
        evaluator = Evaluator(tables, counting)
        ast = parse("σ[p_size IN (5, 14, 49)](part)")
        result = evaluator.evaluate(ast)
        assert result.support_size() == 3

    def test_not_in_predicate(self, parts_relation, counting):
        """TNP-16: NOT IN predicate excludes matching rows."""
        tables = {'part': parts_relation}
        evaluator = Evaluator(tables, counting)
        ast = parse("σ[p_size NOT IN (5, 14, 49)](part)")
        result = evaluator.evaluate(ast)
        assert result.support_size() == 2

    def test_like_predicate(self, parts_relation, counting):
        """TNP-17: LIKE predicate matches pattern."""
        tables = {'part': parts_relation}
        evaluator = Evaluator(tables, counting)
        ast = parse("σ[p_type LIKE 'MEDIUM%'](part)")
        result = evaluator.evaluate(ast)
        # 'MEDIUM POLISHED STEEL' and 'MEDIUM POLISHED BRASS' match
        assert result.support_size() == 2

    def test_not_like_predicate(self, parts_relation, counting):
        """TNP-18: NOT LIKE predicate excludes matching rows."""
        tables = {'part': parts_relation}
        evaluator = Evaluator(tables, counting)
        ast = parse("σ[p_type NOT LIKE 'MEDIUM%'](part)")
        result = evaluator.evaluate(ast)
        assert result.support_size() == 3

    def test_between_predicate(self, parts_relation, counting):
        """TNP-19: BETWEEN predicate filters to range."""
        tables = {'part': parts_relation}
        evaluator = Evaluator(tables, counting)
        ast = parse("σ[p_size BETWEEN 5 AND 14](part)")
        result = evaluator.evaluate(ast)
        # p_size 5, 14, 3, 9 → 5 and 14 and 9 are in [5,14], 3 is not, 49 is not
        assert result.support_size() == 3

    def test_modulo_predicate(self, parts_relation, counting):
        """TNP-20: Modulo predicate filters correctly."""
        tables = {'part': parts_relation}
        evaluator = Evaluator(tables, counting)
        ast = parse("σ[p_partkey % 128 == 0](part)")
        result = evaluator.evaluate(ast)
        # 64 % 128 = 64 (no), 128 % 128 = 0 (yes), 192 % 128 = 64 (no),
        # 256 % 128 = 0 (yes), 100 % 128 = 100 (no)
        assert result.support_size() == 2

    def test_date_comparison(self, dates_relation, counting):
        """TNP-9b: Date strings compare correctly with < operator."""
        tables = {'lineitem': dates_relation}
        evaluator = Evaluator(tables, counting)
        ast = parse("σ[shipdate < '1995-03-15'](lineitem)")
        result = evaluator.evaluate(ast)
        # '1994-06-15' < '1995-03-15' yes, '1995-03-20' no,
        # '1995-12-01' no, '1993-01-10' yes
        assert result.support_size() == 2

    def test_combined_predicates(self, parts_relation, counting):
        """TNP-10: Combined IN + NOT LIKE + comparison."""
        tables = {'part': parts_relation}
        evaluator = Evaluator(tables, counting)
        ast = parse(
            "σ[p_brand != 'Brand#45' "
            "/\\ p_type NOT LIKE 'MEDIUM%' "
            "/\\ p_size IN (5, 14, 49, 9)](part)"
        )
        result = evaluator.evaluate(ast)
        # Brand#45 excluded → row 2 (p_size 14) out
        # MEDIUM% excluded → rows 1,4 out
        # p_size IN (5,14,49,9) → row 5 (p_size 9) in, row 3 (p_size 49) in
        # Row 3: Brand#23, LARGE BURNISHED COPPER, size 49 → passes all
        # Row 5: Brand#12, SMALL PLATED STEEL, size 9 → passes all
        assert result.support_size() == 2
