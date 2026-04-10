"""Deduplication strategy enum.

Two strategies implement the δ operator differently. The choice determines
how much provenance information survives deduplication.

Strategies:
    EXISTENCE: Formal rule: ``δ(R)(t) = semiring.one()`` if
        ``R(t) ≠ semiring.zero()``. Works with any semiring. All annotation
        content is discarded; only tuple presence is recorded.
    HOW_PROVENANCE: Formal rule: ``δ(R)(t) = R(t)`` if
        ``R(t) ≠ semiring.zero()``. Works with any semiring. The complete
        annotation is preserved (how-provenance level).
"""

from enum import Enum, auto


class DedupStrategy(Enum):
    EXISTENCE = auto()   # collapse any nonzero annotation → semiring.one()
    HOW_PROVENANCE = auto()   # pass annotation through unchanged
