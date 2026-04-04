"""Unit tests for KRelation."""

import pytest

from src.semirings import BOOL_SR
from src.relation.k_relation import KRelation


def test_insert_single_row():
    """Inserting one row makes it retrievable via annotation_of."""
    raise NotImplementedError


def test_insert_same_row_twice_accumulates_annotation():
    """Inserting the same row twice combines annotations via semiring.add()."""
    raise NotImplementedError


def test_support_size_excludes_zero_annotations():
    """Tuples with annotation == semiring.zero() are not counted."""
    raise NotImplementedError


def test_annotation_of_absent_row_returns_zero():
    """annotation_of() returns semiring.zero() for rows not in the support."""
    raise NotImplementedError


def test_items_iterates_all_stored_rows():
    """items() yields all (key, annotation) pairs."""
    raise NotImplementedError
