"""
End-to-end integration tests for multi-operator query pipelines.

Each test constructs a KRelation, runs a sequence of operators that
translates a SQL-like query, and asserts the final result is correct.

Test index
----------
TC-1   Cross product → selection → projection → deduplication (𝔹)
       (models: SELECT DISTINCT R.Name FROM R, S WHERE R.Dept = S.Dept)
TC-2   Multiset sum → deduplication (𝔹)
       (models: δ(R ⊎ R))
TC-3   Selection → projection (𝔹)
       (models: π[Name](σ[Dept = Eng](R)))
TC-4   Cross product → projection (𝔹)
       (models: π[Name, Location](R × S))
TC-5   Union → selection → projection (𝔹)
       (models: π[Name](σ[Dept = Eng](R ⊎ R)))
TC-6   Dedup idempotence in pipeline (𝔹)
       (δ(δ(π[Name](R))) == δ(π[Name](R)))
TC-7   Full pipeline with ℕ[X]: × → σ → π → δ(HOW_PROVENANCE)
       provenance polynomials survive deduplication
TC-8   Full pipeline with 𝔹[X]: × → σ → π → δ(HOW_PROVENANCE)
       provenance formulas survive deduplication
TC-9   Full pipeline with ℕ[X]: × → σ → π → δ(EXISTENCE)
       polynomials collapse to Polynomial.one()
TC-10  Full pipeline with ℕ: ⊎ → δ(HOW_PROVENANCE)
       counting multiplicities survive deduplication
TC-11  Full pipeline with 𝔹[X]: ⊎ → π → δ(EXISTENCE)
       formulas collapse to BoolFunc.true_()

Test data / schemas
-------------------
TC-1 to TC-6 — Boolean semiring (𝔹)

    R (Employees), schema: (Name, Dept)
    ┌───────┬──────┬────────────┐
    │ Name  │ Dept │ Annotation │
    ├───────┼──────┼────────────┤
    │ Alice │ Eng  │ True       │
    │ Alice │ HR   │ True       │
    │ Bob   │ Eng  │ True       │
    └───────┴──────┴────────────┘

    S (Departments), schema: (Dept, Location)
    ┌──────┬──────────┬────────────┐
    │ Dept │ Location │ Annotation │
    ├──────┼──────────┼────────────┤
    │ Eng  │ London   │ True       │
    │ HR   │ Paris    │ True       │
    └──────┴──────────┴────────────┘

TC-7, TC-9 — Polynomial semiring (ℕ[X])

    R_poly (Employees), schema: (Name, DeptID)
    ┌───────┬────────┬────────────┐
    │ Name  │ DeptID │ Annotation │
    ├───────┼────────┼────────────┤
    │ Alice │   1    │ t1         │
    │ Alice │   2    │ t2         │
    │ Bob   │   1    │ t3         │
    └───────┴────────┴────────────┘

    S_poly (Departments), schema: (ID, Location)
    ┌────┬──────────┬────────────┐
    │ ID │ Location │ Annotation │
    ├────┼──────────┼────────────┤
    │ 1  │ London   │ s1         │
    │ 2  │ Paris    │ s2         │
    └────┴──────────┴────────────┘

TC-8, TC-11 — BoolFunc semiring (𝔹[X])

    R_bf (Employees), schema: (Name, DeptID)
    ┌───────┬────────┬────────────┐
    │ Name  │ DeptID │ Annotation │
    ├───────┼────────┼────────────┤
    │ Alice │   1    │ x1         │
    │ Alice │   2    │ x2         │
    │ Bob   │   1    │ x3         │
    └───────┴────────┴────────────┘

    S_bf (Departments), schema: (ID, Location)
    ┌────┬──────────┬────────────┐
    │ ID │ Location │ Annotation │
    ├────┼──────────┼────────────┤
    │ 1  │ London   │ y1         │
    │ 2  │ Paris    │ y2         │
    └────┴──────────┴────────────┘

TC-10 — Counting semiring (ℕ)

    R_nat, schema: (Name, Dept)
    ┌───────┬──────┬────────────┐
    │ Name  │ Dept │ Annotation │
    ├───────┼──────┼────────────┤
    │ Alice │ Eng  │ 3          │
    │ Alice │ HR   │ 2          │
    │ Bob   │ Eng  │ 5          │
    └───────┴──────┴────────────┘
"""

