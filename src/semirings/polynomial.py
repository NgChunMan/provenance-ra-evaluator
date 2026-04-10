"""
Polynomial provenance semiring ℕ[X].

Three classes:

    Monomial — immutable product of variables: t1² · t3
    Polynomial — finite formal sum: 2t1² + t1·t3 + t2²
    PolynomialSemiring — Semiring implementation wrapping Polynomial arithmetic

Provenance interpretation
--------------------------
Every input tuple tᵢ is tagged with the polynomial Polynomial.from_var("ti").
As RA operators are applied, annotations combine:

    Join / selection → polynomial multiplication (·)
    Union / projection → polynomial addition (+)

The resulting polynomial for an output tuple records:
    - WHICH input tuples contributed  (the variables present)
    - HOW they combined (coefficient = number of derivation paths, exponent = times the same tuple was used)

Example: annotation  2t1² + t1·t3
    means: the output tuple is derivable in 3 distinct ways —
        2 ways using t1 twice each,
        1 way using t1 and t3 once each.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, FrozenSet, Optional, Set

from .base import Semiring


class Monomial:
    """Immutable product of variables with natural-number exponents.

    Stored as a frozenset of ``(variable, exponent)`` pairs so it is
    hashable and usable as a dict key inside :class:`Polynomial`.
    """
    __slots__ = ('_items',)

    def __init__(self, var_exp: Dict[str, int]):
        # Canonical form: drop any zero exponents
        self._items: FrozenSet[tuple] = frozenset(
            (v, e) for v, e in var_exp.items() if e > 0
        )


    @staticmethod
    def constant_one() -> 'Monomial':
        """Return the multiplicative identity: the empty product (= 1).

        Returns:
            Monomial: The constant monomial ``1``.
        """
        return Monomial({})


    @staticmethod
    def from_var(name: str) -> 'Monomial':
        """Return a single-variable monomial ``name^1``.

        Args:
            name (str): The variable name.

        Returns:
            Monomial: The monomial ``name^1``.
        """
        return Monomial({name: 1})


    def multiply(self, other: 'Monomial') -> 'Monomial':
        """Return the monomial product of ``self`` and *other*.

        Merges exponent maps by summing shared variable exponents.

        Args:
            other (Monomial): The right-hand monomial.

        Returns:
            Monomial: A new monomial representing ``self · other``.
        """
        exps: Dict[str, int] = defaultdict(int)
        for v, e in self._items:
            exps[v] += e
        for v, e in other._items:
            exps[v] += e
        return Monomial(dict(exps))


    def variables(self) -> Set[str]:
        """Return all variable names that appear in this monomial.

        Returns:
            Set[str]: The set of variable names.
        """
        return {v for v, _ in self._items}


    def is_one(self) -> bool:
        """Return ``True`` iff this is the empty product (the constant 1).

        Returns:
            bool: ``True`` when there are no variable terms.
        """
        return len(self._items) == 0


    def __eq__(self, other: object) -> bool:
        return isinstance(other, Monomial) and self._items == other._items


    def __hash__(self) -> int:
        return hash(self._items)


    def __repr__(self) -> str:
        if self.is_one():
            return "1"
        return "·".join(
            f"{v}^{e}" if e > 1 else v
            for v, e in sorted(self._items)
        )


# Module-level singleton — avoids repeated allocation of the constant 1
_M_ONE = Monomial.constant_one()


class Polynomial:
    """Element of ℕ[X]: a finite formal sum  Σ cᵢ · mᵢ
    where cᵢ ∈ ℕ>0 and mᵢ are distinct Monomials.

    Internally a ``Dict[Monomial, int]``.
    Zero coefficients are never stored (absent from the dict).

    Semiring operations:
        add(p, q): Term-wise coefficient addition — models ⊎ (multiset sum)
            and π (projection, collapsing same-key rows).
        multiply(p, q): Distributed monomial products — models × (cross
            product).

    Provenance methods:
        variables(): Set of all variable names in any monomial.
        first_monomial_poly(): Single-term polynomial with one witness.
        term_count(): Number of distinct monomials (for benchmarks).
    """
    __slots__ = ('_terms',)

    def __init__(self, terms: Optional[Dict[Monomial, int]] = None):
        self._terms: Dict[Monomial, int] = (
            {m: c for m, c in terms.items() if c > 0}
            if terms else {}
        )


    @staticmethod
    def zero() -> 'Polynomial':
        """Return the additive identity: the empty sum.

        Returns:
            Polynomial: The zero polynomial.
        """
        return Polynomial()


    @staticmethod
    def one() -> 'Polynomial':
        """Return the multiplicative identity: the constant polynomial 1.

        Returns:
            Polynomial: The polynomial ``1``.
        """
        return Polynomial({_M_ONE: 1})


    @staticmethod
    def from_var(name: str) -> 'Polynomial':
        """Tag an input tuple with its own provenance variable.

        Tuple ``tᵢ`` starts with annotation ``Polynomial.from_var("ti") = tᵢ``.

        Args:
            name (str): The variable name for the input tuple.

        Returns:
            Polynomial: The single-term polynomial ``name^1``.
        """
        return Polynomial({Monomial.from_var(name): 1})


    # ── semiring operations ───────────────────────────────────────────
    def add(self, other: 'Polynomial') -> 'Polynomial':
        """Return the polynomial sum of ``self`` and *other*.

        Args:
            other (Polynomial): The right-hand polynomial.

        Returns:
            Polynomial: A new polynomial representing ``self + other``.
        """
        result = dict(self._terms)
        for m, c in other._terms.items():
            result[m] = result.get(m, 0) + c
        return Polynomial(result)


    def multiply(self, other: 'Polynomial') -> 'Polynomial':
        """Return the polynomial product of ``self`` and *other*.

        Args:
            other (Polynomial): The right-hand polynomial.

        Returns:
            Polynomial: A new polynomial representing ``self · other``.
        """
        if self.is_zero() or other.is_zero():
            return Polynomial.zero()
        acc: Dict[Monomial, int] = defaultdict(int)
        for m1, c1 in self._terms.items():
            for m2, c2 in other._terms.items():
                acc[m1.multiply(m2)] += c1 * c2
        return Polynomial(dict(acc))


    # ── zero test ─────────────────────────────────────────────────────
    def is_zero(self) -> bool:
        """Return ``True`` iff this polynomial is the additive identity.

        Returns:
            bool: ``True`` when the polynomial has no terms.
        """
        return not self._terms


    # ── provenance utilities ──────────────────────────────────────────
    def variables(self) -> Set[str]:
        """Return all tuple-ID variable names appearing in any monomial.

        Returns:
            Set[str]: The set of all variable names across all monomials.
        """
        out: Set[str] = set()
        for m in self._terms:
            out.update(m.variables())
        return out


    def first_monomial_poly(self) -> 'Polynomial':
        """Return a single-term polynomial containing only the first monomial.

        Returns:
            Polynomial: A new polynomial with one monomial from ``self``,
            or the zero polynomial if ``self`` is zero.
        """
        if self.is_zero():
            return Polynomial.zero()
        m = next(iter(self._terms))
        return Polynomial({m: 1})


    def term_count(self) -> int:
        """Return the number of distinct monomials.

        Used by benchmarks to measure annotation complexity.

        Returns:
            int: Number of terms in this polynomial.
        """
        return len(self._terms)


    # ── equality / hashing ────────────────────────────────────────────
    def __eq__(self, other: object) -> bool:
        return isinstance(other, Polynomial) and self._terms == other._terms


    def __hash__(self) -> int:
        return hash(frozenset(self._terms.items()))


    def __repr__(self) -> str:
        if self.is_zero():
            return "0"
        parts = []
        for m, c in sorted(self._terms.items(), key=lambda x: repr(x[0])):
            m_str = repr(m)
            if m_str == "1":
                parts.append(str(c))
            elif c == 1:
                parts.append(m_str)
            else:
                parts.append(f"{c}·{m_str}")
        return " + ".join(parts)


class PolynomialSemiring(Semiring):
    """Semiring wrapper around :class:`Polynomial` arithmetic.

    Passing an instance of this class to a :class:`~src.relation.KRelation`
    or operator means all annotations are :class:`Polynomial` objects and all
    semiring operations delegate to :meth:`Polynomial.add` and
    :meth:`Polynomial.multiply`.
    """
    def zero(self) -> Polynomial:
        """Return the zero polynomial (additive identity)."""
        return Polynomial.zero()
    def one(self) -> Polynomial:
        """Return the constant polynomial 1 (multiplicative identity)."""
        return Polynomial.one()
    def add(self, a: Polynomial, b: Polynomial) -> Polynomial:
        """Return the polynomial sum: models ⊎ (multiset sum) and π (projection)."""
        return a.add(b)
    def mul(self, a: Polynomial, b: Polynomial) -> Polynomial:
        """Return the polynomial product: models × (cross product)."""
        return a.multiply(b)
    def is_zero(self, a: Polynomial) -> bool:
        """Return ``True`` iff the polynomial is the additive identity."""
        return a.is_zero()

    @property
    def name(self) -> str: return "Polynomial (ℕ[X])"


# Module-level singleton
POLY_SR = PolynomialSemiring()
