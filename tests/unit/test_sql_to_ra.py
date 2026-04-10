"""
Unit tests for the SQL-to-Relational-Algebra translator.

Test index
----------
TC-01  SELECT * FROM single table → bare table name
TC-02  SELECT columns FROM table → π projection
TC-03  SELECT DISTINCT * → δ only
TC-04  SELECT DISTINCT cols → δ(π(…))
TC-05  WHERE equality (integer)
TC-06  WHERE inequality (!=)
TC-07  WHERE diamond-bracket inequality (<>)
TC-08  WHERE greater-than / less-than
TC-09  WHERE string literal
TC-10  WHERE AND condition
TC-11  WHERE OR condition
TC-12  WHERE NOT condition
TC-13  WHERE parenthesised group: (A OR B) AND C
TC-14  FROM two tables → cross product
TC-15  FROM three tables → left-associative cross products
TC-16  FROM two tables WITH equi-join condition
TC-17  Full pipeline: DISTINCT + cols + WHERE
TC-18  UNION of two queries
TC-19  UNION ALL (treated as multiset UNION)
TC-20  Qualified column reference (T.col)
TC-21  Case-insensitive keywords
TC-22  AS alias on table (ignored)
TC-23  AS alias on column (ignored)
TC-24  Each translated string is parseable by the RA parser
TC-25  GROUP BY raises SQLTranslationError
TC-26  ORDER BY raises SQLTranslationError
TC-27  JOIN raises SQLTranslationError
TC-28  INTERSECT raises SQLTranslationError
TC-29  Unterminated string literal raises SQLTranslationError
TC-30  Missing FROM clause raises SQLTranslationError
TC-31  Empty query raises SQLTranslationError
TC-32  Unrecognised character raises SQLTranslationError
"""

import pytest

from src.sql_to_ra import sql_to_ra, sql_to_ra_with_aliases, SQLTranslationError
from src.parser import parse


# ── Basic SELECT ──────────────────────────────────────────────────────

def test_select_star_single_table():
    """TC-01: SELECT * from one table → bare table name."""
    assert sql_to_ra("SELECT * FROM R") == "R"


def test_select_columns():
    """TC-02: SELECT with explicit columns → π projection."""
    assert sql_to_ra("SELECT A, B FROM R") == "π[A, B](R)"


def test_select_distinct_star():
    """TC-03: SELECT DISTINCT * → deduplication only."""
    assert sql_to_ra("SELECT DISTINCT * FROM R") == "δ(R)"


def test_select_distinct_columns():
    """TC-04: SELECT DISTINCT cols → δ(π(…))."""
    assert sql_to_ra("SELECT DISTINCT A FROM R") == "δ(π[A](R))"


# ── WHERE conditions ──────────────────────────────────────────────────

def test_where_equality_integer():
    """TC-05: = with integer literal → ==."""
    assert sql_to_ra("SELECT * FROM R WHERE A = 1") == "σ[A == 1](R)"


def test_where_inequality_ne():
    """TC-06: != stays !=."""
    assert sql_to_ra("SELECT * FROM R WHERE A != 1") == "σ[A != 1](R)"


def test_where_inequality_diamond():
    """TC-07: <> maps to !=."""
    assert sql_to_ra("SELECT * FROM R WHERE A <> 1") == "σ[A != 1](R)"


def test_where_greater_than():
    """TC-08: > and < pass through unchanged."""
    assert sql_to_ra("SELECT * FROM R WHERE A > 1") == "σ[A > 1](R)"
    assert sql_to_ra("SELECT * FROM R WHERE A < 1") == "σ[A < 1](R)"
    assert sql_to_ra("SELECT * FROM R WHERE A >= 1") == "σ[A >= 1](R)"
    assert sql_to_ra("SELECT * FROM R WHERE A <= 1") == "σ[A <= 1](R)"


def test_where_string_literal():
    """TC-09: String literal comparison preserves surrounding quotes."""
    assert sql_to_ra("SELECT * FROM R WHERE B = 'x'") == "σ[B == 'x'](R)"


