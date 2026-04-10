"""
π (projection) operator for K-relations.

Formal rule
-----------
    π_A(R)(t) = Σ_{s ∈ supp(R), s[A] = t} R(s)

For each output tuple t (formed by keeping only attributes A), sum
the annotations of all input tuples that project onto t.  The
summation uses semiring.add().

In 𝔹: True ∨ True = True (presence collapses, idempotent)
In ℕ: counts are added (multiset projection)
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
    """Apply the π (projection) operator to a K-annotated relation.

    Args:
        relation (KRelation): The input K-annotated relation.
        attributes (List[str]): The subset of column names to keep.
            Must all exist in ``relation.schema``. Order is preserved
            as given.

    Returns:
        KRelation: New relation with schema equal to ``attributes``.
        Tuples that collapse to the same projected key have their
        annotations combined via ``semiring.add()``.
        The original relation is not modified.

    Raises:
        ValueError: If any attribute in ``attributes`` is not in
            ``relation.schema``.
    """
    # ── validate requested attributes ──────────────────────────────────
    schema_set = set(relation.schema)
    unknown = [a for a in attributes if a not in schema_set]
    if unknown:
        raise ValueError(
            f"Attribute(s) {unknown!r} not found in schema {relation.schema!r}"
        )

    semiring = relation.semiring
    result = KRelation(attributes, semiring)

    # ── precompute index positions once ────────────────────────────────
    indices = [relation.schema.index(a) for a in attributes]

    for row_key, ann in relation.items():

        # ── skip absent tuples ──────────────────────────────────────────
        if semiring.is_zero(ann):
            continue

        # ── build projected tuple and reconstruct as dict ───────────────
        projected_key = tuple(row_key[i] for i in indices)
        projected_row = dict(zip(attributes, projected_key))

        # ── accumulate via semiring.add() (insert handles collisions) ───
        result.insert(projected_row, ann)

    return result

