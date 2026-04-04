"""
Correctness tests for the δ (deduplication) operator.

Each test corresponds to a mathematically verifiable property of the
operator.

Test index
----------
TC-1  EXISTENCE collapses polynomial annotations to Polynomial.one()
TC-2  LINEAGE extracts correct variable sets (the worked example)
TC-3  Zero-annotation tuples are excluded from both strategies
TC-4  Boolean semiring — EXISTENCE is a complete no-op
TC-5  Counting semiring — EXISTENCE discards multiplicity
TC-6  Idempotence: δ(δ(R)) == δ(R) for EXISTENCE
TC-7  Single-variable polynomial (minimal nontrivial case)
TC-8  LINEAGE raises TypeError for non-Polynomial annotations
TC-9  Empty relation → empty result for both strategies

Test data / schemas
-------------------
TC-1, TC-2, TC-6  — Polynomial semiring, schema: (Name,)
    Models the result of the query:  δ( π_Name( R ⋈_Dept R ) )
    where R has schema (Name, Dept):

        R:
        ┌───────┬──────┬─────────────┐
        │ Name  │ Dept │ Annotation  │
        ├───────┼──────┼─────────────┤
        │ Alice │ Eng  │ t1          │
        │ Alice │ HR   │ t2          │
        │ Bob   │ Eng  │ t3          │
        └───────┴──────┴─────────────┘

    After self-join ⋈_Dept and projection π(Name_L), the input to δ is:

        ┌───────┬────────────────────┐
        │ Name  │ Annotation         │
        ├───────┼────────────────────┤
        │ Alice │ t1² + t1·t3 + t2²  │
        │ Bob   │ t1·t3 + t3²        │
        └───────┴────────────────────┘

TC-3  — Polynomial semiring, schema: (Name,)
        ┌───────┬────────────┐
        │ Name  │ Annotation │
        ├───────┼────────────┤
        │ Alice │ t1         │
        │ Ghost │ 0  (zero)  │
        └───────┴────────────┘

TC-4  — Boolean semiring, schema: (Name,)
        ┌───────┬────────────┐
        │ Name  │ Annotation │
        ├───────┼────────────┤
        │ Alice │ True       │
        │ Bob   │ True       │
        └───────┴────────────┘

TC-5, TC-8  — Counting semiring, schema: (Name,)
        ┌───────┬────────────┐
        │ Name  │ Annotation │
        ├───────┼────────────┤
        │ Alice │ 42         │  (TC-5)
        │ Bob   │ 7          │  (TC-5)
        │ Alice │ 5          │  (TC-8)
        └───────┴────────────┘

TC-7  — Polynomial semiring, schema: (Name,)
        ┌───────┬────────────┐
        │ Name  │ Annotation │
        ├───────┼────────────┤
        │ Carol │ t5         │
        └───────┴────────────┘

TC-9  — Polynomial semiring, schema: (Name,), empty relation (no rows)
"""

import pytest

from src.semirings import BOOL_SR, NAT_SR, POLY_SR, Polynomial
from src.relation  import KRelation
from src.operators.deduplication import deduplication
from src.strategies import DedupStrategy


# ──────────────────────────────────────────────────────────────────────
# Shared fixture: the worked example
#
# Query: δ( π_Name( R ⋈_Dept R ) )
#
# Input R:
#   (Alice, Eng) → t1
#   (Alice, HR)  → t2
#   (Bob,   Eng) → t3
#
# After self-join ⋈_Dept and projection π(Name_L) the annotations are:
#   Alice → t1² + t1·t3 + t2²
#   Bob   → t1·t3 + t3²
#
# These polynomials are the input to δ in TC-1 and TC-2.
# ──────────────────────────────────────────────────────────────────────

def _build_worked_example_relation() -> KRelation:
    """Return the pre-dedup KRelation from the worked example."""
    t1 = Polynomial.from_var("t1")
    t2 = Polynomial.from_var("t2")
    t3 = Polynomial.from_var("t3")

    alice_poly = t1.multiply(t1).add(t1.multiply(t3)).add(t2.multiply(t2))
    bob_poly   = t1.multiply(t3).add(t3.multiply(t3))

    rel = KRelation(["Name"], POLY_SR)
    rel._set_raw(("Alice",), alice_poly)
    rel._set_raw(("Bob",),   bob_poly)
    return rel


# ──────────────────────────────────────────────────────────────────────
# TC-1  EXISTENCE collapses polynomial annotations to Polynomial.one()
# ──────────────────────────────────────────────────────────────────────