def test_where_and_condition():
    """TC-10: SQL AND → RA /\\."""
    result = sql_to_ra("SELECT * FROM R WHERE A = 1 AND B = 'x'")
    assert result == "σ[A == 1 /\\ B == 'x'](R)"


def test_where_or_condition():
    """TC-11: SQL OR → RA \\/."""
    result = sql_to_ra("SELECT * FROM R WHERE A = 1 OR A = 2")
    assert result == "σ[A == 1 \\/ A == 2](R)"


def test_where_not_condition():
    """TC-12: SQL NOT → RA ~(…)."""
    result = sql_to_ra("SELECT * FROM R WHERE NOT A = 1")
    assert result == "σ[~(A == 1)](R)"


def test_where_parenthesised_condition():
    """TC-13: Parenthesised group preserves precedence."""
    result = sql_to_ra("SELECT * FROM R WHERE (A = 1 OR A = 2) AND B = 'x'")
    assert result == "σ[(A == 1 \\/ A == 2) /\\ B == 'x'](R)"


# ── Cross product ─────────────────────────────────────────────────────

def test_from_two_tables():
    """TC-14: Two tables → cross product."""
    assert sql_to_ra("SELECT * FROM R, S") == "(R × S)"


def test_from_three_tables():
    """TC-15: Three tables → left-associative cross products."""
    assert sql_to_ra("SELECT * FROM R, S, T") == "((R × S) × T)"


def test_from_two_tables_with_join_condition():
    """TC-16: Cross product with equi-join WHERE condition."""
    result = sql_to_ra("SELECT * FROM R, S WHERE R.A = S.A")
    assert result == "σ[R.A == S.A]((R × S))"


# ── Full pipelines ────────────────────────────────────────────────────

def test_full_pipeline():
    """TC-17: DISTINCT + projection + selection in one query."""
    result = sql_to_ra("SELECT DISTINCT Name FROM Emp WHERE Dept = 'Eng'")
    assert result == "δ(π[Name](σ[Dept == 'Eng'](Emp)))"


# ── UNION ─────────────────────────────────────────────────────────────

def test_union():
    """TC-18: UNION deduplicates → δ(⊎)."""
    result = sql_to_ra("SELECT A FROM R UNION SELECT A FROM S")
    assert result == "δ((π[A](R) ∪ π[A](S)))"


def test_union_all():
    """TC-19: UNION ALL keeps all copies → plain ⊎, no deduplication."""
    result = sql_to_ra("SELECT A FROM R UNION ALL SELECT A FROM S")
    assert result == "(π[A](R) ∪ π[A](S))"


# ── Syntax variants ───────────────────────────────────────────────────

def test_qualified_column_reference():
    """TC-20: Table-qualified column reference T.col passes through."""
    result = sql_to_ra("SELECT R.A FROM R, S WHERE R.A = S.A")
    assert result == "π[R.A](σ[R.A == S.A]((R × S)))"


def test_case_insensitive_keywords():
    """TC-21: SQL keywords are case-insensitive; identifiers preserve case."""
    assert sql_to_ra("select * from R where A = 1") == "σ[A == 1](R)"
    assert sql_to_ra("SELECT DISTINCT * FROM R") == sql_to_ra("select distinct * from R")


def test_as_alias_on_table():
    """TC-22: AS alias on table name uses alias in RA expression."""
    assert sql_to_ra("SELECT * FROM Employees AS E") == "E"


def test_as_alias_on_column_ignored():
    """TC-23: AS alias on column is silently ignored."""
    assert sql_to_ra("SELECT Name AS n FROM R") == "π[Name](R)"


# ── RA parser compatibility ───────────────────────────────────────────

@pytest.mark.parametrize("sql", [
    "SELECT * FROM R",
    "SELECT DISTINCT Name FROM Emp WHERE Dept = 'Eng'",
    "SELECT A FROM R UNION SELECT A FROM S",
    "SELECT * FROM R WHERE A = 1 AND B = 'x'",
    "SELECT * FROM R WHERE (A = 1 OR A = 2) AND B = 'x'",
    "SELECT * FROM R, S WHERE R.A = S.A",
    "SELECT A, B FROM R WHERE NOT A = 1",
])
def test_translated_string_is_parseable(sql):
    """TC-24: Every translated RA string is parseable by the RA parser."""
    ra = sql_to_ra(sql)
    parse(ra)  # must not raise


