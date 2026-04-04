"""
× (cross product) operator for K-relations.

Formal rule
-----------
    (R × S)(t1 ⊕ t2) = R(t1) · S(t2)

For every pair of tuples (one from each relation), the output tuple
has the concatenated schema and an annotation equal to the product of
the two input annotations, computed via semiring.mul().

In 𝔹:    True ∧ True = True  (both tuples must be present)
In ℕ:    counts are multiplied
In ℕ[X]: polynomials are multiplied  (provenance of a join)

Note: the output schema is left.schema + right.schema.  If a column
name appears in both schemas, it is included twice.  Renaming is the
caller's responsibility.

Complexity
----------
O(n · m) — n = |supp(R)|, m = |supp(S)|.
"""

from __future__ import annotations

from src.relation.k_relation import KRelation


def cross_product(
    left: KRelation,
    right: KRelation,
) -> KRelation:
    """
    Apply the × (cross product) operator to two K-annotated relations.

    Parameters
    ----------
    left : KRelation
        The left-hand input relation.
    right : KRelation
        The right-hand input relation.

    Returns
    -------
    KRelation
        New relation with schema = left.schema + right.schema.
        Every pair of tuples (one from each input) appears in the
        output with annotation = semiring.mul(left_ann, right_ann).
        Both input relations are not modified.

    Raises
    ------
    ValueError
        If left and right use different semirings.
    """
    raise NotImplementedError

