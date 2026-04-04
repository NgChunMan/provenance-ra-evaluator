"""
σ (selection) operator for K-relations.

Formal rule
-----------
    σ_θ(R)(t) = R(t)            if θ(t) is True
                semiring.zero() otherwise

The predicate θ is evaluated on the tuple's values.  If it holds,
the annotation passes through unchanged.  If it does not hold, the
tuple is excluded from the output (annotation becomes zero, which
means absent from the support).

This is expressed via semiring.mul():
    σ_θ(R)(t) = R(t) · semiring.one()   if θ(t)
              = R(t) · semiring.zero()  otherwise

In practice we simply skip non-matching tuples rather than
explicitly multiplying by zero, since 0·a = 0 for all a.

Complexity
----------
O(n) — one predicate evaluation per tuple in the support.
"""

from __future__ import annotations

from typing import Callable, Dict, Any

from src.relation.k_relation import KRelation


def selection(
    relation: KRelation,
    predicate: Callable[[Dict[str, Any]], bool],
) -> KRelation:
    """
    Apply the σ (selection) operator to a K-annotated relation.

    Parameters
    ----------
    relation : KRelation
        The input K-annotated relation.
    predicate : Callable[[Dict[str, Any]], bool]
        A function that takes a row as a column→value dict and returns
        True if the row should be included in the result.

    Returns
    -------
    KRelation
        New relation containing only the tuples for which the predicate
        holds, with annotations unchanged.
        The original relation is not modified.
    """
    semiring = relation.semiring
    result = KRelation(relation.schema, semiring)

    for row_key, ann in relation.items():

        # ── skip absent tuples ────────────────────────────────────────
        if semiring.is_zero(ann):
            continue

        # ── reconstruct row dict for predicate evaluation ─────────────
        #
        # The stored key is a positional tuple aligned with relation.schema.
        # We rebuild the column→value mapping so the predicate can refer
        # to columns by name rather than position.

        row_dict: Dict[str, Any] = dict(zip(relation.schema, row_key))

        # ── apply predicate ───────────────────────────────────────────
        #
        # If θ(t) holds, copy the annotation unchanged — selection never
        # modifies annotations, only gates on the predicate.
        # If θ(t) fails, the tuple is absent from the output (equivalent
        # to multiplying by semiring.zero(), which annihilates any value).

        if predicate(row_dict):
            result._data[row_key] = ann

    return result