# ── Error handling ────────────────────────────────────────────────────

def test_group_by_raises():
    """TC-25: GROUP BY is an unsupported clause."""
    with pytest.raises(SQLTranslationError, match="GROUP BY"):
        sql_to_ra("SELECT A FROM R GROUP BY A")


def test_order_by_raises():
    """TC-26: ORDER BY is an unsupported clause."""
    with pytest.raises(SQLTranslationError, match="ORDER BY"):
        sql_to_ra("SELECT * FROM R ORDER BY A")


def test_join_raises():
    """TC-27: JOIN … ON is unsupported (use FROM t1, t2 WHERE … instead)."""
    with pytest.raises(SQLTranslationError, match="JOIN"):
        sql_to_ra("SELECT * FROM R JOIN S ON R.A = S.A")


def test_intersect_raises():
    """TC-28: INTERSECT is unsupported."""
    with pytest.raises(SQLTranslationError, match="INTERSECT"):
        sql_to_ra("SELECT A FROM R INTERSECT SELECT A FROM S")


def test_unterminated_string_raises():
    """TC-29: Unterminated string literal raises SQLTranslationError."""
    with pytest.raises(SQLTranslationError, match="Unterminated"):
        sql_to_ra("SELECT * FROM R WHERE A = 'unclosed")


def test_missing_from_raises():
    """TC-30: Missing FROM clause raises SQLTranslationError."""
    with pytest.raises(SQLTranslationError):
        sql_to_ra("SELECT A")


def test_empty_query_raises():
    """TC-31: Empty string raises SQLTranslationError."""
    with pytest.raises(SQLTranslationError):
        sql_to_ra("")


def test_unrecognised_character_raises():
    """TC-32: Unrecognised character raises SQLTranslationError."""
    with pytest.raises(SQLTranslationError, match="Unrecognised"):
        sql_to_ra("SELECT @ FROM R")


# ── New predicate operators ───────────────────────────────────────────

def test_in_list():
    """IN (val1, val2, ...) translates to RA IN expression."""
    result = sql_to_ra("SELECT * FROM R WHERE A IN (1, 2, 3)")
    assert "IN" in result
    assert "(1, 2, 3)" in result


def test_not_in_list():
    """NOT IN translates to RA NOT IN expression."""
    result = sql_to_ra("SELECT * FROM R WHERE A NOT IN (1, 2)")
    assert "NOT IN" in result
    assert "(1, 2)" in result


def test_in_string_values():
    """IN with string values."""
    result = sql_to_ra("SELECT * FROM R WHERE name IN ('foo', 'bar')")
    assert "IN" in result
    assert "'foo'" in result and "'bar'" in result


def test_like():
    """LIKE translates to RA LIKE expression."""
    result = sql_to_ra("SELECT * FROM R WHERE name LIKE 'MEDIUM%'")
    assert "LIKE" in result
    assert "'MEDIUM%'" in result


def test_not_like():
    """NOT LIKE translates to RA NOT LIKE expression."""
    result = sql_to_ra("SELECT * FROM R WHERE name NOT LIKE 'MEDIUM%'")
    assert "NOT LIKE" in result


def test_between():
    """BETWEEN translates to RA BETWEEN expression."""
    result = sql_to_ra("SELECT * FROM R WHERE A BETWEEN 1 AND 10")
    assert "BETWEEN" in result
    assert "AND" in result


def test_modulo():
    """% (modulo) in WHERE condition."""
    result = sql_to_ra("SELECT * FROM R WHERE A%64 = 0")
    assert "%" in result


def test_date_literal():
    """DATE 'YYYY-MM-DD' treated as string literal."""
    result = sql_to_ra("SELECT * FROM R WHERE d < date '1995-03-15'")
    assert "'1995-03-15'" in result