class TestExistenceCollapseToOne:
    """
    EXISTENCE strategy must replace every nonzero polynomial
    with exactly Polynomial.one(), discarding all provenance content.
    """

    def setup_method(self):
        self.rel    = _build_worked_example_relation()
        self.result = deduplication(self.rel, DedupStrategy.EXISTENCE)
        self.one    = Polynomial.one()

    def test_alice_annotation_is_one(self):
        assert self.result._data.get(("Alice",)) == self.one, (
            "Alice's rich polynomial should collapse to Polynomial.one()"
        )

    def test_bob_annotation_is_one(self):
        assert self.result._data.get(("Bob",)) == self.one, (
            "Bob's polynomial should collapse to Polynomial.one()"
        )

    def test_support_size_unchanged(self):
        assert self.result.support_size() == 2, (
            "Deduplication must not add or remove tuples from the support"
        )


# ──────────────────────────────────────────────────────────────────────
# TC-2  LINEAGE extracts correct variable sets (the worked example)
# ──────────────────────────────────────────────────────────────────────

class TestLineageExtractsCorrectVariableSets:
    """
    LINEAGE strategy must produce exactly the frozenset of all
    tuple-ID variable names that appear in each polynomial.

    Alice  t1² + t1·t3 + t2²  →  {t1, t2, t3}
        t1 appears in t1² and t1·t3
        t2 appears in t2²
        t3 appears in t1·t3

    Bob    t1·t3 + t3²        →  {t1, t3}
        t2 is ABSENT because Bob never joined with an HR tuple.
        This is the key insight: LINEAGE reveals which subsets of
        the input contributed, while EXISTENCE hides it completely.
    """

    def setup_method(self):
        self.rel    = _build_worked_example_relation()
        self.result = deduplication(self.rel, DedupStrategy.LINEAGE)

    def test_alice_why_set_is_all_three_vars(self):
        alice_why = self.result._data.get(("Alice",))
        assert alice_why == frozenset({"t1", "t2", "t3"}), (
            f"Alice's why-set should be {{t1,t2,t3}}, got {alice_why}"
        )

    def test_bob_why_set_excludes_t2(self):
        bob_why = self.result._data.get(("Bob",))
        assert "t2" not in (bob_why or set()), (
            "t2 (Alice-HR) should be absent: Bob has no HR dept, "
            "so no HR pair was ever formed in the join"
        )

    def test_bob_why_set_is_t1_and_t3(self):
        bob_why = self.result._data.get(("Bob",))
        assert bob_why == frozenset({"t1", "t3"}), (
            f"Bob's why-set should be {{t1,t3}}, got {bob_why}"
        )


# ──────────────────────────────────────────────────────────────────────
# TC-3  Zero-annotation tuples are excluded from both strategies
# ──────────────────────────────────────────────────────────────────────

class TestZeroAnnotationTuplesAreExcluded:
    """
    A tuple stored with annotation Polynomial.zero() is absent from the
    relation (it is not in the support).  δ must not materialise it.
    """

    def setup_method(self):
        self.rel = KRelation(["Name"], POLY_SR)
        self.rel._set_raw(("Alice",), Polynomial.from_var("t1"))
        self.rel._set_raw(("Ghost",), Polynomial.zero())   # absent tuple

    def test_existence_excludes_zero_tuple(self):
        result = deduplication(self.rel, DedupStrategy.EXISTENCE)
        assert ("Ghost",) not in result._data, (
            "EXISTENCE must not include a tuple with zero annotation"
        )

    def test_lineage_excludes_zero_tuple(self):
        result = deduplication(self.rel, DedupStrategy.LINEAGE)
        assert ("Ghost",) not in result._data, (
            "LINEAGE must not include a tuple with zero annotation"
        )


# ──────────────────────────────────────────────────────────────────────
# TC-4  Boolean semiring — EXISTENCE is a no-op
# ──────────────────────────────────────────────────────────────────────

class TestBooleanSemiringExistenceIsNoOp:
    """
    In 𝔹, semiring.one() = True.
    Any True annotation stays True; EXISTENCE changes nothing.
    This confirms the framework degenerates correctly to set semantics.
    """

    def setup_method(self):
        self.rel = KRelation(["Name"], BOOL_SR)
        self.rel._set_raw(("Alice",), True)
        self.rel._set_raw(("Bob",),   True)
        self.result = deduplication(self.rel, DedupStrategy.EXISTENCE)

    def test_alice_stays_true(self):
        assert self.result._data.get(("Alice",)) is True

    def test_bob_stays_true(self):
        assert self.result._data.get(("Bob",)) is True


