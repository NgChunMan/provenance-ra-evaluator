"""
Query evaluator: walks a parsed expression tree and dispatches
each node to the corresponding operator implementation.

The evaluator is the bridge between the parser (src/parser/) and the
operator functions (src/operators/).  Each expression node produced by
the parser has an .eval() method; this module provides the context
(loaded tables, active semiring) in which evaluation runs.

Typical usage
-------------
    from src.parser.parser import parse
    from src.evaluator import Evaluator
    from src.semirings import BOOL_SR
    from src.io.csv_loader import load_csv

    ev = Evaluator(
        tables={"R": load_csv("data/R.csv", BOOL_SR),
                "S": load_csv("data/S.csv", BOOL_SR)},
        semiring=BOOL_SR,
    )
    result = ev.evaluate(parse("σ[A == 1](R × S)"))
"""

from __future__ import annotations

from typing import Dict

from src.semirings.base import Semiring
from src.relation.k_relation import KRelation


class Evaluator:
    """
    Evaluates a parsed relational algebra expression tree against a
    fixed set of base tables and a chosen semiring.

    Parameters
    ----------
    tables : Dict[str, KRelation]
        Mapping from table name (as it appears in the query) to a
        pre-loaded KRelation.
    semiring : Semiring
        The semiring used for all operator computations.  Must match
        the semiring of all provided tables.
    """

    def __init__(
        self,
        tables: Dict[str, KRelation],
        semiring: Semiring,
    ) -> None:
        self.tables   = tables
        self.semiring = semiring

    def evaluate(self, expression) -> KRelation:
        """
        Walk the expression tree and compute the result.

        Parameters
        ----------
        expression
            A parsed expression tree node (produced by src.parser.parser).

        Returns
        -------
        KRelation
            The result of evaluating the full expression.
        """
        raise NotImplementedError

