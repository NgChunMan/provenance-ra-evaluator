"""
Each test corresponds to a mathematically verifiable property of the
operator under various semirings.

Test index
----------
TC-1  Output schema is left.schema + right.schema
TC-2  Output support size equals |supp(left)| × |supp(right)|
TC-3  Each output annotation equals semiring.mul(left_ann, right_ann)
TC-4  Cross product with an empty left relation yields an empty result
TC-5  Cross product with an empty right relation yields an empty result
TC-6  Relations with different semirings raise ValueError
TC-7  Original left relation is not mutated
TC-8  Original right relation is not mutated
TC-9  Single-row left × single-row right produces exactly one output tuple
TC-10 BoolFunc: annotation is conjoin (∧) of the two input formulas
TC-11 BoolFunc: non-colliding pairs keep independent formulas
TC-12 Interaction with selection: σ_{A∧B}(R×S) = σ_A(R) × σ_B(S)

Test data / schemas
-------------------
TC-1 through TC-9, TC-12  — Boolean semiring

    left:
        Schema: (A,)
        ┌───┐
        │ A │
        ├───┤
        │ 1 │
        │ 2 │
        └───┘

    right:
        Schema: (B,)
        ┌───┐
        │ B │
        ├───┤
        │ x │
        │ y │
        └───┘

    Result of left × right (Schema: (A, B)):
        ┌───┬───┐
        │ A │ B │
        ├───┼───┤
        │ 1 │ x │  → True ∧ True = True
        │ 1 │ y │  → True ∧ True = True
        │ 2 │ x │  → True ∧ True = True
        │ 2 │ y │  → True ∧ True = True
        └───┴───┘

TC-10, TC-11  — BoolFunc semiring

    bf_left:
        Schema: (Name,)
        ┌───────┬────────────┐
        │ Name  │ Annotation │
        ├───────┼────────────┤
        │ Alice │ t1         │
        │ Bob   │ t2         │
        └───────┴────────────┘

    bf_right:
        Schema: (Dept,)
        ┌──────┬────────────┐
        │ Dept │ Annotation │
        ├──────┼────────────┤
        │ Eng  │ t3         │
        └──────┴────────────┘

    Result of bf_left × bf_right (Schema: (Name, Dept)):
        ┌───────┬──────┬────────────┐
        │ Name  │ Dept │ Annotation │
        ├───────┼──────┼────────────┤
        │ Alice │ Eng  │ t1 ∧ t3    │
        │ Bob   │ Eng  │ t2 ∧ t3    │
        └───────┴──────┴────────────┘
"""

import pytest

from src.semirings import BOOL_SR, BOOLFUNC_SR, NAT_SR, BoolFunc
from src.relation.k_relation import KRelation
from src.operators.cross_product import cross_product
from src.operators.selection import selection


# ──────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────

@pytest.fixture
def left():
    rel = KRelation(["A"], BOOL_SR)
    rel.insert({"A": 1})
    rel.insert({"A": 2})
    return rel


@pytest.fixture
def right():
    rel = KRelation(["B"], BOOL_SR)
    rel.insert({"B": "x"})
    rel.insert({"B": "y"})
    return rel


@pytest.fixture
def bf_left():
    rel = KRelation(["Name"], BOOLFUNC_SR)
    rel._set_raw(("Alice",), BoolFunc.var("t1"))
    rel._set_raw(("Bob",),   BoolFunc.var("t2"))
    return rel


@pytest.fixture
def bf_right():
    rel = KRelation(["Dept"], BOOLFUNC_SR)
    rel._set_raw(("Eng",), BoolFunc.var("t3"))
    return rel


# ──────────────────────────────────────────────────────────────────────
# Boolean semiring tests
# ──────────────────────────────────────────────────────────────────────

def test_cross_product_output_schema(left, right):
    """Output schema is left.schema + right.schema."""
    result = cross_product(left, right)
    assert result.schema == ["A", "B"]


def test_cross_product_row_count(left, right):
    """Output support size equals |supp(left)| × |supp(right)|."""
    result = cross_product(left, right)
    assert result.support_size() == 4