# ──────────────────────────────────────────────────────────────────────
# TC-5  Counting semiring — EXISTENCE discards multiplicity
# ──────────────────────────────────────────────────────────────────────

class TestCountingSemiringExistenceDiscardsMultiplicity:
    """
    In ℕ, semiring.one() = 1.
    Any positive count, however large, collapses to 1.
    This is the semantic difference between UNION ALL and UNION DISTINCT.
    """

    def setup_method(self):
        self.rel = KRelation(["Name"], NAT_SR)
        self.rel._set_raw(("Alice",), 42)
        self.rel._set_raw(("Bob",),    7)
        self.result = deduplication(self.rel, DedupStrategy.EXISTENCE)

    def test_alice_42_becomes_1(self):
        assert self.result._data.get(("Alice",)) == 1, (
            f"Expected 1, got {self.result._data.get(('Alice',))}"
        )

    def test_bob_7_becomes_1(self):
        assert self.result._data.get(("Bob",)) == 1, (
            f"Expected 1, got {self.result._data.get(('Bob',))}"
        )


# ──────────────────────────────────────────────────────────────────────
# TC-6  Idempotence: δ(δ(R)) == δ(R) for EXISTENCE
# ──────────────────────────────────────────────────────────────────────

class TestIdempotence:
    """
    After the first δ every annotation is Polynomial.one().
    Applying δ again should produce the same result:
        EXISTENCE(EXISTENCE(R)) == EXISTENCE(R)
    Polynomial.one() is nonzero, so it maps to one() again unchanged.
    """

    def setup_method(self):
        rel          = _build_worked_example_relation()
        self.r1      = deduplication(rel, DedupStrategy.EXISTENCE)
        self.r1_again = deduplication(self.r1, DedupStrategy.EXISTENCE)
        self.one     = Polynomial.one()

    def test_alice_unchanged_after_second_dedup(self):
        assert self.r1_again._data.get(("Alice",)) == self.one

    def test_bob_unchanged_after_second_dedup(self):
        assert self.r1_again._data.get(("Bob",)) == self.one


# ──────────────────────────────────────────────────────────────────────
# TC-7  Single-variable polynomial (minimal nontrivial case)
# ──────────────────────────────────────────────────────────────────────

class TestSingleVariablePolynomial:
    """
    A polynomial consisting of a single tuple-ID variable is the
    simplest nonzero, non-one annotation.  Both strategies must handle it.
    """

    def setup_method(self):
        self.rel = KRelation(["Name"], POLY_SR)
        self.rel._set_raw(("Carol",), Polynomial.from_var("t5"))

    def test_existence_collapses_to_one(self):
        result = deduplication(self.rel, DedupStrategy.EXISTENCE)
        assert result._data.get(("Carol",)) == Polynomial.one(), (
            "t5 should collapse to Polynomial.one()"
        )

    def test_lineage_gives_singleton_set(self):
        result = deduplication(self.rel, DedupStrategy.LINEAGE)
        assert result._data.get(("Carol",)) == frozenset({"t5"}), (
            "Single-variable poly t5 should yield why-set {t5}"
        )


# ──────────────────────────────────────────────────────────────────────
# TC-8  LINEAGE raises TypeError for non-Polynomial annotations
# ──────────────────────────────────────────────────────────────────────

class TestLineageTypeErrorOnNonPolynomial:
    """
    LINEAGE needs to call ann.variables(), which only exists on Polynomial.
    If a CountingSemiring (or any other) is used, the operator must raise
    a descriptive TypeError rather than silently returning wrong results.
    """

    def test_raises_type_error_for_counting_semiring(self):
        rel = KRelation(["Name"], NAT_SR)
        rel._set_raw(("Alice",), 5)
        with pytest.raises(TypeError):
            deduplication(rel, DedupStrategy.LINEAGE)


# ──────────────────────────────────────────────────────────────────────
# TC-9  Empty relation → empty result for both strategies
# ──────────────────────────────────────────────────────────────────────

class TestEmptyRelation:
    """
    Applying δ to a relation with no tuples must produce a relation
    with no tuples.  This is the base case of the support definition.
    """

    def setup_method(self):
        self.empty = KRelation(["Name"], POLY_SR)

    def test_existence_on_empty_gives_empty(self):
        result = deduplication(self.empty, DedupStrategy.EXISTENCE)
        assert result.support_size() == 0

    def test_lineage_on_empty_gives_empty(self):
        result = deduplication(self.empty, DedupStrategy.LINEAGE)
        assert result.support_size() == 0
