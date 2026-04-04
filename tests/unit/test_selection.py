"""
Each test corresponds to a mathematically verifiable property of the
operator under various semirings.

Test index
----------
TS-1  Rows satisfying the predicate appear in the result
TS-2  Rows not satisfying the predicate are absent from the result
TS-3  Support size equals the number of rows passing the predicate
TS-4  Annotations of kept rows are identical to input (True stays True)
TS-5  When all rows satisfy the predicate, support unchanged
TS-6  When no rows satisfy the predicate, result is empty
TS-7  Applying selection to an empty relation returns empty
TS-8  Output schema is identical to input schema
TS-9  Original relation is not modified by selection
TS-10 Selection works with string equality predicates
TS-11 Selection works with compound AND predicates
TS-12 BoolFunc: annotations pass through selection unchanged
TS-13 BoolFunc: rows failing the predicate are not in the result
TS-14 BoolFunc: when no rows pass, result is empty
TS-15 BoolFunc: when all rows pass, all formulas are preserved
TS-16 Idempotence: σ_A(σ_A(R)) = σ_A(R)
TS-17 Composition: σ_A(σ_B(R)) = σ_{A ∧ B}(R)

Test data / schemas
-------------------
TS-1 through TS-11, TS-16, TS-17  — simple_relation (Boolean semiring)
    Schema: (Name, Dept, Salary)
        ┌───────┬──────┬────────┐
        │ Name  │ Dept │ Salary │
        ├───────┼──────┼────────┤
        │ Alice │ Eng  │    90  │
        │ Bob   │ HR   │    60  │
        │ Carol │ Eng  │    40  │
        └───────┴──────┴────────┘

    Predicates tested:
      • Salary > 50     → Alice (90), Bob (60)
      • Salary > 9999   → (empty)
      • Dept == "Eng"   → Alice, Carol
      • Dept == "HR"    → Bob
      • Dept == "Eng" AND Salary > 50  → Alice only

TS-12 through TS-15  — boolfunc_relation (BoolFunc semiring)
    Schema: (Name, Salary)
        ┌───────┬────────┬──────────────────┐
        │ Name  │ Salary │ Annotation       │
        ├───────┼────────┼──────────────────┤
        │ Alice │   90   │ t1               │
        │ Bob   │   60   │ t2 ∨ t3          │
        │ Carol │   40   │ t4               │
        └───────┴────────┴──────────────────┘

    Predicates tested:
      • Salary > 50     → Alice (t1), Bob (t2 ∨ t3)
      • Salary > 9999   → (empty)
      • True            → all three with formulas preserved
"""

import pytest

from src.semirings import BOOL_SR, BOOLFUNC_SR, BoolFunc
from src.relation.k_relation import KRelation
from src.operators.selection import selection


# ──────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────

@pytest.fixture
def simple_relation():
    """A small Boolean relation with three rows."""
    rel = KRelation(["Name", "Dept", "Salary"], BOOL_SR)
    rel.insert({"Name": "Alice", "Dept": "Eng", "Salary": 90})
    rel.insert({"Name": "Bob", "Dept": "HR", "Salary": 60})
    rel.insert({"Name": "Carol", "Dept": "Eng", "Salary": 40})
    return rel


@pytest.fixture
def boolfunc_relation():
    """A BoolFunc relation where each tuple has a provenance formula."""
    rel = KRelation(["Name", "Salary"], BOOLFUNC_SR)
    rel._set_raw(("Alice", 90), BoolFunc.var("t1"))
    rel._set_raw(("Bob", 60), BoolFunc.var("t2").disjoin(BoolFunc.var("t3")))
    rel._set_raw(("Carol", 40), BoolFunc.var("t4"))
    return rel


# ──────────────────────────────────────────────────────────────────────
# Boolean semiring tests
# ──────────────────────────────────────────────────────────────────────

def test_selection_matching_rows_are_kept(simple_relation):
    """Rows satisfying the predicate appear in the result."""
    result = selection(simple_relation, lambda r: r["Salary"] > 50)
    assert result.annotation_of(Name="Alice", Dept="Eng", Salary=90) is True
    assert result.annotation_of(Name="Bob",   Dept="HR",  Salary=60) is True


def test_selection_non_matching_rows_are_excluded(simple_relation):
    """Rows not satisfying the predicate are absent from the result."""
    result = selection(simple_relation, lambda r: r["Salary"] > 50)
    assert result.annotation_of(Name="Carol", Dept="Eng", Salary=40) is False


def test_selection_support_size_reflects_predicate(simple_relation):
    """Support size equals the number of rows passing the predicate."""
    result = selection(simple_relation, lambda r: r["Salary"] > 50)
    assert result.support_size() == 2


