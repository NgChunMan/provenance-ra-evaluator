"""
Counting semiring  (ℕ, +, ×, 0, 1) — bag / multiset semantics.

Each tuple annotation is a natural number representing how many times
the tuple appears in the multiset.  Zero means absent.

Used as the **no-provenance baseline** in performance benchmarks:
it is the cheapest possible annotation type (just a Python int) so
any overhead measured against it is attributable purely to the
provenance machinery.

Deduplication in ℕ with EXISTENCE:
    any count k > 0  →  semiring.one() = 1
    (all multiplicity information is discarded)
"""

from .base import Semiring


class CountingSemiring(Semiring):
    def zero(self) -> int: return 0
    def one(self)  -> int: return 1
    def add(self, a: int, b: int) -> int: return a + b
    def mul(self, a: int, b: int) -> int: return a * b
    def is_zero(self, a: int) -> bool: return a == 0

    @property
    def name(self) -> str: return "Counting (ℕ)"


# Module-level singleton
NAT_SR = CountingSemiring()