def test_cross_product_annotation_is_mul(left, right):
    """Each output annotation equals semiring.mul(left_ann, right_ann)."""
    result = cross_product(left, right)
    # Boolean: True ∧ True = True for every pair
    assert result.annotation_of(A=1, B="x") is True
    assert result.annotation_of(A=1, B="y") is True
    assert result.annotation_of(A=2, B="x") is True
    assert result.annotation_of(A=2, B="y") is True


def test_cross_product_empty_left(right):
    """Cross product with an empty left relation yields an empty result."""
    empty = KRelation(["A"], BOOL_SR)
    result = cross_product(empty, right)
    assert result.support_size() == 0


def test_cross_product_empty_right(left):
    """Cross product with an empty right relation yields an empty result."""
    empty = KRelation(["B"], BOOL_SR)
    result = cross_product(left, empty)
    assert result.support_size() == 0


def test_cross_product_mismatched_semirings():
    """Relations with different semirings raise ValueError."""
    rel_bool = KRelation(["A"], BOOL_SR)
    rel_bool.insert({"A": 1})
    rel_nat = KRelation(["B"], NAT_SR)
    rel_nat.insert({"B": 2})
    with pytest.raises(ValueError):
        cross_product(rel_bool, rel_nat)


def test_cross_product_does_not_mutate_left(left, right):
    """Original left relation is not modified."""
    original_size = left.support_size()
    original_schema = left.schema[:]
    cross_product(left, right)
    assert left.support_size() == original_size
    assert left.schema == original_schema


def test_cross_product_does_not_mutate_right(left, right):
    """Original right relation is not modified."""
    original_size = right.support_size()
    original_schema = right.schema[:]
    cross_product(left, right)
    assert right.support_size() == original_size
    assert right.schema == original_schema


def test_cross_product_single_row_each():
    """Single-row left × single-row right produces exactly one output tuple."""
    r1 = KRelation(["X"], BOOL_SR)
    r1.insert({"X": "a"})
    r2 = KRelation(["Y"], BOOL_SR)
    r2.insert({"Y": "b"})
    result = cross_product(r1, r2)
    assert result.support_size() == 1
    assert result.annotation_of(X="a", Y="b") is True


# ──────────────────────────────────────────────────────────────────────
# BoolFunc semiring tests
# ──────────────────────────────────────────────────────────────────────

def test_cross_product_boolfunc_annotation_is_conjoin(bf_left, bf_right):
    """BoolFunc: annotation is conjoin (∧) of the two input formulas."""
    result = cross_product(bf_left, bf_right)
    expected_alice = BoolFunc.var("t1").conjoin(BoolFunc.var("t3"))
    assert result._data[("Alice", "Eng")] == expected_alice


def test_cross_product_boolfunc_independent_pairs(bf_left, bf_right):
    """BoolFunc: distinct pairs carry independent conjunctions."""
    result = cross_product(bf_left, bf_right)
    expected_bob = BoolFunc.var("t2").conjoin(BoolFunc.var("t3"))
    assert result._data[("Bob", "Eng")] == expected_bob
    assert result.support_size() == 2


# ──────────────────────────────────────────────────────────────────────
# Algebraic properties
# ──────────────────────────────────────────────────────────────────────

def test_cross_product_interaction_with_selection(left, right):
    """σ_{A∧B}(R × S) = σ_A(R) × σ_B(S) when predicates are separated."""
    # σ on the cross product
    combined = cross_product(left, right)
    filtered_combined = selection(combined, lambda r: r["A"] == 1 and r["B"] == "x")

    # σ on each side first, then cross product
    filtered_left = selection(left, lambda r: r["A"] == 1)
    filtered_right = selection(right, lambda r: r["B"] == "x")
    product_of_filtered = cross_product(filtered_left, filtered_right)

    assert filtered_combined.support_size() == product_of_filtered.support_size()
    for key, ann in filtered_combined.items():
        assert product_of_filtered._data.get(key) == ann