def test_selection_annotation_unchanged_for_passing_rows(simple_relation):
    """Annotations of kept rows are identical to the input (True stays True)."""
    result = selection(simple_relation, lambda r: r["Dept"] == "Eng")
    assert result.annotation_of(Name="Alice", Dept="Eng", Salary=90) is True
    assert result.annotation_of(Name="Carol", Dept="Eng", Salary=40) is True


def test_selection_all_rows_pass(simple_relation):
    """When all rows satisfy the predicate, the result has the same support."""
    result = selection(simple_relation, lambda r: True)
    assert result.support_size() == simple_relation.support_size()


def test_selection_no_rows_pass(simple_relation):
    """When no rows satisfy the predicate, the result is empty."""
    result = selection(simple_relation, lambda r: r["Salary"] > 9999)
    assert result.support_size() == 0


def test_selection_empty_input():
    """Applying selection to an empty relation returns an empty relation."""
    rel = KRelation(["Name"], BOOL_SR)
    result = selection(rel, lambda r: True)
    assert result.support_size() == 0


def test_selection_schema_preserved(simple_relation):
    """The output schema is identical to the input schema."""
    result = selection(simple_relation, lambda r: r["Salary"] > 50)
    assert result.schema == simple_relation.schema


def test_selection_does_not_mutate_input(simple_relation):
    """The original relation is not modified by selection."""
    original_size = simple_relation.support_size()
    selection(simple_relation, lambda r: r["Salary"] > 50)
    assert simple_relation.support_size() == original_size


def test_selection_string_predicate(simple_relation):
    """Selection works with string equality predicates."""
    result = selection(simple_relation, lambda r: r["Dept"] == "HR")
    assert result.support_size() == 1
    assert result.annotation_of(Name="Bob", Dept="HR", Salary=60) is True


def test_selection_compound_predicate(simple_relation):
    """Selection works with compound AND predicates."""
    result = selection(
        simple_relation,
        lambda r: r["Dept"] == "Eng" and r["Salary"] > 50,
    )
    assert result.support_size() == 1
    assert result.annotation_of(Name="Alice", Dept="Eng", Salary=90) is True
    assert result.annotation_of(Name="Carol", Dept="Eng", Salary=40) is False


# ──────────────────────────────────────────────────────────────────────
# BoolFunc semiring tests — provenance must be preserved
# ──────────────────────────────────────────────────────────────────────

def test_selection_boolfunc_annotation_preserved(boolfunc_relation):
    """BoolFunc annotations pass through selection unchanged."""
    result = selection(boolfunc_relation, lambda r: r["Salary"] > 50)
    assert result._data[("Alice", 90)] == BoolFunc.var("t1")
    assert result._data[("Bob", 60)] == BoolFunc.var("t2").disjoin(BoolFunc.var("t3"))


def test_selection_boolfunc_excluded_row_absent(boolfunc_relation):
    """BoolFunc rows failing the predicate are not in the result."""
    result = selection(boolfunc_relation, lambda r: r["Salary"] > 50)
    assert ("Carol", 40) not in result._data


def test_selection_boolfunc_no_rows_pass(boolfunc_relation):
    """BoolFunc: when no rows pass, result is empty."""
    result = selection(boolfunc_relation, lambda r: r["Salary"] > 9999)
    assert result.support_size() == 0


def test_selection_boolfunc_all_rows_pass(boolfunc_relation):
    """BoolFunc: when all rows pass, all formulas are preserved."""
    result = selection(boolfunc_relation, lambda r: True)
    assert result.support_size() == 3
    assert result._data[("Alice", 90)] == BoolFunc.var("t1")
    assert result._data[("Carol", 40)] == BoolFunc.var("t4")


# ──────────────────────────────────────────────────────────────────────
# Idempotence and composability
# ──────────────────────────────────────────────────────────────────────

def test_selection_idempotent(simple_relation):
    """Applying the same selection twice gives the same result as once."""
    pred = lambda r: r["Salary"] > 50
    once  = selection(simple_relation, pred)
    twice = selection(once, pred)
    assert once.support_size() == twice.support_size()
    for key, ann in once.items():
        assert twice._data.get(key) == ann


def test_selection_composition_is_intersection(simple_relation):
    """σ_A(σ_B(R)) = σ_{A ∧ B}(R) — composing two selections is their AND."""
    composed = selection(
        selection(simple_relation, lambda r: r["Dept"] == "Eng"),
        lambda r: r["Salary"] > 50,
    )
    direct = selection(
        simple_relation,
        lambda r: r["Dept"] == "Eng" and r["Salary"] > 50,
    )
    assert composed.support_size() == direct.support_size()
    for key, ann in composed.items():
        assert direct._data.get(key) == ann
