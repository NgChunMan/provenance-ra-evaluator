"""
⊎ (multiset sum) operator for K-relations.

Formal rule
-----------
    (R ⊎ S)(t) = R(t) + S(t)

For every tuple t, add the annotations from both relations using
semiring.add(). If a tuple only exists in one relation, the other
contributes semiring.zero() (additive identity), so the annotation
is unchanged.

In 𝔹: True ∨ False = True (union; a tuple present in either is present)
In ℕ: counts are added (bag union)
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
        New relation with the same schema as both inputs. Each tuple's
        annotation is the semiring sum of its annotations in left and right.
        Both input relations are not modified.

    Raises
    ------
    ValueError
        If left and right have different schemas or different semirings.
    """
    # ── validate schema compatibility ──────────────────────────────────
    if left.schema != right.schema:
        raise ValueError(
            f"Both relations must have the same schema; "
            f"got {left.schema!r} and {right.schema!r}"
        )

    # ── validate semiring compatibility ────────────────────────────────
    if left.semiring is not right.semiring:
        raise ValueError(
            f"Both relations must use the same semiring; "
            f"got {left.semiring!r} and {right.semiring!r}"
        )

    semiring = left.semiring
    result = KRelation(left.schema, semiring)

    # ── pass 1: copy all left annotations (no collisions yet) ──────────
    result._data.update(left._data)

    # ── pass 2: accumulate right annotations via semiring.add() ────────
    schema = left.schema
    for key, ann in right.items():
        row = dict(zip(schema, key))
        result.insert(row, ann)

    return result

