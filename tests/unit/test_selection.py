import pytest

from src.semirings import BOOL_SR
from src.relation.k_relation import KRelation
from src.operators.selection import selection


# ──────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────

@pytest.fixture
def simple_relation():
    """A small Boolean relation with three rows."""
    rel = KRelation(["Name", "Dept", "Salary"], BOOL_SR)
    rel.insert({"Name": "Alice", "Dept": "Eng",  "Salary": 90})
    rel.insert({"Name": "Bob",   "Dept": "HR",   "Salary": 60})
    rel.insert({"Name": "Carol", "Dept": "Eng",  "Salary": 40})
    return rel


# ──────────────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────────────

def test_selection_matching_rows_are_kept(simple_relation):
    """Rows satisfying the predicate appear in the result."""
    raise NotImplementedError


def test_selection_non_matching_rows_are_excluded(simple_relation):
    """Rows not satisfying the predicate are absent from the result."""
    raise NotImplementedError


def test_selection_annotation_unchanged_for_passing_rows(simple_relation):
    """Annotations of kept rows are not modified."""
    raise NotImplementedError


def test_selection_all_rows_pass():
    """When all rows satisfy the predicate, the result equals the input."""
    raise NotImplementedError


def test_selection_no_rows_pass(simple_relation):
    """When no rows satisfy the predicate, the result is empty."""
    raise NotImplementedError


def test_selection_empty_input():
    """Applying selection to an empty relation returns an empty relation."""
    raise NotImplementedError
