"""
Each test corresponds to a mathematically verifiable property of the
operator under various semirings.

Test index
----------
TP-1  Output schema is correctly set to the projected attributes
TP-2  Multiple attributes maintain their requested order
TP-3  Colliding rows merge via semiring.add() (Boolean: True ∨ True = True)
TP-4  Non-colliding rows all appear in the result
TP-5  Annotations unchanged when no collisions occur
TP-6  Projecting onto all attributes is the identity relation
TP-7  Invalid attribute raises ValueError
TP-8  Empty input relation produces empty output
TP-9  Original relation is not mutated by projection
TP-10 All rows collapsing to the exact same key merge into one
TP-11 BoolFunc: colliding annotations combine by disjunction (∨)
TP-12 BoolFunc: non-colliding rows preserve their formula
TP-13 BoolFunc: schema updated correctly
TP-14 BoolFunc: input relation remains unmodified
TP-15 Idempotence: π_A(π_A(R)) = π_A(R)
TP-16 Composition: π_A(π_{A∪B}(R)) = π_A(R)

Test data / schemas
-------------------
TP-1, TP-3, TP-6, TP-10, TP-15  — collision_relation (Boolean semiring)
    Schema: (Name, Dept)
        ┌───────┬──────┐
        │ Name  │ Dept │
        ├───────┼──────┤
        │ Alice │ Eng  │
        │ Alice │ HR   │
        │ Bob   │ Eng  │
        └───────┴──────┘

    When projecting to [Name], Alice's two rows merge to one annotation:
        ┌───────┐
        │ Name  │
        ├───────┤
        │ Alice │  (True ∨ True = True)
        │ Bob   │
        └───────┘

TP-2, TP-4, TP-5  — no_collision_relation (Boolean semiring)
    Schema: (Name, Dept, Salary)
        ┌───────┬──────┬────────┐
        │ Name  │ Dept │ Salary │
        ├───────┼──────┼────────┤
        │ Alice │ Eng  │   90   │
        │ Bob   │ HR   │   60   │
        └───────┴──────┴────────┘

TP-11, TP-12, TP-13, TP-14  — boolfunc_relation (BoolFunc semiring)
    Schema: (Name, Dept, Salary)
        ┌───────┬──────┬────────┬────────────────────┐
        │ Name  │ Dept │ Salary │ Annotation         │
        ├───────┼──────┼────────┼────────────────────┤
        │ Alice │ Eng  │   90   │ t1                 │
        │ Alice │ HR   │   80   │ t2                 │
        │ Bob   │ Eng  │   70   │ t3                 │
        └───────┴──────┴────────┴────────────────────┘

    When projecting to [Name], Alice's two formulas merge via disjunction:
        ┌───────┬──────────────────┐
        │ Name  │ Annotation       │
        ├───────┼──────────────────┤
        │ Alice │ t1 ∨ t2          │
        │ Bob   │ t3               │
        └───────┴──────────────────┘
"""

import pytest

from src.semirings import BOOL_SR, BOOLFUNC_SR, BoolFunc
from src.relation.k_relation import KRelation
from src.operators.projection import projection


# ──────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────

@pytest.fixture
def collision_relation():
    """Boolean relation where projecting onto Name causes collisions."""
    rel = KRelation(["Name", "Dept"], BOOL_SR)
    rel.insert({"Name": "Alice", "Dept": "Eng"})
    rel.insert({"Name": "Alice", "Dept": "HR"})
    rel.insert({"Name": "Bob", "Dept": "Eng"})
    return rel


@pytest.fixture
def no_collision_relation():
    """Boolean relation with distinct rows under all projections."""
    rel = KRelation(["Name", "Dept", "Salary"], BOOL_SR)
    rel.insert({"Name": "Alice", "Dept": "Eng", "Salary": 90})
    rel.insert({"Name": "Bob", "Dept": "HR", "Salary": 60})
    return rel


@pytest.fixture
def boolfunc_relation():
    """BoolFunc relation with provenance-annotated tuples."""
    rel = KRelation(["Name", "Dept", "Salary"], BOOLFUNC_SR)
    rel._set_raw(("Alice", "Eng", 90), BoolFunc.var("t1"))
    rel._set_raw(("Alice", "HR", 80), BoolFunc.var("t2"))
    rel._set_raw(("Bob", "Eng", 70), BoolFunc.var("t3"))
    return rel


# ──────────────────────────────────────────────────────────────────────
# Boolean semiring tests
# ──────────────────────────────────────────────────────────────────────

def test_projection_output_schema_is_correct(collision_relation):
    """Result schema equals the requested attributes, in order."""
    result = projection(collision_relation, ["Name"])
    assert result.schema == ["Name"]


def test_projection_multiple_attributes_schema_order(no_collision_relation):
    """Schema respects the requested attribute order even when reversed."""
    result = projection(no_collision_relation, ["Salary", "Name"])
    assert result.schema == ["Salary", "Name"]


