"""
Integration tests for the parser.

Verifies that expression strings are tokenised and parsed into the
correct expression tree nodes, and that .eval() produces the expected
result for simple single-operator queries.
"""

import pytest


def test_parser_tokenises_selection_expression():
    """A selection expression is tokenised without error."""
    raise NotImplementedError


def test_parser_tokenises_cross_product_expression():
    """A cross product expression is tokenised without error."""
    raise NotImplementedError


def test_parser_builds_correct_tree_for_nested_expression():
    """A nested expression produces the correct operator tree structure."""
    raise NotImplementedError


def test_parser_eval_selection():
    """Parsing and evaluating a selection expression produces the right rows."""
    raise NotImplementedError


def test_parser_eval_projection():
    """Parsing and evaluating a projection expression produces the right schema."""
    raise NotImplementedError