import pytest

from src.semirings import (
    BOOL_SR,
    NAT_SR,
    POLY_SR, Polynomial,
    BOOLFUNC_SR, BoolFunc,
)
from src.relation.k_relation import KRelation
from src.operators.selection import selection
from src.operators.projection import projection
from src.operators.cross_product import cross_product
from src.operators.multiset_sum import multiset_sum
from src.operators.deduplication import deduplication
from src.strategies import DedupStrategy


# ──────────────────────────────────────────────────────────────────────
# Fixtures — Boolean semiring
# ──────────────────────────────────────────────────────────────────────

@pytest.fixture
def R():
    """Employees table (𝔹)."""
    rel = KRelation(["Name", "Dept"], BOOL_SR)
    rel.insert({"Name": "Alice", "Dept": "Eng"})
    rel.insert({"Name": "Alice", "Dept": "HR"})
    rel.insert({"Name": "Bob", "Dept": "Eng"})
    return rel


@pytest.fixture
def S():
    """Departments table (𝔹)."""
    rel = KRelation(["Dept", "Location"], BOOL_SR)
    rel.insert({"Dept": "Eng", "Location": "London"})
    rel.insert({"Dept": "HR", "Location": "Paris"})
    return rel


# ──────────────────────────────────────────────────────────────────────
# Fixtures — Polynomial semiring
# ──────────────────────────────────────────────────────────────────────

@pytest.fixture
def R_poly():
    """Employees table (ℕ[X])."""
    t1 = Polynomial.from_var("t1")
    t2 = Polynomial.from_var("t2")
    t3 = Polynomial.from_var("t3")
    rel = KRelation(["Name", "DeptID"], POLY_SR)
    rel._set_raw(("Alice", 1), t1)
    rel._set_raw(("Alice", 2), t2)
    rel._set_raw(("Bob", 1), t3)
    return rel


@pytest.fixture
def S_poly():
    """Departments table (ℕ[X])."""
    s1 = Polynomial.from_var("s1")
    s2 = Polynomial.from_var("s2")
    rel = KRelation(["ID", "Location"], POLY_SR)
    rel._set_raw((1, "London"), s1)
    rel._set_raw((2, "Paris"), s2)
    return rel


# ──────────────────────────────────────────────────────────────────────
# Fixtures — BoolFunc semiring
# ──────────────────────────────────────────────────────────────────────

@pytest.fixture
def R_bf():
    """Employees table (𝔹[X])."""
    x1 = BoolFunc.var("x1")
    x2 = BoolFunc.var("x2")
    x3 = BoolFunc.var("x3")
    rel = KRelation(["Name", "DeptID"], BOOLFUNC_SR)
    rel._set_raw(("Alice", 1), x1)
    rel._set_raw(("Alice", 2), x2)
    rel._set_raw(("Bob", 1), x3)
    return rel


@pytest.fixture
def S_bf():
    """Departments table (𝔹[X])."""
    y1 = BoolFunc.var("y1")
    y2 = BoolFunc.var("y2")
    rel = KRelation(["ID", "Location"], BOOLFUNC_SR)
    rel._set_raw((1, "London"), y1)
    rel._set_raw((2, "Paris"), y2)
    return rel


# ──────────────────────────────────────────────────────────────────────
# Fixtures — Counting semiring
# ──────────────────────────────────────────────────────────────────────

