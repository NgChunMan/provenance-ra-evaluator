"""
Query evaluator: walks a parsed expression tree and dispatches
each node to the corresponding operator implementation.

The evaluator is the bridge between the parser (src/parser/) and the
operator functions (src/operators/).  It pattern-matches on AST node
types and recursively evaluates sub-expressions.
"""

from __future__ import annotations

import operator as op
from typing import Any, Callable, Dict

from src.semirings.base import Semiring
from src.relation.k_relation import KRelation
from src.operators.selection import selection
from src.operators.projection import projection
from src.operators.cross_product import cross_product
from src.operators.multiset_sum import multiset_sum
from src.operators.deduplication import deduplication
from src.strategies import DedupStrategy
from src.parser.grammar import (
    Select, Project, Dedup, Cross, Union, Table,
    And, Or, Not, Comp, Attr, Val,
    Rename, Group, Div, Inner, Outer, Anti, Intersect, Minus,
)


# ── Supported-operator registry ───────────────────────────────────────

_SUPPORTED = (
    "σ (selection), π (projection), × (cross product), "
    "∪ (union / multiset-sum), δ (deduplication)"
)

# Maps each unsupported grammar node to a human-readable (symbol, name) pair.
_UNSUPPORTED_OPS = {
    Rename: ("ρ",  "rename"),
    Group: ("ɣ",  "group-by / aggregation"),
    Div: ("÷",  "division"),
    Inner: ("⨝",  "inner join"),
    Outer: ("⟕",  "left outer join"),
    Anti: ("⊳",  "anti join"),
    Intersect: ("∩",  "intersection"),
    Minus: ("-",  "set difference"),
}


class UnsupportedOperatorError(NotImplementedError):
    """
    Raised when an expression node maps to an operator that has not
    been implemented in this system.

    Attributes
    ----------
    symbol : str
        The Unicode symbol for the operator (e.g. ``'ɣ'``).
    operator_name : str
        The English name of the operator (e.g. ``'group-by / aggregation'``).
    """

    def __init__(self, symbol: str, operator_name: str) -> None:
        super().__init__(
            f"Operator '{operator_name}' ({symbol}) is not supported. "
            f"Supported operators: {_SUPPORTED}."
        )
        self.symbol = symbol
        self.operator_name = operator_name
_CMP_OPS: Dict[str, Callable] = {
    "==": op.eq,
    "!=": op.ne,
    ">=": op.ge,
    "<=": op.le,
    ">":  op.gt,
    "<":  op.lt,
}


def _build_predicate(cond) -> Callable[[Dict[str, Any]], bool]:
    """
    Convert a condition AST node into a callable predicate.

    Parameters
    ----------
    cond
        A condition node from the parser grammar (Comp, And, Or, Not).

    Returns
    -------
    Callable[[Dict[str, Any]], bool]
        A function that takes a row dict and returns True/False.
    """
    if isinstance(cond, Comp):
        cmp_fn = _CMP_OPS[cond.op]
        lhs = cond.lhs
        rhs = cond.rhs

        # Attr <op> Val
        if isinstance(lhs, Attr) and isinstance(rhs, Val):
            attr_name = lhs.attr
            val = rhs.val
            return lambda row, _a=attr_name, _v=val, _f=cmp_fn: _f(row[_a], _v)

        # Val <op> Attr
        if isinstance(lhs, Val) and isinstance(rhs, Attr):
            val = lhs.val
            attr_name = rhs.attr
            return lambda row, _v=val, _a=attr_name, _f=cmp_fn: _f(_v, row[_a])

        # Attr <op> Attr
        if isinstance(lhs, Attr) and isinstance(rhs, Attr):
            a1 = lhs.attr
            a2 = rhs.attr
            return lambda row, _a1=a1, _a2=a2, _f=cmp_fn: _f(row[_a1], row[_a2])

        # Val <op> Val (degenerate but valid)
        if isinstance(lhs, Val) and isinstance(rhs, Val):
            result = cmp_fn(lhs.val, rhs.val)
            return lambda row, _r=result: _r

    if isinstance(cond, And):
        pred_l = _build_predicate(cond.lhs)
        pred_r = _build_predicate(cond.rhs)
        return lambda row, _l=pred_l, _r=pred_r: _l(row) and _r(row)

    if isinstance(cond, Or):
        pred_l = _build_predicate(cond.lhs)
        pred_r = _build_predicate(cond.rhs)
        return lambda row, _l=pred_l, _r=pred_r: _l(row) or _r(row)

    if isinstance(cond, Not):
        pred = _build_predicate(cond.arg)
        return lambda row, _p=pred: not _p(row)

    raise ValueError(f"Unsupported condition node: {type(cond).__name__}")


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
    strategy : DedupStrategy
        The deduplication strategy to use for δ nodes.  Defaults to
        EXISTENCE.
    """

    def __init__(
        self,
        tables: Dict[str, KRelation],
        semiring: Semiring,
        strategy: DedupStrategy = DedupStrategy.EXISTENCE,
    ) -> None:
        self.tables   = tables
        self.semiring = semiring
        self.strategy = strategy
        self._handlers = {
            Table: self._eval_table,
            Select: self._eval_select,
            Project: self._eval_project,
            Cross: self._eval_cross,
            Union: self._eval_union,
            Dedup: self._eval_dedup,
        }

    def evaluate(self, expression) -> KRelation:
        """
        Walk the expression tree and compute the result.

        Parameters
        ----------
        expression
            A parsed expression tree node (produced by src.parser).

        Returns
        -------
        KRelation
            The result of evaluating the full expression.

        Raises
        ------
        ValueError
            If the query references an unknown table name.
        UnsupportedOperatorError
            If the expression contains an operator that is not implemented.
        """
        node_type = type(expression)

        # ── Check unsupported operators first for a helpful error ──────
        if node_type in _UNSUPPORTED_OPS:
            symbol, name = _UNSUPPORTED_OPS[node_type]
            raise UnsupportedOperatorError(symbol, name)

        # ── Dispatch to the appropriate handler ────────────────────────
        handler = self._handlers.get(node_type)
        if handler is None:
            raise UnsupportedOperatorError(
                "?", type(expression).__name__
            )
        return handler(expression)

    # ── Private handler methods ────────────────────────────────────────

    def _eval_table(self, expression) -> KRelation:
        name = expression.name
        if name not in self.tables:
            raise ValueError(f"Unknown table: {name!r}")
        return self.tables[name]

    def _eval_select(self, expression) -> KRelation:
        sub_rel = self.evaluate(expression.rel)
        pred = _build_predicate(expression.cond)
        return selection(sub_rel, pred)

    def _eval_project(self, expression) -> KRelation:
        sub_rel = self.evaluate(expression.rel)
        attrs = [a.attr if isinstance(a, Attr) else str(a)
                 for a in expression.attrs]
        return projection(sub_rel, attrs)

    def _eval_cross(self, expression) -> KRelation:
        return cross_product(
            self.evaluate(expression.lhs),
            self.evaluate(expression.rhs),
        )

    def _eval_union(self, expression) -> KRelation:
        return multiset_sum(
            self.evaluate(expression.lhs),
            self.evaluate(expression.rhs),
        )

    def _eval_dedup(self, expression) -> KRelation:
        return deduplication(self.evaluate(expression.rel), self.strategy)

