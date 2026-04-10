"""Semirings package — re-exports all public semiring classes and singletons.

Available semirings:
    BOOL_SR: Boolean semiring (𝔹, ∨, ∧, False, True) — set semantics.
    NAT_SR: Counting semiring (ℕ, +, ×, 0, 1) — bag / multiset semantics.
    POLY_SR: Polynomial semiring (ℕ[X]) — how-provenance semantics.
    BOOLFUNC_SR: Boolean function semiring (𝔹[X]) — Boolean provenance.
"""

from .base import Semiring
from .boolean import BooleanSemiring, BOOL_SR
from .boolean_function import BoolFuncSemiring, BoolFunc, BOOLFUNC_SR
from .counting import CountingSemiring, NAT_SR
from .polynomial import PolynomialSemiring, POLY_SR, Monomial, Polynomial

__all__ = [
    "Semiring",
    "BooleanSemiring", "BOOL_SR",
    "BoolFuncSemiring", "BoolFunc", "BOOLFUNC_SR",
    "CountingSemiring", "NAT_SR",
    "PolynomialSemiring", "POLY_SR",
    "Monomial",
    "Polynomial",
]