@pytest.fixture
def R_nat():
    """Employees table (ℕ)."""
    rel = KRelation(["Name", "Dept"], NAT_SR)
    rel._set_raw(("Alice", "Eng"), 3)
    rel._set_raw(("Alice", "HR"), 2)
    rel._set_raw(("Bob", "Eng"), 5)
    return rel


# ──────────────────────────────────────────────────────────────────────
# Boolean pipeline tests (TC-1 to TC-6)
# ──────────────────────────────────────────────────────────────────────

def test_cross_then_selection_then_projection_then_dedup(R, S):
    """
    Full pipeline: SELECT DISTINCT R.Name FROM R, S WHERE R.Dept = S.Dept
    Translated to: δ( π[Name]( σ[Dept match]( R × S ) ) )

    Expected result: {Alice, Bob}
    """
    crossed = cross_product(R, S)
    # After cross: schema = [Name, Dept, Dept, Location]
    # Need to match Dept columns — use positional predicate
    schema = crossed.schema
    dept_l = schema.index("Dept")
    dept_r = dept_l + 1 + schema[dept_l + 1:].index("Dept")
    selected = selection(
        crossed,
        lambda row: row[schema[dept_l]] == row[schema[dept_r]],
    )
    projected = projection(selected, ["Name"])
    result = deduplication(projected, DedupStrategy.EXISTENCE)

    assert set(result._data.keys()) == {("Alice",), ("Bob",)}
    for ann in result._data.values():
        assert ann == BOOL_SR.one()


def test_cross_then_projection(R, S):
    """
    TC-4: π[Name, Location]( R × S )
    Projects two columns from the cartesian product.

    Expected: 4 distinct (Name, Location) pairs.
    """
    crossed = cross_product(R, S)
    result = projection(crossed, ["Name", "Location"])

    expected = {
        ("Alice", "London"),
        ("Alice", "Paris"),
        ("Bob", "London"),
        ("Bob", "Paris"),
    }
    assert set(result._data.keys()) == expected


def test_union_then_selection_then_projection(R):
    """
    TC-5: π[Name]( σ[Dept = Eng]( R ⊎ R ) )
    Union with self, filter, then project.

    In 𝔹: True + True = True, so the result is the same as without union.
    Expected: {Alice, Bob}
    """
    unioned = multiset_sum(R, R)
    selected = selection(unioned, lambda row: row["Dept"] == "Eng")
    result = projection(selected, ["Name"])

    assert set(result._data.keys()) == {("Alice",), ("Bob",)}


def test_dedup_idempotence_in_pipeline(R):
    """
    TC-6: δ(δ(π[Name](R))) == δ(π[Name](R))
    Applying dedup twice produces the same result as applying it once.
    """
    projected = projection(R, ["Name"])
    once = deduplication(projected, DedupStrategy.EXISTENCE)
    twice = deduplication(once, DedupStrategy.EXISTENCE)

    assert dict(once._data) == dict(twice._data)


# ──────────────────────────────────────────────────────────────────────
# Polynomial pipeline tests (TC-7, TC-9)
# ──────────────────────────────────────────────────────────────────────

def test_poly_full_pipeline_how_provenance(R_poly, S_poly):
    """
    TC-7: δ_HOW( π[Name]( σ[DeptID == ID]( R × S ) ) )

    After cross product, equi-select on DeptID == ID, and projection:
      Alice: t1·s1 + t2·s2  (Dept 1 join via t1·s1, Dept 2 join via t2·s2)
      Bob:   t3·s1  (Dept 1 join only)

    HOW_PROVENANCE preserves the full polynomial unchanged.
    """
    crossed = cross_product(R_poly, S_poly)
    selected = selection(
        crossed,
        lambda row: row["DeptID"] == row["ID"],
    )
    projected = projection(selected, ["Name"])
    result = deduplication(projected, DedupStrategy.HOW_PROVENANCE)

    t1 = Polynomial.from_var("t1")
    t2 = Polynomial.from_var("t2")
    t3 = Polynomial.from_var("t3")
    s1 = Polynomial.from_var("s1")
    s2 = Polynomial.from_var("s2")

    alice_expected = t1.multiply(s1).add(t2.multiply(s2))
    bob_expected = t3.multiply(s1)

    assert result._data.get(("Alice",)) == alice_expected
    assert result._data.get(("Bob",)) == bob_expected


