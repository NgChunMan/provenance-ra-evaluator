"""
δ (deduplication) operator for K-relations.

Background
----------
All other RA operators (σ, π, ×, ⊎) are expressible purely through the
semiring's add() and mul() operations. Deduplication is the exception:

    δ(R)(t) is defined by a ZERO-TEST on R(t), not by + or ·.

This is why δ cannot be expressed as a semiring homomorphism in general,
and why it needs its own implementation rather than being derived from
the semiring structure.

Two strategies
--------------
EXISTENCE (DedupStrategy.EXISTENCE)
    Formal rule: δ(R)(t) = semiring.one() if R(t) ≠ semiring.zero()
    Provenance: None. All annotation content is discarded.
    Works with: Any semiring.

    In 𝔹: True → True  (no-op; was already in {0,1})
    In 𝔹[X]: (x1 ∧ x3) ∨ x2 → the constant True.
    In ℕ: 42 → 1 (multiplicity discarded)
    In ℕ[X]: 2t1²+t1t2 → Polynomial.one()  (all provenance lost)

HOW_PROVENANCE (DedupStrategy.HOW_PROVENANCE)
    Formal rule: δ(R)(t) = R(t) if R(t) ≠ semiring.zero()
    Provenance: The complete annotation is preserved (how-provenance level).
    Works with: Any semiring.

    In 𝔹: True → True (identical to EXISTENCE; True = one())
    In 𝔹[X]: (x1∧x3)∨x2 → (x1∧x3)∨x2  (formula unchanged)
    In ℕ: 42 → 42 (multiplicity preserved; contrast EXISTENCE: 42 → 1)
    In ℕ[X]: 2t1²+t1t2 → 2t1²+t1t2 (unchanged)

Complexity
----------
EXISTENCE: O(n) — n = support size of the input relation
HOW_PROVENANCE: O(n) — identity on nonzero annotations
"""

from __future__ import annotations

from src.relation.k_relation import KRelation
from src.strategies import DedupStrategy


def deduplication(
    relation: KRelation,
    strategy: DedupStrategy = DedupStrategy.EXISTENCE,
) -> KRelation:
    """Apply the δ (deduplication) operator to a K-annotated relation.

    Both strategies share the same outer loop structure:

    1. Iterate all ``(row_key, annotation)`` pairs in the input.
    2. Skip rows whose annotation equals ``semiring.zero()`` (absent tuples).
    3. Assign a new annotation according to the chosen strategy.

    The returned ``KRelation`` has the same schema and semiring as the input.
    For ``HOW_PROVENANCE`` the annotation is passed through unchanged from the
    input relation — it is the identity on nonzero annotations.

    Args:
        relation (KRelation): The input K-annotated relation.
        strategy (DedupStrategy): Controls how annotations are transformed.
            ``EXISTENCE`` collapses any nonzero annotation to
            ``semiring.one()``. ``HOW_PROVENANCE`` passes the annotation
            through unchanged.

    Returns:
        KRelation: New relation with deduplicated annotations.
        The original relation is not modified.
    """
    semiring = relation.semiring
    result = KRelation(relation.schema, semiring)

    for row_key, ann in relation.items():

        # ── shared gate: skip absent tuples ──────────────────────────
        #
        # An annotation equal to semiring.zero() means this row is not
        # in the support of R. δ must not materialise it in the output.
        #
        if semiring.is_zero(ann):
            continue

        # ── EXISTENCE: collapse to the multiplicative identity ────────

        if strategy is DedupStrategy.EXISTENCE:
            result._data[row_key] = semiring.one()

        # ── HOW_PROVENANCE: identity on nonzero annotations ───────────
        # No computation needed — pass the annotation through unchanged.
        # Cost: O(1) per tuple.

        else:
            result._data[row_key] = ann

    return result
