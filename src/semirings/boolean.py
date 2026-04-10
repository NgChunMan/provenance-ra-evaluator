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
    """Boolean semiring (𝔹, ∨, ∧, False, True) — standard set semantics.

    A tuple is either in the relation (``True``) or absent (``False``).
    There are no multiplicities and no provenance.
    """

    def zero(self) -> bool:
        """Return the additive identity ``False`` (tuple absent).

        Returns:
            bool: Always ``False``.
        """
        return False

    def one(self) -> bool:
        """Return the multiplicative identity ``True`` (tuple present).

        Returns:
            bool: Always ``True``.
        """
        return True

    def add(self, a: bool, b: bool) -> bool:
        """Return the logical OR of two Boolean annotations.

        Args:
            a (bool): Left annotation.
            b (bool): Right annotation.

        Returns:
            bool: ``a or b``.
        """
        return a or b

    def mul(self, a: bool, b: bool) -> bool:
        """Return the logical AND of two Boolean annotations.

        Args:
            a (bool): Left annotation.
            b (bool): Right annotation.

        Returns:
            bool: ``a and b``.
        """
        return a and b

    def is_zero(self, a: bool) -> bool:
        """Return ``True`` iff the annotation is the zero element ``False``.

        Args:
            a (bool): The annotation to test.

        Returns:
            bool: ``not a``.
        """
        return not a

    @property
    def name(self) -> str:
        """Return the semiring display name.

        Returns:
            str: ``'Boolean (𝔹)'``.
        """
        return "Boolean (𝔹)"


# Module-level singleton — import and use directly
BOOL_SR = BooleanSemiring()