def test_poly_full_pipeline_existence(R_poly, S_poly):
    """
    TC-9: δ( π[Name]( σ[DeptID == ID]( R × S ) ) )

    Same pipeline as TC-7 but with δ_EXISTENCE: all polynomials collapse
    to Polynomial.one().
    """
    crossed = cross_product(R_poly, S_poly)
    selected = selection(
        crossed,
        lambda row: row["DeptID"] == row["ID"],
    )
    projected = projection(selected, ["Name"])
    result = deduplication(projected, DedupStrategy.EXISTENCE)

    one = Polynomial.one()
    assert result._data.get(("Alice",)) == one
    assert result._data.get(("Bob",)) == one


# ──────────────────────────────────────────────────────────────────────
# BoolFunc pipeline tests (TC-8, TC-11)
# ──────────────────────────────────────────────────────────────────────

def test_boolfunc_full_pipeline_how_provenance(R_bf, S_bf):
    """
    TC-8: δ_HOW( π[Name]( σ[DeptID == ID]( R × S ) ) )

    After cross product, equi-select on DeptID == ID, and projection:
      Alice: (x1 ∧ y1) ∨ (x2 ∧ y2)  (Dept 1 join OR Dept 2 join)
      Bob:   (x3 ∧ y1)  (Dept 1 join only)

    HOW_PROVENANCE preserves the full DNF formula unchanged.
    """
    crossed = cross_product(R_bf, S_bf)
    selected = selection(
        crossed,
        lambda row: row["DeptID"] == row["ID"],
    )
    projected = projection(selected, ["Name"])
    result = deduplication(projected, DedupStrategy.HOW_PROVENANCE)

    x1 = BoolFunc.var("x1")
    x2 = BoolFunc.var("x2")
    x3 = BoolFunc.var("x3")
    y1 = BoolFunc.var("y1")
    y2 = BoolFunc.var("y2")

    alice_expected = x1.conjoin(y1).disjoin(x2.conjoin(y2))
    bob_expected = x3.conjoin(y1)

    assert result._data.get(("Alice",)) == alice_expected
    assert result._data.get(("Bob",)) == bob_expected


def test_boolfunc_union_project_existence(R_bf):
    """
    TC-11: δ_EXISTENCE( π[Name]( R ⊎ R ) )

    In 𝔹[X]: add = ∨, so self-union gives identical formulas
    (x1 ∨ x1 = x1 after absorption).
    EXISTENCE then collapses everything to BoolFunc.true_().
    """
    unioned = multiset_sum(R_bf, R_bf)
    projected = projection(unioned, ["Name"])
    result = deduplication(projected, DedupStrategy.EXISTENCE)

    assert set(result._data.keys()) == {("Alice",), ("Bob",)}
    for ann in result._data.values():
        assert ann == BOOLFUNC_SR.one()


# ──────────────────────────────────────────────────────────────────────
# Counting pipeline test (TC-10)
# ──────────────────────────────────────────────────────────────────────

def test_counting_union_how_provenance(R_nat):
    """
    TC-10: δ_HOW( R ⊎ R )

    In ℕ: add(a, a) = 2a. After self-union:
      (Alice, Eng): 3+3 = 6
      (Alice, HR): 2+2 = 4
      (Bob, Eng): 5+5 = 10

    HOW_PROVENANCE preserves the doubled counts.
    """
    unioned = multiset_sum(R_nat, R_nat)
    result = deduplication(unioned, DedupStrategy.HOW_PROVENANCE)

    assert result._data.get(("Alice", "Eng")) == 6
    assert result._data.get(("Alice", "HR"))  == 4
    assert result._data.get(("Bob", "Eng")) == 10
