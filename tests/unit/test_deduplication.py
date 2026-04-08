"""
Each test corresponds to a mathematically verifiable property of the
operator.

Test index
----------
TC-1  EXISTENCE collapses polynomial annotations to Polynomial.one()
TC-2  HOW_PROVENANCE preserves annotation unchanged (the worked example)
TC-3  Zero-annotation tuples are excluded from both strategies
TC-4  Boolean semiring — EXISTENCE is a complete no-op
TC-5  Counting semiring — EXISTENCE discards multiplicity
TC-6  Idempotence: δ(δ(R)) == δ(R) for EXISTENCE
TC-7  Single-variable polynomial (minimal nontrivial case)
TC-8  HOW_PROVENANCE works correctly for BoolFunc annotations
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

TC-8  — BoolFunc semiring (𝔹[X]), schema: (Name,)
        ┌───────┬───────────────────────┐
        │ Name  │ Annotation            │
        ├───────┼───────────────────────┤
        │ Alice │ (x1 ∧ x3) ∨ x2        │
        └───────┴───────────────────────┘

TC-7  — Polynomial semiring, schema: (Name,)
        ┌───────┬────────────┐
        │ Name  │ Annotation │
        ├───────┼────────────┤
        │ Carol │ t5         │
        └───────┴────────────┘

TC-9  — Polynomial semiring, schema: (Name,), empty relation (no rows)
"""

import pytest

from src.semirings import BOOL_SR, BOOLFUNC_SR, BoolFunc, NAT_SR, POLY_SR, Polynomial
from src.relation  import KRelation
from src.operators.deduplication import deduplication
from src.strategies import DedupStrategy


def _build_worked_example_relation() -> KRelation:
    """Return the pre-dedup KRelation from the worked example."""
    t1 = Polynomial.from_var("t1")
    t2 = Polynomial.from_var("t2")
    t3 = Polynomial.from_var("t3")

    alice_poly = t1.multiply(t1).add(t1.multiply(t3)).add(t2.multiply(t2))
    bob_poly = t1.multiply(t3).add(t3.multiply(t3))

    rel = KRelation(["Name"], POLY_SR)
    rel._set_raw(("Alice",), alice_poly)
    rel._set_raw(("Bob",), bob_poly)
    return rel


class TestExistenceCollapseToOne:
    """
    EXISTENCE strategy must replace every nonzero polynomial
    with exactly Polynomial.one(), discarding all provenance content.
    """

    def setup_method(self):
        self.rel = _build_worked_example_relation()
        self.result = deduplication(self.rel, DedupStrategy.EXISTENCE)
        self.one = Polynomial.one()

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


class TestHowProvenancePreservesAnnotation:
    """
    HOW_PROVENANCE strategy must return each nonzero polynomial annotation
    completely unchanged — coefficients, exponents, and variable names all
    preserved.

    Alice  t1² + t1·t3 + t2²  →  t1² + t1·t3 + t2²  (identity)
    Bob    t1·t3 + t3²  →  t1·t3 + t3²  (identity)

    The full polynomial is the how-provenance: coefficients record the
    number of derivation paths, exponents record how many times each
    input tuple was used in a single path. HOW_PROVENANCE discards nothing.
    """

    def setup_method(self):
        self.rel = _build_worked_example_relation()
        self.result = deduplication(self.rel, DedupStrategy.HOW_PROVENANCE)
        t1 = Polynomial.from_var("t1")
        t2 = Polynomial.from_var("t2")
        t3 = Polynomial.from_var("t3")
        self.alice_poly = t1.multiply(t1).add(t1.multiply(t3)).add(t2.multiply(t2))
        self.bob_poly = t1.multiply(t3).add(t3.multiply(t3))

    def test_alice_annotation_is_unchanged(self):
        assert self.result._data.get(("Alice",)) == self.alice_poly, (
            "HOW_PROVENANCE must preserve Alice's full polynomial annotation"
        )

    def test_bob_annotation_is_unchanged(self):
        assert self.result._data.get(("Bob",)) == self.bob_poly, (
            "HOW_PROVENANCE must preserve Bob's full polynomial annotation"
        )

    def test_support_size_unchanged(self):
        assert self.result.support_size() == 2, (
            "Deduplication must not add or remove tuples from the support"
        )


