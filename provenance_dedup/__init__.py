"""
provenance_dedup
=============
Provenance-aware relational algebra evaluator.

Quick imports
-------------
    from provenance_dedup import KRelation, deduplication, DedupStrategy
    from provenance_dedup import BOOL_SR, NAT_SR, POLY_SR, Polynomial
"""

from .semirings   import BOOL_SR, NAT_SR, POLY_SR, Polynomial, Semiring
from .relation    import KRelation
from .operators   import deduplication
from .strategies  import DedupStrategy

__all__ = [
    "Semiring",
    "BOOL_SR", "NAT_SR", "POLY_SR",
    "Polynomial",
    "KRelation",
    "deduplication",
    "DedupStrategy",
]