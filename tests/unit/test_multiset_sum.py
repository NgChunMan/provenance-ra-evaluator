"""
Each test corresponds to a mathematically verifiable property of the
operator under various semirings.

Test index
----------
TM-1  Tuples only in left appear in the output unchanged
TM-2  Tuples only in right appear in the output unchanged
TM-3  A tuple in both relations has annotation = semiring.add(left, right)
TM-4  Output schema matches both input schemas
TM-5  ⊎ with an empty left relation returns a copy of right
TM-6  ⊎ with an empty right relation returns a copy of left
TM-7  Relations with different schemas raise ValueError
TM-8  Relations with different semirings raise ValueError
TM-9  Original left relation is not mutated
TM-10 Original right relation is not mutated
TM-11 Counting semiring: annotations are summed numerically
TM-12 BoolFunc semiring: overlapping tuples combine via disjunction (∨)
TM-13 BoolFunc semiring: non-overlapping tuples are preserved
TM-14 Commutativity: R ⊎ S and S ⊎ R have the same support and annotations
TM-15 Identity: R ⊎ ∅ = R

Test data / schemas
-------------------
TM-1 through TM-10, TM-14, TM-15  — Boolean semiring

    left:
        Schema: (Name,)
        ┌───────┐
        │ Name  │
        ├───────┤
        │ Alice │
        │ Bob   │
        └───────┘

    right:
        Schema: (Name,)
        ┌───────┐
        │ Name  │
        ├───────┤
        │ Bob   │
        │ Carol │
        └───────┘

    Result of left ⊎ right:
        ┌───────┬─────────────────────────────────┐
        │ Name  │ Annotation                      │
        ├───────┼─────────────────────────────────┤
        │ Alice │ True               (left only)  │
        │ Bob   │ True ∨ True = True (both sides) │
        │ Carol │ True               (right only) │
        └───────┴─────────────────────────────────┘

TM-11  — Counting semiring (ℕ)

    left_nat:
        ┌───────┬────────────┐
        │ Name  │ Annotation │
        ├───────┼────────────┤
        │ Alice │ 3          │
        │ Bob   │ 2          │
        └───────┴────────────┘

    right_nat:
        ┌───────┬────────────┐
        │ Name  │ Annotation │
        ├───────┼────────────┤
        │ Bob   │ 5          │
        │ Carol │ 1          │
        └───────┴────────────┘

    Result: Alice→3, Bob→7, Carol→1

TM-12, TM-13  — BoolFunc semiring (ℬ[X])

    bf_left:
        ┌───────┬────────────┐
        │ Name  │ Annotation │
        ├───────┼────────────┤
        │ Alice │ t1         │
        │ Bob   │ t2         │
        └───────┴────────────┘

    bf_right:
        ┌───────┬────────────┐
        │ Name  │ Annotation │
        ├───────┼────────────┤
        │ Bob   │ t3         │
        │ Carol │ t4         │
        └───────┴────────────┘

    Result:
        ┌───────┬────────────┐
        │ Name  │ Annotation │
        ├───────┼────────────┤
        │ Alice │ t1         │
        │ Bob   │ t2 ∨ t3    │
        │ Carol │ t4         │
        └───────┴────────────┘
"""

import pytest

from src.semirings import BOOL_SR, BOOLFUNC_SR, NAT_SR, BoolFunc
from src.relation.k_relation import KRelation
from src.operators.multiset_sum import multiset_sum
from src.operators.cross_product import cross_product


# ──────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────

@pytest.fixture
def left():
    rel = KRelation(["Name"], BOOL_SR)
    rel.insert({"Name": "Alice"})
    rel.insert({"Name": "Bob"})
    return rel


@pytest.fixture
def right():
    rel = KRelation(["Name"], BOOL_SR)
    rel.insert({"Name": "Bob"})
    rel.insert({"Name": "Carol"})
    return rel


@pytest.fixture
def left_nat():
    rel = KRelation(["Name"], NAT_SR)
    rel._set_raw(("Alice",), 3)
    rel._set_raw(("Bob",), 2)
    return rel


@pytest.fixture
def right_nat():
    rel = KRelation(["Name"], NAT_SR)
    rel._set_raw(("Bob",), 5)
    rel._set_raw(("Carol",), 1)
    return rel


@pytest.fixture
def bf_left():
    rel = KRelation(["Name"], BOOLFUNC_SR)
    rel._set_raw(("Alice",), BoolFunc.var("t1"))
    rel._set_raw(("Bob",), BoolFunc.var("t2"))
    return rel


@pytest.fixture
def bf_right():
    rel = KRelation(["Name"], BOOLFUNC_SR)
    rel._set_raw(("Bob",), BoolFunc.var("t3"))
    rel._set_raw(("Carol",), BoolFunc.var("t4"))
    return rel


# ──────────────────────────────────────────────────────────────────────
# Boolean semiring tests
# ──────────────────────────────────────────────────────────────────────

def test_multiset_sum_left_only_tuple(left, right):
    """Tuples only in left appear in the output unchanged."""
    result = multiset_sum(left, right)
    assert result.annotation_of(Name="Alice") is True


def test_multiset_sum_right_only_tuple(left, right):
    """Tuples only in right appear in the output unchanged."""
    result = multiset_sum(left, right)
    assert result.annotation_of(Name="Carol") is True


def test_multiset_sum_overlapping_tuple_annotations_combined(left, right):
    """A tuple in both relations has annotation = semiring.add(left_ann, right_ann)."""
    result = multiset_sum(left, right)
    assert result.annotation_of(Name="Bob") is True


