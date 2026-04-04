"""
π (projection) operator for K-relations.

Formal rule
-----------
    π_A(R)(t) = Σ_{s ∈ supp(R), s[A] = t} R(s)

For each output tuple t (formed by keeping only attributes A), sum
the annotations of all input tuples that project onto t.  The
summation uses semiring.add().

In 𝔹:    True ∨ True = True  (presence collapses, idempotent)
In ℕ:    counts are added    (multiset projection)
In ℕ[X]: polynomials are added (how-provenance accumulation)

Complexity
----------
O(n) — one add() per input tuple.
"""

from __future__ import annotations

from typing import List

from src.relation.k_relation import KRelation


def projection(
    relation: KRelation,
    attributes: List[str],
) -> KRelation:
    """
    Apply the π (projection) operator to a K-annotated relation.

    Parameters
    ----------
    relation : KRelation
        The input K-annotated relation.
    attributes : List[str]
        The subset of column names to keep.  Must all exist in
        relation.schema.  Order is preserved as given.

    Returns
    -------
    KRelation
        New relation with schema equal to `attributes`.  Tuples that
        collapse to the same projected key have their annotations
        combined via semiring.add().
        The original relation is not modified.

    Raises
    ------
    ValueError
        If any attribute in `attributes` is not in relation.schema.
    """
    raise NotImplementedError

