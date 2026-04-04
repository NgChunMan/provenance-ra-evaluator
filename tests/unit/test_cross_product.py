import pytest

from src.semirings import BOOL_SR
from src.relation.k_relation import KRelation
from src.operators.cross_product import cross_product


# ──────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────

@pytest.fixture
def left():
    rel = KRelation(["A"], BOOL_SR)
    rel.insert({"A": 1})
    rel.insert({"A": 2})
    return rel


@pytest.fixture
def right():
    rel = KRelation(["B"], BOOL_SR)
    rel.insert({"B": "x"})
    rel.insert({"B": "y"})
    return rel


# ──────────────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────────────

def test_cross_product_output_schema(left, right):
    """Output schema is left.schema + right.schema."""
    raise NotImplementedError


def test_cross_product_row_count(left, right):
    """Output support size equals |supp(left)| * |supp(right)|."""
    raise NotImplementedError


def test_cross_product_annotation_is_mul(left, right):
    """Each output annotation equals semiring.mul(left_ann, right_ann)."""
    raise NotImplementedError


def test_cross_product_empty_left(right):
    """Cross product with an empty left relation yields an empty result."""
    raise NotImplementedError


def test_cross_product_empty_right(left):
    """Cross product with an empty right relation yields an empty result."""
    raise NotImplementedError


def test_cross_product_mismatched_semirings():
    """Relations with different semirings raise ValueError."""
    raise NotImplementedError
