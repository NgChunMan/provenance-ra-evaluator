"""
Polynomial provenance semiring  ℕ[X].

Three classes:

    Monomial — immutable product of variables: t1² · t3
    Polynomial — finite formal sum: 2t1² + t1·t3 + t2²
    PolynomialSemiring — Semiring implementation wrapping Polynomial arithmetic

Provenance interpretation
--------------------------
Every input tuple tᵢ is tagged with the polynomial  Polynomial.from_var("ti").
As RA operators are applied, annotations combine:

    Join / selection  →  polynomial multiplication  (·)
    Union / projection →  polynomial addition        (+)

The resulting polynomial for an output tuple records:
    - WHICH input tuples contributed  (the variables present)
    - HOW they combined (coefficient = number of derivation paths, exponent = times the same tuple was used)

Example: annotation  2t1² + t1·t3
    means: the output tuple is derivable in 3 distinct ways —
        2 ways using t1 twice each,
        1 way using t1 and t3 once each.

This is what the paper calls "how-provenance", in contrast to the
simpler "why-provenance" (just a set of contributing tuple IDs).
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, FrozenSet, Optional, Set

from .base import Semiring


class Monomial:
    """
    Immutable product of variables with natural-number exponents.

        t1² · t3  →  Monomial({'t1': 2, 't3': 1})

    Stored as a frozenset of (variable, exponent) pairs so it is
    hashable and usable as a dict key inside Polynomial.
    """
    __slots__ = ('_items',)

    def __init__(self, var_exp: Dict[str, int]):
        # Canonical form: drop any zero exponents
        self._items: FrozenSet[tuple] = frozenset(
            (v, e) for v, e in var_exp.items() if e > 0
        )


    @staticmethod
    def constant_one() -> 'Monomial':
        """The multiplicative identity: the empty product (= 1)."""
        return Monomial({})


    @staticmethod
    def from_var(name: str) -> 'Monomial':
        """Single-variable monomial: name^1."""
        return Monomial({name: 1})


    def multiply(self, other: 'Monomial') -> 'Monomial':
        """
        Monomial multiplication: merge exponent maps, summing shared vars.
        t1² · t1·t3  =  t1³ · t3
        """
        exps: Dict[str, int] = defaultdict(int)
        for v, e in self._items:
            exps[v] += e
        for v, e in other._items:
            exps[v] += e
        return Monomial(dict(exps))


    def variables(self) -> Set[str]:
        """All variable names that appear in this monomial."""
        return {v for v, _ in self._items}


    def is_one(self) -> bool:
        """True iff this is the empty product (the constant 1)."""
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
    """
    Element of ℕ[X]: a finite formal sum  Σ cᵢ · mᵢ
    where cᵢ ∈ ℕ>0 and mᵢ are distinct Monomials.

    Internally a Dict[Monomial, int].
    Zero coefficients are never stored (absent from the dict).

    Semiring operations
    -------------------
    add(p, q)       →  term-wise coefficient addition   (models union / projection)
    multiply(p, q)  →  distributed monomial products    (models join / selection)

    Provenance methods
    ------------------
    variables()             — set of all variable names in any monomial
                              (provenance extraction calls this)
    first_monomial_poly()   — single-term polynomial with one witness
                              (useful for a "Strategy 2" witness extension)
    term_count()            — number of distinct monomials (for benchmarks)
    """
    __slots__ = ('_terms',)

    def __init__(self, terms: Optional[Dict[Monomial, int]] = None):
        self._terms: Dict[Monomial, int] = (
            {m: c for m, c in terms.items() if c > 0}
            if terms else {}
        )


    @staticmethod
    def zero() -> 'Polynomial':
        """Additive identity: the empty sum."""
        return Polynomial()


    @staticmethod
    def one() -> 'Polynomial':
        """Multiplicative identity: the constant polynomial 1."""
        return Polynomial({_M_ONE: 1})


    @staticmethod
    def from_var(name: str) -> 'Polynomial':
        """
        Tag an input tuple with its own ID.
        Tuple tᵢ starts with annotation  Polynomial.from_var("ti") = tᵢ.
        """
        return Polynomial({Monomial.from_var(name): 1})


    # ── semiring operations ───────────────────────────────────────────
    def add(self, other: 'Polynomial') -> 'Polynomial':
        """
        Polynomial addition.
        Models UNION ALL and projection (collapsing same-key rows).
        """
        result = dict(self._terms)
        for m, c in other._terms.items():
            result[m] = result.get(m, 0) + c
        return Polynomial(result)


    def multiply(self, other: 'Polynomial') -> 'Polynomial':
        """
        Polynomial multiplication.
        Models JOIN and selection (combining paired tuple annotations).
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
        """True iff this polynomial is the additive identity (no terms)."""
        return not self._terms


    # ── provenance utilities ──────────────────────────────────────────
    def variables(self) -> Set[str]:
        """
        Return all tuple-ID variable names that appear anywhere
        in any monomial of this polynomial.

        Used for provenance extraction (collapses how-provenance to
        why-provenance):
            2t1² + t1·t3 + t2²  →  {'t1', 't2', 't3'}

        This is a lossy projection: coefficients and exponents are dropped.
        The result is equivalent to 'why-provenance' from
        Buneman, Khanna & Tan (ICDT 2001).
        """
        out: Set[str] = set()
        for m in self._terms:
            out.update(m.variables())
        return out


    def first_monomial_poly(self) -> 'Polynomial':
        """
        Return a single-term polynomial containing only the first monomial.
        """
        if self.is_zero():
            return Polynomial.zero()
        m = next(iter(self._terms))
        return Polynomial({m: 1})


    def term_count(self) -> int:
        """Number of distinct monomials. Used by benchmarks."""
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
    """
    Semiring wrapper around Polynomial arithmetic.

    Passing an instance of this class to a KRelation or operator means
    all annotations are Polynomial objects and all semiring operations
    delegate to Polynomial.add / Polynomial.multiply.
    """
    def zero(self) -> Polynomial: return Polynomial.zero()
    def one(self) -> Polynomial: return Polynomial.one()
    def add(self, a: Polynomial, b: Polynomial) -> Polynomial: return a.add(b)
    def mul(self, a: Polynomial, b: Polynomial) -> Polynomial: return a.multiply(b)
    def is_zero(self, a: Polynomial) -> bool: return a.is_zero()

    @property
    def name(self) -> str: return "Polynomial (ℕ[X])"


# Module-level singleton
POLY_SR = PolynomialSemiring()
