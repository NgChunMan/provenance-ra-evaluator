"""
⊎ (multiset sum) operator for K-relations.

Formal rule
-----------
    (R ⊎ S)(t) = R(t) + S(t)

For every tuple t, add the annotations from both relations using
semiring.add().  If a tuple only exists in one relation, the other
contributes semiring.zero() (additive identity), so the annotation
is unchanged.

In 𝔹:    True ∨ False = True  (union; a tuple present in either is present)
In ℕ:    counts are added     (bag union)
In ℕ[X]: polynomials are added

Both input relations must share the same schema and semiring.

Complexity
----------
O(n + m) — n = |supp(R)|, m = |supp(S)|.
"""

from __future__ import annotations

from src.relation.k_relation import KRelation


def multiset_sum(
    left: KRelation,
    right: KRelation,
) -> KRelation:
    """
    Apply the ⊎ (multiset sum) operator to two K-annotated relations.

    Parameters
    ----------
    left : KRelation
        The left-hand input relation.
    right : KRelation
        The right-hand input relation.

    Returns
    -------
    KRelation
        New relation with the same schema as both inputs.  Each tuple's
        annotation is the semiring sum of its annotations in left and right.
        Both input relations are not modified.

    Raises
    ------
    ValueError
        If left and right have different schemas or different semirings.
    """
    raise NotImplementedError