class TestZeroAnnotationTuplesAreExcluded:
    """
    A tuple stored with annotation Polynomial.zero() is absent from the
    relation (it is not in the support). δ must not materialise it.
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

    def test_how_provenance_excludes_zero_tuple(self):
        result = deduplication(self.rel, DedupStrategy.HOW_PROVENANCE)
        assert ("Ghost",) not in result._data, (
            "HOW_PROVENANCE must not include a tuple with zero annotation"
        )


class TestBooleanSemiringExistenceIsNoOp:
    """
    In 𝔹, semiring.one() = True.
    Any True annotation stays True; EXISTENCE changes nothing.
    This confirms the framework degenerates correctly to set semantics.
    """

    def setup_method(self):
        self.rel = KRelation(["Name"], BOOL_SR)
        self.rel._set_raw(("Alice",), True)
        self.rel._set_raw(("Bob",), True)
        self.result = deduplication(self.rel, DedupStrategy.EXISTENCE)

    def test_alice_stays_true(self):
        assert self.result._data.get(("Alice",)) is True

    def test_bob_stays_true(self):
        assert self.result._data.get(("Bob",)) is True


class TestCountingSemiringExistenceDiscardsMultiplicity:
    """
    In ℕ, semiring.one() = 1.
    Any positive count, however large, collapses to 1.
    This is the semantic difference between UNION ALL and UNION DISTINCT.
    """

    def setup_method(self):
        self.rel = KRelation(["Name"], NAT_SR)
        self.rel._set_raw(("Alice",), 42)
        self.rel._set_raw(("Bob",), 7)
        self.result = deduplication(self.rel, DedupStrategy.EXISTENCE)

    def test_alice_42_becomes_1(self):
        assert self.result._data.get(("Alice",)) == 1, (
            f"Expected 1, got {self.result._data.get(('Alice',))}"
        )

    def test_bob_7_becomes_1(self):
        assert self.result._data.get(("Bob",)) == 1, (
            f"Expected 1, got {self.result._data.get(('Bob',))}"
        )


class TestIdempotence:
    """
    After the first δ every annotation is Polynomial.one().
    Applying δ again should produce the same result:
        EXISTENCE(EXISTENCE(R)) == EXISTENCE(R)
    Polynomial.one() is nonzero, so it maps to one() again unchanged.
    """

    def setup_method(self):
        rel = _build_worked_example_relation()
        self.r1 = deduplication(rel, DedupStrategy.EXISTENCE)
        self.r1_again = deduplication(self.r1, DedupStrategy.EXISTENCE)
        self.one = Polynomial.one()

    def test_alice_unchanged_after_second_dedup(self):
        assert self.r1_again._data.get(("Alice",)) == self.one

    def test_bob_unchanged_after_second_dedup(self):
        assert self.r1_again._data.get(("Bob",)) == self.one


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

    def test_how_provenance_preserves_polynomial(self):
        result = deduplication(self.rel, DedupStrategy.HOW_PROVENANCE)
        assert result._data.get(("Carol",)) == Polynomial.from_var("t5"), (
            "HOW_PROVENANCE must return the original polynomial t5 unchanged"
        )


class TestHowProvenanceBoolFunc:
    """
    HOW_PROVENANCE works for BoolFunc annotations (𝔹[X] semiring).

    The formula is the how-provenance of 𝔹[X]: each DNF clause
    represents a minimal sufficient witness set (a conjunction of input
    tuple-IDs). HOW_PROVENANCE returns it unchanged.
    EXISTENCE collapses it to BoolFunc.true_() (the semiring one element).
    """

    def setup_method(self):
        x1 = BoolFunc.var("x1")
        x2 = BoolFunc.var("x2")
        x3 = BoolFunc.var("x3")
        # (x1 ∧ x3) ∨ x2
        self.formula = x1.conjoin(x3).disjoin(x2)
        self.rel = KRelation(["Name"], BOOLFUNC_SR)
        self.rel._set_raw(("Alice",), self.formula)

    def test_how_provenance_preserves_formula(self):
        result = deduplication(self.rel, DedupStrategy.HOW_PROVENANCE)
        assert result._data.get(("Alice",)) == self.formula, (
            "HOW_PROVENANCE must return the BoolFunc formula unchanged"
        )

    def test_existence_collapses_formula_to_true(self):
        result = deduplication(self.rel, DedupStrategy.EXISTENCE)
        assert result._data.get(("Alice",)) == BOOLFUNC_SR.one(), (
            "EXISTENCE must collapse any nonzero BoolFunc formula to True"
        )


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

    def test_how_provenance_on_empty_gives_empty(self):
        result = deduplication(self.empty, DedupStrategy.HOW_PROVENANCE)
        assert result.support_size() == 0
