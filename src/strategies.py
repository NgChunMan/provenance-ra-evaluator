"""
Deduplication strategy enum.

Two strategies implement the δ operator differently. The choice
determines how much provenance information survives deduplication.

EXISTENCE
    Formal rule: δ(R)(t) = semiring.one() if R(t) ≠ semiring.zero()
    Works with : any semiring
    Provenance : none — only tuple presence is recorded

    Every nonzero annotation collapses to the multiplicative identity.
    In 𝔹 True → True (a complete no-op).
    In 𝔹[X] a rich formula like (x1 ∧ x3) ∨ x2 → the constant True.
    In ℕ that means any count → 1.
    In ℕ[X] a rich polynomial like 2t₁² + t₁t₂ → the constant 1.

HOW_PROVENANCE
    Formal rule: δ(R)(t) = R(t) if R(t) ≠ semiring.zero()
    Works with: Any semiring
    Provenance: the complete annotation is preserved (how-provenance level)

    The annotation already IS the how-provenance — no transformation needed:
      - 𝔹 Boolean: True → True  (identical to EXISTENCE; True = one())
      - PosBool[X] formula: each DNF clause = a minimal sufficient witness set
      - ℕ Counting: 42 → 42  (multiplicity preserved; contrast EXISTENCE: 42 → 1)
      - ℕ[X] polynomial: coefficients = number of derivation paths,
                         exponents = times a tuple was reused in a path
"""

from enum import Enum, auto


class DedupStrategy(Enum):
    EXISTENCE = auto()   # collapse any nonzero annotation → semiring.one()
    HOW_PROVENANCE = auto()   # pass annotation through unchanged
