"""
Deduplication strategy enum.

Two strategies implement the δ operator differently. The choice
determines how much provenance information survives deduplication.

EXISTENCE
    Formal rule:  δ(R)(t) = semiring.one() if R(t) ≠ semiring.zero()
    Works with :  any semiring
    Provenance :  none — only tuple presence is recorded

    Every nonzero annotation collapses to the multiplicative identity.
    In ℕ that means any count → 1.
    In ℕ[X] a rich polynomial like 2t₁² + t₁t₂ → the constant 1.
    In 𝔹 True → True (a complete no-op).

LINEAGE
    Formal rule:  δ(R)(t) = frozenset{ x ∈ X | x appears in R(t) }
    Works with:   PolynomialSemiring only
    Provenance:   which input tuples contributed (why-provenance level)

    Scans every monomial of the polynomial annotation and collects
    all distinct tuple-ID variable names. The result is a frozenset
    of strings. It records *which* input tuples are responsible for the 
    output tuple, but not *how* they contributed (coefficients and exponents 
    are discarded).

    Useful for:
      - Trust / access-control queries ("did a sensitive tuple contribute?")
      - Probabilistic databases ("what is the probability this
                                  output tuple exists, given
                                  independent tuple probabilities?")
      - Debugging ("which source records led to
                   this result row?")
"""

from enum import Enum, auto


class DedupStrategy(Enum):
    EXISTENCE = auto()   # collapse any nonzero annotation → semiring.one()
    LINEAGE   = auto()   # extract set of contributing variable names