def test_projection_colliding_rows_are_merged(collision_relation):
    """Two rows projecting to the same key collapse into one (True ∨ True = True)."""
    result = projection(collision_relation, ["Name"])
    assert result.support_size() == 2
    assert result.annotation_of(Name="Alice") is True
    assert result.annotation_of(Name="Bob") is True


def test_projection_no_collision_all_rows_kept(no_collision_relation):
    """When no two input rows collide, every row appears in the result."""
    result = projection(no_collision_relation, ["Name", "Dept"])
    assert result.support_size() == 2


def test_projection_annotation_unchanged_when_no_collision(no_collision_relation):
    """Annotations of non-colliding rows survive unchanged (True stays True)."""
    result = projection(no_collision_relation, ["Name"])
    assert result.annotation_of(Name="Alice") is True
    assert result.annotation_of(Name="Bob") is True


def test_projection_full_schema_is_identity(no_collision_relation):
    """Projecting onto all attributes preserves the full relation."""
    attrs = no_collision_relation.schema[:]
    result = projection(no_collision_relation, attrs)
    assert result.support_size() == no_collision_relation.support_size()
    for key, ann in no_collision_relation.items():
        row = dict(zip(no_collision_relation.schema, key))
        assert result.annotation_of(**row) == ann


def test_projection_invalid_attribute_raises(collision_relation):
    """Requesting a non-existent attribute raises ValueError."""
    with pytest.raises(ValueError, match="nonexistent"):
        projection(collision_relation, ["Name", "nonexistent"])


def test_projection_empty_input():
    """Projecting an empty relation returns an empty relation."""
    rel = KRelation(["Name", "Dept"], BOOL_SR)
    result = projection(rel, ["Name"])
    assert result.support_size() == 0
    assert result.schema == ["Name"]


def test_projection_does_not_mutate_input(collision_relation):
    """The original relation is not modified by projection."""
    original_size = collision_relation.support_size()
    projection(collision_relation, ["Name"])
    assert collision_relation.support_size() == original_size
    assert collision_relation.schema == ["Name", "Dept"]


def test_projection_single_attribute_all_same():
    """All rows projecting to the same key collapse into one."""
    rel = KRelation(["X", "Y"], BOOL_SR)
    rel.insert({"X": "a", "Y": 1})
    rel.insert({"X": "a", "Y": 2})
    rel.insert({"X": "a", "Y": 3})
    result = projection(rel, ["X"])
    assert result.support_size() == 1
    assert result.annotation_of(X="a") is True


# ──────────────────────────────────────────────────────────────────────
# BoolFunc semiring tests — provenance accumulation
# ──────────────────────────────────────────────────────────────────────

def test_projection_boolfunc_collision_disjoin(boolfunc_relation):
    """Colliding BoolFunc annotations are combined by disjunction (∨)."""
    result = projection(boolfunc_relation, ["Name"])
    # Alice maps from t1 and t2 → t1 ∨ t2
    expected_alice = BoolFunc.var("t1").disjoin(BoolFunc.var("t2"))
    assert result._data[("Alice",)] == expected_alice


def test_projection_boolfunc_no_collision_preserved(boolfunc_relation):
    """Non-colliding BoolFunc rows keep their original formula."""
    result = projection(boolfunc_relation, ["Name"])
    # Bob has no collision
    assert result._data[("Bob",)] == BoolFunc.var("t3")


def test_projection_boolfunc_schema_correct(boolfunc_relation):
    """Schema is updated correctly after BoolFunc projection."""
    result = projection(boolfunc_relation, ["Name", "Dept"])
    assert result.schema == ["Name", "Dept"]


def test_projection_boolfunc_does_not_mutate_input(boolfunc_relation):
    """Input BoolFunc relation is not modified."""
    original_ann = boolfunc_relation._data[("Alice", "Eng", 90)]
    projection(boolfunc_relation, ["Name"])
    assert boolfunc_relation._data[("Alice", "Eng", 90)] == original_ann


# ──────────────────────────────────────────────────────────────────────
# Algebraic properties
# ──────────────────────────────────────────────────────────────────────

def test_projection_idempotent(collision_relation):
    """π_A(π_A(R)) = π_A(R) — projecting twice gives the same support."""
    once  = projection(collision_relation, ["Name"])
    twice = projection(once, ["Name"])
    assert once.support_size() == twice.support_size()
    for key, ann in once.items():
        assert twice._data.get(key) == ann


def test_projection_composition(no_collision_relation):
    """π_A(π_{A∪B}(R)) = π_A(R) — projecting to a subset commutes."""
    # Project onto {Name, Dept}, then onto {Name}
    intermediate = projection(no_collision_relation, ["Name", "Dept"])
    final = projection(intermediate, ["Name"])
    direct = projection(no_collision_relation, ["Name"])
    assert final.support_size() == direct.support_size()
    for key, ann in direct.items():
        assert final._data.get(key) == ann
