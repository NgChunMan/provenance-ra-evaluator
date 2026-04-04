"""
Boolean semiring  (𝔹, ∨, ∧, False, True).

Models standard set semantics: a tuple is either in the relation (True)
or not (False).  There are no multiplicities and no provenance.

Key property: + is idempotent (True ∨ True = True), which is why
set union (UNION DISTINCT) collapses duplicates automatically.
By contrast, the bag semiring ℕ does NOT have this property.

Deduplication in 𝔹: EXISTENCE strategy is a complete no-op.
    True → semiring.one() = True   (unchanged)
"""

from .base import Semiring


class BooleanSemiring(Semiring):
    def zero(self) -> bool: return False
    def one(self) -> bool: return True
    def add(self, a: bool, b: bool) -> bool: return a or b
    def mul(self, a: bool, b: bool) -> bool: return a and b
    def is_zero(self, a: bool) -> bool: return not a

    @property
    def name(self) -> str: return "Boolean (𝔹)"


# Module-level singleton — import and use directly
BOOL_SR = BooleanSemiring()
