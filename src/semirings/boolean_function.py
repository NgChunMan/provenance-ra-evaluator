"""
Boolean Function semiring 𝔹[X].

Unlike the plain Boolean semiring (𝔹), annotations here are
positive Boolean formulas over tuple-ID variables — expressions built
from variable names, ∨ (OR), and ∧ (AND).

Each clause represents a sufficient witness — a set of input tuples
whose joint presence produces the output. Absorption ensures no clause
is subsumed by another.
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
    """Remove subsumed clauses: if A ⊆ B, drop B (A is more general).

    A clause A is more general than B when ``A ⊆ B``, because satisfying
    A's variables is a weaker requirement than satisfying all of B's.
    Keeping only the most general clauses gives the canonical DNF.

    Cost: O(k²) where k = number of clauses. Usually k is small for the
    provenance use-case.

    Args:
        clauses (Set[_Clause]): Raw set of conjunctive clauses to reduce.

    Returns:
        _Formula: Canonical frozenset of non-subsumed clauses.
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
    """An element of 𝔹[X]: a positive Boolean formula in canonical DNF.

    Immutable. Equality and hashing are based on the canonical absorbed DNF
    representation, so two logically equivalent formulas that reduce to the
    same DNF compare equal.

    Do not construct directly — use the class methods:

    - :meth:`false_`: zero element.
    - :meth:`true_`: one element.
    - :meth:`var`: single-variable formula.
    """

    __slots__ = ("_formula",)

    def __init__(self, formula: _Formula) -> None:
        self._formula = formula

    # ── constructors ──────────────────────────────────────────────────

    @classmethod
    def false_(cls) -> BoolFunc:
        """Return the zero element: an unsatisfiable formula (empty disjunction).

        Returns:
            BoolFunc: The zero / ``False`` element.
        """
        return cls(_FALSE)

    @classmethod
    def true_(cls) -> BoolFunc:
        """Return the one element: a tautological formula (empty conjunction).

        Returns:
            BoolFunc: The one / ``True`` element.
        """
        return cls(_TRUE)

    @classmethod
    def var(cls, name: str) -> BoolFunc:
        """Return a single-variable formula.

        Args:
            name (str): The variable name.

        Returns:
            BoolFunc: A formula consisting of just the single variable ``name``.
        """
        return cls(frozenset([frozenset([name])]))

    # ── semiring operations ───────────────────────────────────────────

    def disjoin(self, other: BoolFunc) -> BoolFunc:
        """Return the disjunction (∨) of this formula and *other*.

        In DNF: union the two clause sets, then absorb subsumed clauses.

        Args:
            other (BoolFunc): The right-hand operand.

        Returns:
            BoolFunc: A new formula equivalent to ``self OR other``.
        """
        merged = set(self._formula) | set(other._formula)
        return BoolFunc(_absorb(merged))

    def conjoin(self, other: BoolFunc) -> BoolFunc:
        """Return the conjunction (∧) of this formula and *other*.

        In DNF: distribute — for every pair of clauses (a, b), form ``a∪b``.
        Then absorb subsumed clauses.

        Special cases:

        - ``False ∧ anything = False`` (empty clause set stays empty).
        - ``True ∧ x = x`` (empty clause ∪ c = c).

        Args:
            other (BoolFunc): The right-hand operand.

        Returns:
            BoolFunc: A new formula equivalent to ``self AND other``.
        """
        if not self._formula or not other._formula:
            return BoolFunc(_FALSE)
        distributed: Set[_Clause] = set()
        for clause_a in self._formula:
            for clause_b in other._formula:
                distributed.add(clause_a | clause_b)
        return BoolFunc(_absorb(distributed))

    def is_false(self) -> bool:
        """Return ``True`` iff this formula is unsatisfiable (the zero element).

        Returns:
            bool: ``True`` when the formula has no clauses.
        """
        return len(self._formula) == 0

    def variables(self) -> set[str]:
        """Return all variable names that appear in any clause of this formula.

        Returns:
            set[str]: The set of all variable names.
        """
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
    """Semiring of positive Boolean functions over tuple variables.

    Elements are :class:`BoolFunc` instances (positive Boolean formulae in
    DNF).

    - ``zero()``: ``BoolFunc.false_()`` — the unsatisfiable formula.
    - ``one()``: ``BoolFunc.true_()`` — the tautology.
    - ``add(a, b)``: ``a.disjoin(b)`` — logical OR.
    - ``mul(a, b)``: ``a.conjoin(b)`` — logical AND.
    - ``is_zero(a)``: ``a.is_false()``.
    """

    def zero(self) -> BoolFunc:
        """Return the zero element: the unsatisfiable formula (False)."""
        return BoolFunc.false_()

    def one(self) -> BoolFunc:
        """Return the one element: the tautological formula (True)."""
        return BoolFunc.true_()

    def add(self, a: BoolFunc, b: BoolFunc) -> BoolFunc:
        """Return the disjunction (∨) of two positive Boolean formulas."""
        return a.disjoin(b)

    def mul(self, a: BoolFunc, b: BoolFunc) -> BoolFunc:
        """Return the conjunction (∧) of two positive Boolean formulas."""
        return a.conjoin(b)

    def is_zero(self, a: BoolFunc) -> bool:
        """Return ``True`` iff the formula is unsatisfiable (the zero element)."""
        return a.is_false()

    @property
    def name(self) -> str:
        return "Boolean Function (𝔹[X])"


# Module-level singleton — import and use directly
BOOLFUNC_SR = BoolFuncSemiring()