def test_multiset_sum_output_schema_unchanged(left, right):
    """Output schema matches both input schemas."""
    result = multiset_sum(left, right)
    assert result.schema == ["Name"]


def test_multiset_sum_support_size(left, right):
    """Support size is the union of both sides (Alice + Bob + Carol = 3)."""
    result = multiset_sum(left, right)
    assert result.support_size() == 3


def test_multiset_sum_with_empty_left(right):
    """⊎ with an empty left relation returns a copy of right."""
    empty = KRelation(["Name"], BOOL_SR)
    result = multiset_sum(empty, right)
    assert result.support_size() == right.support_size()
    for key, ann in right.items():
        assert result._data.get(key) == ann


def test_multiset_sum_with_empty_right(left):
    """⊎ with an empty right relation returns a copy of left."""
    empty = KRelation(["Name"], BOOL_SR)
    result = multiset_sum(left, empty)
    assert result.support_size() == left.support_size()
    for key, ann in left.items():
        assert result._data.get(key) == ann


def test_multiset_sum_mismatched_schemas():
    """Relations with different schemas raise ValueError."""
    r1 = KRelation(["A"], BOOL_SR)
    r2 = KRelation(["B"], BOOL_SR)
    r1.insert({"A": 1})
    r2.insert({"B": 2})
    with pytest.raises(ValueError, match="schema"):
        multiset_sum(r1, r2)


def test_multiset_sum_mismatched_semirings():
    """Relations with different semirings raise ValueError."""
    r1 = KRelation(["Name"], BOOL_SR)
    r2 = KRelation(["Name"], NAT_SR)
    r1.insert({"Name": "Alice"})
    r2.insert({"Name": "Alice"})
    with pytest.raises(ValueError):
        multiset_sum(r1, r2)


def test_multiset_sum_does_not_mutate_left(left, right):
    """Original left relation is not modified."""
    original_size = left.support_size()
    original_data = dict(left._data)
    multiset_sum(left, right)
    assert left.support_size() == original_size
    assert left._data == original_data


def test_multiset_sum_does_not_mutate_right(left, right):
    """Original right relation is not modified."""
    original_size = right.support_size()
    original_data = dict(right._data)
    multiset_sum(left, right)
    assert right.support_size() == original_size
    assert right._data == original_data


# ──────────────────────────────────────────────────────────────────────
# Counting semiring tests
# ──────────────────────────────────────────────────────────────────────

def test_multiset_sum_counting_overlap_adds(left_nat, right_nat):
    """Counting semiring: overlapping tuple annotations are summed (2 + 5 = 7)."""
    result = multiset_sum(left_nat, right_nat)
    assert result._data.get(("Bob",)) == 7


def test_multiset_sum_counting_exclusive_unchanged(left_nat, right_nat):
    """Counting semiring: exclusive tuples keep their annotation."""
    result = multiset_sum(left_nat, right_nat)
    assert result._data.get(("Alice",)) == 3
    assert result._data.get(("Carol",)) == 1


# ──────────────────────────────────────────────────────────────────────
# BoolFunc semiring tests
# ──────────────────────────────────────────────────────────────────────

def test_multiset_sum_boolfunc_overlap_disjoin(bf_left, bf_right):
    """BoolFunc: overlapping tuples combine via disjunction (t2 ∨ t3)."""
    result = multiset_sum(bf_left, bf_right)
    expected = BoolFunc.var("t2").disjoin(BoolFunc.var("t3"))
    assert result._data.get(("Bob",)) == expected


def test_multiset_sum_boolfunc_exclusive_preserved(bf_left, bf_right):
    """BoolFunc: non-overlapping tuples keep their original formula."""
    result = multiset_sum(bf_left, bf_right)
    assert result._data.get(("Alice",)) == BoolFunc.var("t1")
    assert result._data.get(("Carol",)) == BoolFunc.var("t4")


# ──────────────────────────────────────────────────────────────────────
# Algebraic properties
# ──────────────────────────────────────────────────────────────────────

def test_multiset_sum_commutativity(left, right):
    """R ⊎ S and S ⊎ R have the same support and annotations (𝔹 is idempotent)."""
    lr = multiset_sum(left, right)
    rl = multiset_sum(right, left)
    assert lr.support_size() == rl.support_size()
    for key, ann in lr.items():
        assert rl._data.get(key) == ann


def test_multiset_sum_identity_empty(left):
    """R ⊎ ∅ = R — empty relation is the neutral element."""
    empty = KRelation(["Name"], BOOL_SR)
    result = multiset_sum(left, empty)
    assert result.support_size() == left.support_size()
    for key, ann in left.items():
        assert result._data.get(key) == ann


def test_multiset_sum_distributivity_with_cross_product():
    """R × (S ⊎ T) = (R × S) ⊎ (R × T)."""
    r = KRelation(["X"], BOOL_SR)
    r.insert({"X": "a"})

    s = KRelation(["Y"], BOOL_SR)
    s.insert({"Y": 1})

    t = KRelation(["Y"], BOOL_SR)
    t.insert({"Y": 2})
    t.insert({"Y": 3})

    # left side: R × (S ⊎ T)
    lhs = cross_product(r, multiset_sum(s, t))

    # right side: (R × S) ⊎ (R × T)
    rhs = multiset_sum(cross_product(r, s), cross_product(r, t))

    assert lhs.support_size() == rhs.support_size()
    for key, ann in lhs.items():
        assert rhs._data.get(key) == ann
