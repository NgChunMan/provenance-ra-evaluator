"""
δ (deduplication) operator for K-relations.

Background
----------
All other RA operators (σ, π, ×, ⊎) are expressible purely through the
semiring's add() and mul() operations.  Deduplication is the exception:

    δ(R)(t) is defined by a ZERO-TEST on R(t), not by + or ·.

This is why δ cannot be expressed as a semiring homomorphism in general,
and why it needs its own implementation rather than being derived from
the semiring structure.

Two strategies
--------------
EXISTENCE  (DedupStrategy.EXISTENCE)
    Formal rule:  δ(R)(t) = semiring.one() if R(t) ≠ semiring.zero()
    Paper ref:    Definition 3.2 (implicit); standard set-semantics collapse.
    Provenance:   None. All annotation content is discarded.
    Works with:   Any semiring.

    In ℕ: 42 → 1  (multiplicity discarded)
    In ℕ[X]: 2t1²+t1t2 → Polynomial.one()  (all provenance lost)
    In 𝔹: True → True  (no-op; was already in {0,1})

LINEAGE  (DedupStrategy.LINEAGE)
    Formal rule:  δ(R)(t) = frozenset{ x ∈ X | x appears in R(t) }
    Paper ref:    Buneman, Khanna & Tan "why-provenance" (ICDT 2001),
                  applied after polynomial computation.
    Provenance:   Which input tuples contributed (why-provenance level).
    Works with:   PolynomialSemiring only (raises TypeError otherwise).

    In ℕ[X]:  2t1²+t1t2 → frozenset({'t1','t2'})

Complexity
----------
EXISTENCE : O(n)        — n = support size of the input relation
LINEAGE   : O(n · T · V) — T = avg monomials per polynomial,
                            V = avg variables per monomial
"""

from __future__ import annotations

from typing import FrozenSet

from src.relation.k_relation import KRelation
from src.semirings.polynomial import Polynomial
from src.strategies import DedupStrategy


def deduplication(
    relation: KRelation,
    strategy: DedupStrategy = DedupStrategy.EXISTENCE,
) -> KRelation:
    """
    Apply the δ (deduplication) operator to a K-annotated relation.

    Both strategies share the same outer loop structure:
        1. Iterate all (row_key, annotation) pairs in the input.
        2. Skip rows whose annotation equals semiring.zero() (absent tuples).
        3. Assign a new annotation according to the chosen strategy.

    The returned KRelation has the same schema and semiring as the input.
    For LINEAGE the annotation type changes to frozenset[str],
    but the semiring object reference is preserved so downstream code
    can still identify which semiring was in use.

    Parameters
    ----------
    relation : KRelation
        The input K-annotated relation.
    strategy : DedupStrategy
        EXISTENCE  — collapse any nonzero annotation to semiring.one().
        LINEAGE    — extract the frozenset of variable names (requires
                     Polynomial annotations; raises TypeError otherwise).

    Returns
    -------
    KRelation
        New relation with deduplicated annotations.
        The original relation is not modified.

    Raises
    ------
    TypeError
        If LINEAGE is requested but the annotations are not Polynomial
        objects (e.g. when using CountingSemiring or BooleanSemiring).
    """
    semiring = relation.semiring
    result = KRelation(relation.schema, semiring)

    for row_key, ann in relation.items():

        # ── shared gate: skip absent tuples ──────────────────────────
        #
        # An annotation equal to semiring.zero() means this row is not
        # in the support of R.  δ must not materialise it in the output.
        #
        if semiring.is_zero(ann):
            continue

        # ── EXISTENCE: collapse to the multiplicative identity ────────
        #
        # Formal rule:  δ(R)(t) = semiring.one()
        #
        # In ℕ     :  any count  → 1
        # In ℕ[X]  :  any poly   → Polynomial({_M_ONE: 1})
        # In 𝔹     :  True       → True  (genuinely a no-op)
        #
        # This strategy uses ONLY is_zero() — never add() or mul().

        if strategy is DedupStrategy.EXISTENCE:
            result._data[row_key] = semiring.one()

        # ── LINEAGE: extract the why-set ──────────────────────────────
        #
        # Formal rule:  δ(R)(t) = { x ∈ X | x appears in R(t) }
        #
        # We iterate every monomial in the polynomial and collect the
        # union of all their variable-name sets.
        # Cost: O(T · V) per tuple, T = #monomials, V = #vars/monomial.
        #
        # Semantics: the resulting frozenset says WHICH input tuples
        # contributed to this output tuple, without recording HOW MANY
        # TIMES or IN WHAT COMBINATION (coefficients + exponents are
        # discarded). This is precisely "why-provenance".

        else:
            if not isinstance(ann, Polynomial):
                raise TypeError(
                    f"DedupStrategy.LINEAGE requires Polynomial annotations "
                    f"(got {type(ann).__name__} from semiring "
                    f"'{semiring.name}'). "
                    f"Use PolynomialSemiring and tag each input tuple with "
                    f"Polynomial.from_var('t_i') before running queries."
                )
            why_set: FrozenSet[str] = frozenset(ann.variables())
            result._data[row_key] = why_set

    return result