def test_in_list_parseable():
    """Translated IN expression is parseable by the RA parser."""
    ra = sql_to_ra("SELECT * FROM R WHERE A IN (1, 2, 3)")
    ast = parse(ra)
    assert ast is not None


def test_not_like_parseable():
    """Translated NOT LIKE expression is parseable by the RA parser."""
    ra = sql_to_ra("SELECT * FROM R WHERE name NOT LIKE 'MEDIUM%'")
    ast = parse(ra)
    assert ast is not None


def test_between_parseable():
    """Translated BETWEEN expression is parseable by the RA parser."""
    ra = sql_to_ra("SELECT * FROM R WHERE A BETWEEN 1 AND 10")
    ast = parse(ra)
    assert ast is not None


def test_modulo_parseable():
    """Translated modulo expression is parseable by the RA parser."""
    ra = sql_to_ra("SELECT * FROM R WHERE A%64 = 0")
    ast = parse(ra)
    assert ast is not None


def test_date_parseable():
    """Translated DATE literal is parseable by the RA parser."""
    ra = sql_to_ra("SELECT * FROM R WHERE d < date '1995-03-15'")
    ast = parse(ra)
    assert ast is not None


def test_complex_tpch_like_query():
    """Complex TPC-H-style query with multiple new operators."""
    sql = """
        SELECT DISTINCT ps_partkey
        FROM partsupp, supplier, nation
        WHERE ps_suppkey = s_suppkey
          AND s_nationkey = n_nationkey
          AND n_name = 'GERMANY'
          AND ps_partkey%512 = 0
    """
    ra = sql_to_ra(sql)
    ast = parse(ra)
    assert ast is not None


def test_combined_in_and_not_like():
    """Query using both IN and NOT LIKE."""
    sql = """
        SELECT * FROM part
        WHERE p_brand <> 'Brand#45'
          AND p_type NOT LIKE 'MEDIUM POLISHED%'
          AND p_size IN (49, 14, 23)
    """
    ra = sql_to_ra(sql)
    ast = parse(ra)
    assert ast is not None


# ── Table alias tests ─────────────────────────────────────────────────

def test_bare_alias():
    """Table alias without AS keyword: FROM nation n1."""
    ra, aliases = sql_to_ra_with_aliases(
        "SELECT * FROM nation n1 WHERE n1.n_name = 'FRANCE'"
    )
    assert aliases == {'n1': 'nation'}
    assert 'n1' in ra


def test_as_alias():
    """Table alias with AS keyword: FROM nation AS n1."""
    ra, aliases = sql_to_ra_with_aliases(
        "SELECT * FROM nation AS n1 WHERE n1.n_name = 'FRANCE'"
    )
    assert aliases == {'n1': 'nation'}


def test_self_join_aliases():
    """Self-join: FROM nation n1, nation n2."""
    ra, aliases = sql_to_ra_with_aliases(
        "SELECT * FROM nation n1, nation n2 "
        "WHERE n1.n_name = 'FRANCE' AND n2.n_name = 'GERMANY'"
    )
    assert aliases == {'n1': 'nation', 'n2': 'nation'}
    assert '(n1 × n2)' in ra


def test_no_alias_no_map():
    """Non-aliased tables produce empty alias map."""
    ra, aliases = sql_to_ra_with_aliases(
        "SELECT * FROM customer, orders WHERE c_custkey = o_custkey"
    )
    assert aliases == {}


def test_mixed_alias_and_plain():
    """Mix of aliased and non-aliased tables."""
    ra, aliases = sql_to_ra_with_aliases(
        "SELECT * FROM supplier, nation n1 WHERE s_nationkey = n1.n_nationkey"
    )
    assert aliases == {'n1': 'nation'}
    assert '(supplier × n1)' in ra


def test_self_join_parseable():
    """Self-join RA expression is parseable."""
    ra, _ = sql_to_ra_with_aliases(
        "SELECT DISTINCT n1.n_name, n2.n_name "
        "FROM nation n1, nation n2 "
        "WHERE n1.n_name = 'FRANCE' AND n2.n_name = 'GERMANY'"
    )
    ast = parse(ra)
    assert ast is not None
