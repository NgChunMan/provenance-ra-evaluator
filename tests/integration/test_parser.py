"""
Integration tests for the parser + evaluator pipeline.

Verifies that expression strings are tokenised and parsed into the
correct expression tree nodes, and that the Evaluator produces the
expected results for single- and multi-operator queries.

Test index
----------
TC-1   Selection expression is tokenised into a Select node
TC-2   Cross product expression is tokenised into a Cross node
TC-3   Nested expression produces the correct operator tree structure
TC-4   Evaluator evaluates a parsed selection against in-memory tables
TC-5   Evaluator evaluates a parsed projection and returns the correct schema
TC-6   Cross product of two relations parses all three node types
TC-7   Union of two relations parses into a Union node
TC-8   Selection with AND condition: σ[A == 1 /\\ B == 'x'](R)
TC-9   Selection with OR condition: σ[A == 1 \\/ A == 2](R)
TC-10  Selection with NOT condition: σ[~(A == 1)](R)
TC-11  Projection followed by dedup: δ(π[A](R))
TC-12  Selection on cross product: σ[A == 1](R × S)
TC-13  Full pipeline: δ(π[A](σ[A >= 1](R × S)))
TC-14  Union then projection: π[A](R ∪ R)
TC-15  Selection with string comparison: σ[B == 'x'](R)
TC-16  Selection with greater-than: σ[A > 1](R)
TC-17  Selection with Attr-Attr comparison: σ[A == C](R × S)

Test data / schemas
-------------------
TC-1, TC-3  — parse only (no tables loaded)
    Expression: σ[A == 1](R) and δ(π[A](σ[A == 1](R)))

TC-2  — parse only (no tables loaded)
    Expression: R × S

TC-4 to TC-17  — Boolean semiring
    R, schema: (A, B)
    ┌───┬───┬────────────┐
    │ A │ B │ Annotation │
    ├───┼───┼────────────┤
    │ 1 │ x │ True       │
    │ 2 │ y │ True       │
    │ 1 │ z │ True       │
    └───┴───┴────────────┘

    S, schema: (C,)
    ┌───┬────────────┐
    │ C │ Annotation │
    ├───┼────────────┤
    │ x │ True       │
    │ y │ True       │
    └───┴────────────┘

    TC-4   σ[A == 1](R)  →  expected rows: {(1, 'x'), (1, 'z')}
    TC-5   π[B](R)       →  expected schema: ['B'], rows: {('x',), ('y',), ('z',)}
    TC-6   R × S          →  6 rows (3 × 2)
    TC-7   R ∪ R          →  same support as R (Boolean: True + True = True)
    TC-8   σ[A == 1 /\\ B == 'x'](R)  →  {(1, 'x')}
    TC-9   σ[A == 1 \\/ A == 2](R)    →  all 3 rows
    TC-10  σ[~(A == 1)](R)            →  {(2, 'y')}
    TC-11  δ(π[A](R))                 →  {(1,), (2,)}
    TC-12  σ[A == 1](R × S)           →  {(1,'x','x'), (1,'x','y'), (1,'z','x'), (1,'z','y')}
    TC-13  δ(π[A](σ[A >= 1](R × S))) →  {(1,), (2,)}
    TC-14  π[A](R ∪ R)               →  {(1,), (2,)}
    TC-15  σ[B == 'x'](R)            →  {(1, 'x')}
    TC-16  σ[A > 1](R)               →  {(2, 'y')}
    TC-17  σ[A == C](R × S)          →  cross rows where A value matches C value
"""

import pytest

from src.parser import (
    parse,
    Select, Project, Cross, Dedup, Table,
)
from src.evaluator import Evaluator, UnsupportedOperatorError
from src.semirings import BOOL_SR
from src.relation.k_relation import KRelation


# ── Fixtures ───────────────────────────────────────────────────────────

@pytest.fixture
def tables():
    R = KRelation(["A", "B"], BOOL_SR)
    R.insert({"A": 1, "B": "x"})
    R.insert({"A": 2, "B": "y"})
    R.insert({"A": 1, "B": "z"})

    S = KRelation(["C"], BOOL_SR)
    S.insert({"C": "x"})
    S.insert({"C": "y"})
    return {"R": R, "S": S}


@pytest.fixture
def ev(tables):
    return Evaluator(tables, BOOL_SR)


# ── Parse-tree tests ──────────────────────────────────────────────────

def test_parser_tokenises_selection_expression():
    """TC-1: A selection expression is tokenised without error."""
    tree = parse("σ[A == 1](R)")
    assert isinstance(tree, Select)
    assert isinstance(tree.rel, Table)
    assert tree.rel.name == "R"


def test_parser_tokenises_cross_product_expression():
    """TC-2: A cross product expression is tokenised without error."""
    tree = parse("R × S")
    assert isinstance(tree, Cross)
    assert isinstance(tree.lhs, Table)
    assert isinstance(tree.rhs, Table)


def test_parser_builds_correct_tree_for_nested_expression():
    """TC-3: A nested expression produces the correct operator tree structure."""
    tree = parse("δ(π[A](σ[A == 1](R)))")
    assert isinstance(tree, Dedup)
    assert isinstance(tree.rel, Project)
    assert isinstance(tree.rel.rel, Select)
    assert isinstance(tree.rel.rel.rel, Table)


