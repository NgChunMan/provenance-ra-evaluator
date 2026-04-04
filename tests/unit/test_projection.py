import pytest

from src.semirings import BOOL_SR
from src.relation.k_relation import KRelation
from src.operators.projection import projection


# ──────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────

@pytest.fixture
def simple_relation():
    """A small Boolean relation where projecting Name will cause collisions."""
    rel = KRelation(["Name", "Dept"], BOOL_SR)
    rel.insert({"Name": "Alice", "Dept": "Eng"})
    rel.insert({"Name": "Alice", "Dept": "HR"})
    rel.insert({"Name": "Bob",   "Dept": "Eng"})
    return rel


# ──────────────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────────────

def test_projection_output_schema_is_correct(simple_relation):
    """Resulting relation has exactly the projected attributes."""
    raise NotImplementedError


def test_projection_colliding_rows_are_merged(simple_relation):
    """Two rows with the same projected key merge into one via semiring.add()."""
    raise NotImplementedError


def test_projection_no_collision():
    """When no rows collapse, annotation of each row is unchanged."""
    raise NotImplementedError


def test_projection_invalid_attribute_raises(simple_relation):
    """Requesting a non-existent attribute raises ValueError."""
    raise NotImplementedError


def test_projection_empty_input():
    """Projecting an empty relation returns an empty relation."""
    raise NotImplementedError
