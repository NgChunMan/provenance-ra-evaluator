import pytest

from src.semirings import BOOL_SR
from src.relation.k_relation import KRelation
from src.operators.multiset_sum import multiset_sum


# ──────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────

@pytest.fixture
def left():
    rel = KRelation(["Name"], BOOL_SR)
    rel.insert({"Name": "Alice"})
    rel.insert({"Name": "Bob"})
    return rel


@pytest.fixture
def right():
    rel = KRelation(["Name"], BOOL_SR)
    rel.insert({"Name": "Bob"})
    rel.insert({"Name": "Carol"})
    return rel


# ──────────────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────────────

def test_multiset_sum_union_of_disjoint_tuples():
    """Tuples only in one side appear in the output."""
    raise NotImplementedError


def test_multiset_sum_overlapping_tuple_annotations_combined(left, right):
    """A tuple in both relations has annotation = semiring.add(left_ann, right_ann)."""
    raise NotImplementedError


def test_multiset_sum_output_schema_unchanged(left, right):
    """Output schema matches both input schemas."""
    raise NotImplementedError


def test_multiset_sum_with_empty_left(right):
    """⊎ with an empty left relation returns a copy of right."""
    raise NotImplementedError


def test_multiset_sum_with_empty_right(left):
    """⊎ with an empty right relation returns a copy of left."""
    raise NotImplementedError


def test_multiset_sum_mismatched_schemas():
    """Relations with different schemas raise ValueError."""
    raise NotImplementedError


def test_multiset_sum_mismatched_semirings():
    """Relations with different semirings raise ValueError."""
    raise NotImplementedError