# ── Evaluator tests (single operator) ────────────────────────────────

def test_parser_eval_selection(ev):
    """TC-4: Parsing and evaluating a selection expression produces the right rows."""
    result = ev.evaluate(parse("σ[A == 1](R)"))
    assert set(result._data.keys()) == {(1, "x"), (1, "z")}


def test_parser_eval_projection(ev):
    """TC-5: Parsing and evaluating a projection expression produces the right schema."""
    result = ev.evaluate(parse("π[B](R)"))
    assert result.schema == ["B"]
    assert set(result._data.keys()) == {("x",), ("y",), ("z",)}


def test_parser_eval_cross_product(ev):
    """TC-6: Cross product of two relations produces the cartesian product."""
    result = ev.evaluate(parse("R × S"))
    assert result.support_size() == 6  # 3 × 2


def test_parser_eval_union(ev):
    """TC-7: Union of a relation with itself produces the same support."""
    result = ev.evaluate(parse("R ∪ R"))
    assert set(result._data.keys()) == {(1, "x"), (2, "y"), (1, "z")}


# ── Compound condition tests ─────────────────────────────────────────

def test_parser_eval_selection_and_condition(ev):
    """TC-8: Selection with AND condition keeps only rows satisfying both."""
    result = ev.evaluate(parse("σ[A == 1 /\\ B == 'x'](R)"))
    assert set(result._data.keys()) == {(1, "x")}


def test_parser_eval_selection_or_condition(ev):
    """TC-9: Selection with OR condition keeps rows satisfying either."""
    result = ev.evaluate(parse("σ[A == 1 \\/ A == 2](R)"))
    assert result.support_size() == 3


def test_parser_eval_selection_not_condition(ev):
    """TC-10: Selection with NOT condition negates the inner predicate."""
    result = ev.evaluate(parse("σ[~(A == 1)](R)"))
    assert set(result._data.keys()) == {(2, "y")}


# ── Multi-operator pipeline tests ────────────────────────────────────

def test_parser_eval_projection_then_dedup(ev):
    """TC-11: δ(π[A](R)) deduplicates projected values."""
    result = ev.evaluate(parse("δ(π[A](R))"))
    assert set(result._data.keys()) == {(1,), (2,)}


def test_parser_eval_selection_on_cross_product(ev):
    """TC-12: σ[A == 1](R × S) selects matching rows from cross product."""
    result = ev.evaluate(parse("σ[A == 1](R × S)"))
    assert result.support_size() == 4  # 2 rows with A=1 × 2 rows in S
    for key in result._data:
        assert key[0] == 1


def test_parser_eval_full_pipeline(ev):
    """TC-13: δ(π[A](σ[A >= 1](R × S))) — full nested pipeline."""
    result = ev.evaluate(parse("δ(π[A](σ[A >= 1](R × S)))"))
    assert set(result._data.keys()) == {(1,), (2,)}


def test_parser_eval_union_then_projection(ev):
    """TC-14: π[A](R ∪ R) — union followed by projection."""
    result = ev.evaluate(parse("π[A](R ∪ R)"))
    assert set(result._data.keys()) == {(1,), (2,)}


# ── Comparison operator variety ──────────────────────────────────────

def test_parser_eval_string_comparison(ev):
    """TC-15: Selection with string literal comparison."""
    result = ev.evaluate(parse("σ[B == 'x'](R)"))
    assert set(result._data.keys()) == {(1, "x")}


def test_parser_eval_greater_than(ev):
    """TC-16: Selection with > operator."""
    result = ev.evaluate(parse("σ[A > 1](R)"))
    assert set(result._data.keys()) == {(2, "y")}


def test_parser_eval_attr_attr_comparison(ev):
    """TC-17: Attr-Attr comparison across cross product columns."""
    # R(A,B) × S(C) → σ[B == C](...) keeps rows where B value = C value
    result = ev.evaluate(parse("σ[B == C](R × S)"))
    # (1,'x','x') and (2,'y','y') match; (1,'z',*) has no match
    assert result.support_size() == 2
    for key in result._data:
        assert key[1] == key[2]  # B == C


# ── UnsupportedOperatorError tests ───────────────────────────────────

@pytest.mark.parametrize("ra_expr,expected_symbol,expected_name", [
    ("ρ(A, B)",              "ρ",  "rename"),
    ("R ÷ S",                "÷",  "division"),
    ("R ⨝[A == C] S",        "⨝",  "inner join"),
    ("R ⟕[A == C] S",        "⟕",  "left outer join"),
    ("R ⊳[A == C] S",        "⊳",  "anti join"),
    ("R ∩ S",                "∩",  "intersection"),
    ("R - S",                "-",  "set difference"),
])
def test_unsupported_operator_raises(ev, ra_expr, expected_symbol, expected_name):
    """TC-18: Evaluating an unsupported operator raises UnsupportedOperatorError
    with the correct symbol and operator_name attributes."""
    with pytest.raises(UnsupportedOperatorError) as exc_info:
        ev.evaluate(parse(ra_expr))
    err = exc_info.value
    assert err.symbol == expected_symbol
    assert err.operator_name == expected_name


def test_unsupported_operator_is_not_implemented_error(ev):
    """TC-19: UnsupportedOperatorError is a subclass of NotImplementedError."""
    with pytest.raises(NotImplementedError):
        ev.evaluate(parse("R ÷ S"))
