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
    And, Or, Not, Comp, Attr, Val, In, Like, Between, Mod,
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


def _build_atom_evaluator(node) -> Callable[[Dict[str, Any]], Any]:
    """Return a callable that extracts/computes an atom value from a row dict."""
    if isinstance(node, Attr):
        name = node.attr
        return lambda row, _n=name: row[_n]
    if isinstance(node, Val):
        v = node.val
        return lambda row, _v=v: _v
    if isinstance(node, Mod):
        lhs_fn = _build_atom_evaluator(node.lhs)
        rhs_fn = _build_atom_evaluator(node.rhs)
        return lambda row, _l=lhs_fn, _r=rhs_fn: _l(row) % _r(row)
    raise ValueError(f"Cannot build atom evaluator for {type(node).__name__}")


def _like_match(val: Any, pattern: Any, negated: bool) -> bool:
    """Evaluate SQL LIKE match at runtime with a dynamic pattern."""
    import re as _re
    if val is None or pattern is None:
        return False
    regex_str = '^' + _re.escape(str(pattern)).replace('%', '.*').replace('_', '.') + '$'
    result = bool(_re.match(regex_str, str(val)))
    return not result if negated else result


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

        # Generic fallback for complex expressions (Mod, etc.)
        lhs_fn = _build_atom_evaluator(lhs)
        rhs_fn = _build_atom_evaluator(rhs)
        return lambda row, _l=lhs_fn, _r=rhs_fn, _f=cmp_fn: _f(_l(row), _r(row))

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

    if isinstance(cond, In):
        attr_name = cond.lhs.attr if isinstance(cond.lhs, Attr) else None
        values = [v.val for v in cond.values if isinstance(v, Val)]
        negated = cond.negated
        if attr_name is not None:
            return lambda row, _a=attr_name, _vs=values, _neg=negated: (
                (row[_a] not in _vs) if _neg else (row[_a] in _vs)
            )
        # Fallback: evaluate lhs dynamically
        lhs_pred = _build_atom_evaluator(cond.lhs)
        return lambda row, _l=lhs_pred, _vs=values, _neg=negated: (
            (_l(row) not in _vs) if _neg else (_l(row) in _vs)
        )

    if isinstance(cond, Like):
        import re as _re
        lhs_pred = _build_atom_evaluator(cond.lhs)
        pat_val = cond.pattern.val if isinstance(cond.pattern, Val) else None
        negated = cond.negated
        if pat_val is not None:
            # Pre-compile regex from SQL LIKE pattern
            regex_str = '^' + _re.escape(str(pat_val)).replace('%', '.*').replace('_', '.') + '$'
            compiled = _re.compile(regex_str)
            return lambda row, _l=lhs_pred, _r=compiled, _neg=negated: (
                (not bool(_r.match(str(_l(row))))) if _neg else bool(_r.match(str(_l(row))))
            )
        # Dynamic pattern
        pat_pred = _build_atom_evaluator(cond.pattern)
        return lambda row, _l=lhs_pred, _p=pat_pred, _neg=negated: (
            _like_match(_l(row), _p(row), _neg)
        )

    if isinstance(cond, Between):
        lhs_pred = _build_atom_evaluator(cond.lhs)
        lo_pred = _build_atom_evaluator(cond.lo)
        hi_pred = _build_atom_evaluator(cond.hi)
        return lambda row, _l=lhs_pred, _lo=lo_pred, _hi=hi_pred: (
            _lo(row) <= _l(row) <= _hi(row)
        )

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
        alias_map: Dict[str, str] | None = None,
    ) -> None:
        self.tables   = tables
        self.semiring = semiring
        self.strategy = strategy
        self.alias_map = alias_map or {}
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
        if name in self.tables:
            return self.tables[name]

        # Check if this name is an alias for a real table
        real_name = self.alias_map.get(name)
        if real_name and real_name in self.tables:
            return self._prefix_relation(self.tables[real_name], name)

        raise ValueError(f"Unknown table: {name!r}")

    def _prefix_relation(self, rel: KRelation, alias: str) -> KRelation:
        """
        Create a copy of *rel* with every column prefixed as ``alias.col``.

        This supports self-joins: ``FROM nation n1, nation n2`` produces
        two copies whose columns are ``n1.n_nationkey``, ``n2.n_nationkey``, etc.
        """
        new_schema = [f"{alias}.{col}" for col in rel.schema]
        result = KRelation(new_schema, rel.semiring)
        for old_key, ann in rel.items():
            # old_key is aligned with rel.schema, new_key aligns with new_schema
            result._data[old_key] = ann
        return result

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
