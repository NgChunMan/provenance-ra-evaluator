"""
Counting semiring  (ℕ, +, ×, 0, 1) — bag / multiset semantics.

Each tuple annotation is a natural number representing how many times
the tuple appears in the multiset. Zero means absent.

Used as the no-provenance baseline in performance benchmarks:
it is the cheapest possible annotation type (just a Python int) so
any overhead measured against it is attributable purely to the
provenance machinery.

Deduplication in ℕ with EXISTENCE:
    any count k > 0  →  semiring.one() = 1
    (all multiplicity information is discarded)
"""

from .base import Semiring


class CountingSemiring(Semiring):
    """Counting semiring (ℕ, +, ×, 0, 1) — bag / multiset semantics."""

    def zero(self) -> int:
        """Return the additive identity ``0`` (tuple absent).

        Returns:
            int: ``0``.
        """
        return 0

    def one(self) -> int:
        """Return the multiplicative identity ``1`` (tuple present once).

        Returns:
            int: ``1``.
        """
        return 1

    def add(self, a: int, b: int) -> int:
        """Return the integer sum of two counting annotations.

        Args:
            a (int): Left annotation.
            b (int): Right annotation.

        Returns:
            int: ``a + b``.
        """
        return a + b

    def mul(self, a: int, b: int) -> int:
        """Return the integer product of two counting annotations.

        Args:
            a (int): Left annotation.
            b (int): Right annotation.

        Returns:
            int: ``a * b``.
        """
        return a * b

    def is_zero(self, a: int) -> bool:
        """Return ``True`` iff the annotation is ``0``.

        Args:
            a (int): The annotation to test.

        Returns:
            bool: ``a == 0``.
        """
        return a == 0

    @property
    def name(self) -> str:
        """Return the semiring display name.

        Returns:
            str: ``'Counting (ℕ)'``.
        """
        return "Counting (ℕ)"


# Module-level singleton
NAT_SR = CountingSemiring()
