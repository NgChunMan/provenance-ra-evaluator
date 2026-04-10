"""Abstract base class for all commutative semirings (K, +, ·, 0, 1).

A commutative semiring satisfies:

- ``(K, +, 0)`` is a commutative monoid: ``+`` is associative, commutative,
  with identity ``0``.
- ``(K, ·, 1)`` is a commutative monoid: ``·`` is associative, commutative,
  with identity ``1``.
- ``·`` distributes over ``+``: ``a·(b+c) = a·b + a·c``.
- ``0`` annihilates ``·``: ``0·a = 0``.

Notably, idempotence (``a + a = a``) is NOT required. This lets bag
semantics (ℕ) be a valid semiring while set semantics (𝔹) is the special
case where ``+`` happens to be idempotent.

Each RA operator maps to one semiring operation:

- Selection σ → ``mul(annotation, 0_or_1)``
- Projection π → ``add(acc, annotation)`` on collision
- Cross product × → ``mul(ann1, ann2)``
- Multiset sum ⊎ → ``add(ann1, ann2)``
- Deduplication δ → ``is_zero(annotation)`` (zero-test, not ``+`` or ``·``)
"""

from abc import ABC, abstractmethod
from typing import Any


class Semiring(ABC):
    """Abstract commutative semiring interface.

    Subclasses must implement :meth:`zero`, :meth:`one`, :meth:`add`,
    :meth:`mul`, :meth:`is_zero`, and :attr:`name`.
    """

    @abstractmethod
    def zero(self) -> Any:
        """Return the additive identity (marks a tuple as absent).

        Returns:
            Any: The zero element of the semiring.
        """
        ...

    @abstractmethod
    def one(self) -> Any:
        """Return the multiplicative identity (marks a tuple as present once).

        Returns:
            Any: The one element of the semiring.
        """
        ...

    @abstractmethod
    def add(self, a: Any, b: Any) -> Any:
        """Apply semiring addition.

        Used by projection (collapsing rows) and multiset union.

        Args:
            a: Left operand.
            b: Right operand.

        Returns:
            Any: The semiring sum ``a + b``.
        """
        ...

    @abstractmethod
    def mul(self, a: Any, b: Any) -> Any:
        """Apply semiring multiplication.

        Args:
            a: Left operand.
            b: Right operand.

        Returns:
            Any: The semiring product ``a · b``.
        """
        ...

    @abstractmethod
    def is_zero(self, a: Any) -> bool:
        """Return ``True`` iff ``a`` equals the additive identity.

        Used by deduplication to decide whether a tuple is present.
        This is the ONLY operation deduplication uses — it does not
        call :meth:`add` or :meth:`mul` at all.

        Args:
            a: The annotation value to test.

        Returns:
            bool: ``True`` if ``a`` is the zero element.
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Return a human-readable semiring name for display.

        Returns:
            str: The semiring name (e.g. ``'Boolean (𝔹)'``).
        """
        ...
