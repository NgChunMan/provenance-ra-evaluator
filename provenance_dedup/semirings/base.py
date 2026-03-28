"""
Abstract base class for all commutative semirings (K, +, ·, 0, 1).

A commutative semiring satisfies:
    (K, +, 0)  is a commutative monoid   — + is assoc., comm., identity 0
    (K, ·, 1)  is a commutative monoid   — · is assoc., comm., identity 1
    ·  distributes over +                — a·(b+c) = a·b + a·c
    0  annihilates ·                     — 0·a = 0

Notably, idempotence (a + a = a) is NOT required.
This lets bag semantics (ℕ) be a valid semiring while set semantics (𝔹)
is simply the special case where + happens to be idempotent.

Each RA operator maps to one semiring operation:
    Selection   σ  →  mul(annotation, 0_or_1)
    Projection  π  →  add(acc, annotation)      on collision
    Cross product × → mul(ann1, ann2)
    Multiset sum ⊎  →  add(ann1, ann2)
    Deduplication δ →  is_zero(annotation)       (zero-test, not + or ·)
"""

from abc import ABC, abstractmethod
from typing import Any


class Semiring(ABC):
    """Abstract commutative semiring interface."""

    @abstractmethod
    def zero(self) -> Any:
        """Additive identity — marks a tuple as absent from the relation."""
        ...

    @abstractmethod
    def one(self) -> Any:
        """Multiplicative identity — marks a tuple as present exactly once."""
        ...

    @abstractmethod
    def add(self, a: Any, b: Any) -> Any:
        """
        Semiring addition.
        Used by:  projection (collapsing rows), multiset union.
        """
        ...

    @abstractmethod
    def mul(self, a: Any, b: Any) -> Any:
        """
        Semiring multiplication.
        Used by:  selection (predicate filtering), cross product / join.
        """
        ...

    @abstractmethod
    def is_zero(self, a: Any) -> bool:
        """
        Return True iff a equals the additive identity.
        Used by:  deduplication (deciding whether a tuple is present).
        This is the ONLY operation deduplication uses — it does not
        call add() or mul() at all.
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable semiring name for display."""
        ...
