"""
Boolean Function semiring PosBool[X] (𝔹[X], ∨, ∧, False, True).

Unlike the plain Boolean semiring (𝔹), annotations here are positive
Boolean formulas over tuple-ID variables — expressions built from
variable names, ∨ (OR), and ∧ (AND), with no negation.

Provenance interpretation
--------------------------
Each input tuple tᵢ is tagged with BoolFunc.var("tᵢ"). As RA
operators are applied, annotations combine:

    Join / selection  →  conjunction  (∧ = mul)
    Union / projection →  disjunction  (∨ = add)

The resulting formula for an output tuple records WHICH COMBINATIONS
of input tuples are sufficient to produce it:

    Example: annotation  (t1 ∧ t3) ∨ t2
        means the output tuple exists if (t1 AND t3 are present)
               OR (t2 is present alone).

This is "why-provenance" at the level of sufficient witnesses,
which is more informative than plain 𝔹 (presence only) but less
detailed than ℕ[X] (full derivation-path counts).

Formula representation
-----------------------
A BoolFunc is a frozenset of frozensets of strings:

    Outer frozenset  — disjunction (OR) of clauses
    Inner frozenset  — conjunction (AND) of variables within a clause

This is Disjunctive Normal Form (DNF). DNF is chosen because:
    add (∨) = union of clause sets  — O(1)
    mul (∧) = distribute clauses    — O(|a| · |b|)
    is_zero — the formula is unsatisfiable — outer set is empty

Absorption / simplification
-----------------------------
After each add() or mul(), absorption is applied:
    If clause A ⊆ clause B, then B is subsumed and removed.
    (A is at least as general as B — it is satisfied by more inputs.)
This keeps formulas compact and in a canonical reduced form.

Example absorption:
    {t1} ∨ {t1 ∧ t2}  →  {t1}
    because any assignment satisfying {t1} already satisfies {t1 ∧ t2}.

Semiring axioms hold:
    zero()  =  False  (empty disjunction — no clause can be satisfied)
    one()   =  True   (single empty clause — always satisfied)
    add     =  ∨      (commutative, associative, idempotent)
    mul     =  ∧      (commutative, associative, distributes over ∨)
    0 · a   =  0      (distributing over empty clause set gives empty)
"""

from __future__ import annotations

from typing import FrozenSet, Set

from .base import Semiring

# A clause is a conjunction of variable names (frozenset of str).
# A formula is a disjunction of clauses (frozenset of clauses).
_Clause = FrozenSet[str]
_Formula = FrozenSet[_Clause]

# Constants
_FALSE: _Formula = frozenset()          # empty disjunction — unsatisfiable
_TRUE: _Formula = frozenset([frozenset()])  # single empty clause — tautology


def _absorb(clauses: Set[_Clause]) -> _Formula:
    """
    Remove subsumed clauses: if A ⊆ B, drop B (A is more general).

    A clause A is more general than B when A ⊆ B, because satisfying
    A's variables is a weaker requirement than satisfying all of B's.
    Keeping only the most general clauses gives the canonical DNF.

    Cost: O(k²) where k = number of clauses.
    Usually k is small for the provenance use-case.
    """
    reduced: list[_Clause] = []
    for candidate in clauses:
        # Keep candidate unless some already-kept clause subsumes it
        if not any(kept <= candidate for kept in reduced):
            # Also drop any previously kept clause that candidate subsumes
            reduced = [kept for kept in reduced if not candidate <= kept]
            reduced.append(candidate)
    return frozenset(reduced)


class BoolFunc:
    """
    An element of PosBool[X]: a positive Boolean formula in DNF.

    Immutable. Equality and hashing are based on the canonical
    absorbed DNF representation, so two logically equivalent formulas
    that reduce to the same DNF compare equal.

    Do not construct directly — use the class methods:
        BoolFunc.false_()      →  zero element
        BoolFunc.true_()       →  one element
        BoolFunc.var(name)     →  single-variable formula
    """

    __slots__ = ("_formula",)

    def __init__(self, formula: _Formula) -> None:
        self._formula = formula

    # ── constructors ──────────────────────────────────────────────────

    @classmethod
    def false_(cls) -> BoolFunc:
        """The zero element: an unsatisfiable formula (empty disjunction)."""
        return cls(_FALSE)

    @classmethod
    def true_(cls) -> BoolFunc:
        """The one element: a tautological formula (empty conjunction)."""
        return cls(_TRUE)

    @classmethod
    def var(cls, name: str) -> BoolFunc:
        """A single-variable formula: just the variable `name`."""
        return cls(frozenset([frozenset([name])]))

    # ── semiring operations ───────────────────────────────────────────

    def disjoin(self, other: BoolFunc) -> BoolFunc:
        """
        Disjunction (∨): self OR other.

        In DNF: union the two clause sets, then absorb subsumed clauses.
        """
        merged = set(self._formula) | set(other._formula)
        return BoolFunc(_absorb(merged))

    def conjoin(self, other: BoolFunc) -> BoolFunc:
        """
        Conjunction (∧): self AND other.

        In DNF: distribute — for every pair of clauses (a, b), form a∪b.
        Then absorb subsumed clauses.

        Special cases:
            False ∧ anything  =  False   (empty clause set stays empty)
            True  ∧ x         =  x       (empty clause ∪ c = c)
        """
        if not self._formula or not other._formula:
            return BoolFunc(_FALSE)
        distributed: Set[_Clause] = set()
        for clause_a in self._formula:
            for clause_b in other._formula:
                distributed.add(clause_a | clause_b)
        return BoolFunc(_absorb(distributed))

    def is_false(self) -> bool:
        """True iff this formula is unsatisfiable (the zero element)."""
        return len(self._formula) == 0

    def variables(self) -> set[str]:
        """All variable names that appear in any clause of this formula."""
        return {v for clause in self._formula for v in clause}

    # ── display ───────────────────────────────────────────────────────

    def __repr__(self) -> str:
        if self.is_false():
            return "False"
        clauses = sorted(
            "(" + " ∧ ".join(sorted(clause)) + ")" if clause else "True"
            for clause in self._formula
        )
        return " ∨ ".join(clauses)

    # ── equality and hashing ──────────────────────────────────────────

    def __eq__(self, other: object) -> bool:
        return isinstance(other, BoolFunc) and self._formula == other._formula

    def __hash__(self) -> int:
        return hash(self._formula)


class BoolFuncSemiring(Semiring):
    """
    Semiring of positive Boolean functions over tuple variables.

    Elements : BoolFunc   (positive Boolean formula in DNF)
    zero()   : BoolFunc.false_()  — unsatisfiable formula
    one()    : BoolFunc.true_()   — tautology
    add(a,b) : a.disjoin(b)       — logical OR
    mul(a,b) : a.conjoin(b)       — logical AND
    is_zero  : a.is_false()
    """

    def zero(self) -> BoolFunc:
        return BoolFunc.false_()

    def one(self) -> BoolFunc:
        return BoolFunc.true_()

    def add(self, a: BoolFunc, b: BoolFunc) -> BoolFunc:
        return a.disjoin(b)

    def mul(self, a: BoolFunc, b: BoolFunc) -> BoolFunc:
        return a.conjoin(b)

    def is_zero(self, a: BoolFunc) -> bool:
        return a.is_false()

    @property
    def name(self) -> str:
        return "Boolean Function (PosBool[X])"


# Module-level singleton — import and use directly
BOOLFUNC_SR = BoolFuncSemiring()
