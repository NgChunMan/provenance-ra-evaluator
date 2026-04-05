"""
Unit tests for KRelation.

Test index
----------
Insertion and annotation retrieval
    TK-1   Insert a single row → annotation_of() returns semiring.one()
    TK-2   Insert same row twice → annotation is semiring.add(one(), one())
    TK-3   Insert row with an explicit annotation → annotation_of() returns it
    TK-4   Insert multiple distinct rows → all are retrievable independently
    TK-5   Insert with explicit annotation, then again → annotations accumulate

Schema ordering
    TK-6   Row tuple key respects schema column order, not dict insertion order
    TK-7   Multi-column schema resolves keys correctly

Support size
    TK-8   support_size() counts rows with non-zero annotations
    TK-9   support_size() excludes rows with zero annotations (_set_raw)
    TK-10  support_size() of an empty relation is 0
    TK-11  Inserting then overwriting with zero → no longer in support

Absent-row behaviour
    TK-12  annotation_of() returns zero for a row never inserted
    TK-13  annotation_of() returns zero after all rows of a fresh relation

items() iteration
    TK-14  items() yields exactly all stored (key, annotation) pairs
    TK-15  items() also yields rows whose annotation is zero (raw storage)
    TK-16  items() preserves annotation accuracy

_set_raw()
    TK-17  _set_raw() sets a row directly without invoking semiring.add()
    TK-18  _set_raw() overwrites existing annotation

pretty() / __repr__()
    TK-19  pretty() output contains schema and semiring name
    TK-20  __repr__() shows class name, schema, semiring, and support_size
"""

import pytest

from src.semirings import BOOL_SR, NAT_SR, POLY_SR
from src.semirings.polynomial import Polynomial
from src.relation.k_relation import KRelation


# ──────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────

@pytest.fixture
def bool_rel():
    """Empty KRelation over schema [Name, Dept] with Boolean semiring."""
    return KRelation(["Name", "Dept"], BOOL_SR)


@pytest.fixture
def nat_rel():
    """Empty KRelation over schema [Name] with Counting semiring."""
    return KRelation(["Name"], NAT_SR)


@pytest.fixture
def poly_rel():
    """Empty KRelation over schema [Name] with Polynomial semiring."""
    return KRelation(["Name"], POLY_SR)


# ──────────────────────────────────────────────────────────────────────
# TK-1 to TK-5: Insertion and annotation retrieval
# ──────────────────────────────────────────────────────────────────────

def test_insert_single_row(bool_rel):
    """TK-1: Inserting one row makes it retrievable via annotation_of()."""
    bool_rel.insert({"Name": "Alice", "Dept": "Eng"})
    assert bool_rel.annotation_of(Name="Alice", Dept="Eng") == BOOL_SR.one()


def test_insert_same_row_twice_accumulates_annotation(nat_rel):
    """TK-2: Inserting the same row twice combines annotations via semiring.add()."""
    nat_rel.insert({"Name": "Alice"})
    nat_rel.insert({"Name": "Alice"})
    # ℕ: 1 + 1 = 2
    expected = NAT_SR.add(NAT_SR.one(), NAT_SR.one())
    assert nat_rel.annotation_of(Name="Alice") == expected
    assert nat_rel.annotation_of(Name="Alice") == 2


def test_insert_with_explicit_annotation(nat_rel):
    """TK-3: Inserting with an explicit annotation stores that annotation."""
    nat_rel.insert({"Name": "Bob"}, annotation=7)
    assert nat_rel.annotation_of(Name="Bob") == 7


def test_insert_multiple_distinct_rows(bool_rel):
    """TK-4: Inserting multiple distinct rows stores all of them independently."""
    bool_rel.insert({"Name": "Alice", "Dept": "Eng"})
    bool_rel.insert({"Name": "Bob", "Dept": "HR"})
    bool_rel.insert({"Name": "Carol", "Dept": "Eng"})

    assert bool_rel.annotation_of(Name="Alice", Dept="Eng") == True
    assert bool_rel.annotation_of(Name="Bob", Dept="HR") == True
    assert bool_rel.annotation_of(Name="Carol", Dept="Eng") == True
    assert bool_rel.support_size() == 3


def test_insert_explicit_annotation_accumulates(nat_rel):
    """TK-5: Multiple inserts with explicit annotations accumulate via add()."""
    nat_rel.insert({"Name": "Alice"}, annotation=3)
    nat_rel.insert({"Name": "Alice"}, annotation=5)
    # ℕ: 3 + 5 = 8
    assert nat_rel.annotation_of(Name="Alice") == 8


# ──────────────────────────────────────────────────────────────────────
# TK-6 to TK-7: Schema ordering
# ──────────────────────────────────────────────────────────────────────

def test_row_tuple_key_respects_schema_order():
    """TK-6: The internal key tuple follows schema column order, not dict order."""
    rel = KRelation(["A", "B", "C"], BOOL_SR)
    # Pass the dict in reverse order
    rel.insert({"C": 3, "A": 1, "B": 2})
    # Internally stored as (1, 2, 3) following [A, B, C]
    assert (1, 2, 3) in rel._data


def test_multi_column_schema_resolves_keys_correctly():
    """TK-7: annotation_of() correctly projects a multi-column schema."""
    rel = KRelation(["X", "Y", "Z"], NAT_SR)
    rel.insert({"X": "a", "Y": "b", "Z": "c"}, annotation=4)
    assert rel.annotation_of(X="a", Y="b", Z="c") == 4
    # Different values in the same columns → zero
    assert rel.annotation_of(X="a", Y="b", Z="d") == NAT_SR.zero()


# ──────────────────────────────────────────────────────────────────────
# TK-8 to TK-11: Support size
# ──────────────────────────────────────────────────────────────────────

def test_support_size_counts_nonzero_rows(bool_rel):
    """TK-8: support_size() counts only rows with non-zero annotations."""
    bool_rel.insert({"Name": "Alice", "Dept": "Eng"})
    bool_rel.insert({"Name": "Bob", "Dept": "HR"})
    assert bool_rel.support_size() == 2


def test_support_size_excludes_zero_annotations(nat_rel):
    """TK-9: Rows with annotation 0 (set via _set_raw) are excluded from support_size()."""
    nat_rel._set_raw(("Alice",), 5)
    nat_rel._set_raw(("Ghost",), 0)   # zero annotation — absent from support
    assert nat_rel.support_size() == 1


def test_support_size_of_empty_relation(bool_rel):
    """TK-10: support_size() is 0 for a freshly created empty relation."""
    assert bool_rel.support_size() == 0


def test_support_size_after_zero_overwrite(nat_rel):
    """TK-11: Overwriting a row's annotation with zero removes it from support."""
    nat_rel.insert({"Name": "Alice"}, annotation=3)
    assert nat_rel.support_size() == 1
    nat_rel._set_raw(("Alice",), 0)
    assert nat_rel.support_size() == 0


# ──────────────────────────────────────────────────────────────────────
# TK-12 to TK-13: Absent-row behaviour
# ──────────────────────────────────────────────────────────────────────

def test_annotation_of_absent_row_returns_zero(bool_rel):
    """TK-12: annotation_of() returns semiring.zero() for rows never inserted."""
    assert bool_rel.annotation_of(Name="Nobody", Dept="Finance") == BOOL_SR.zero()
    assert bool_rel.annotation_of(Name="Nobody", Dept="Finance") is False


def test_annotation_of_absent_after_other_inserts(bool_rel):
    """TK-13: annotation_of() returns zero for a row not inserted, even when others exist."""
    bool_rel.insert({"Name": "Alice", "Dept": "Eng"})
    assert bool_rel.annotation_of(Name="Bob", Dept="Eng") == BOOL_SR.zero()


# ──────────────────────────────────────────────────────────────────────
# TK-14 to TK-16: items() iteration
# ──────────────────────────────────────────────────────────────────────

def test_items_iterates_all_stored_rows(nat_rel):
    """TK-14: items() yields exactly all (key, annotation) pairs in storage."""
    nat_rel.insert({"Name": "Alice"}, annotation=3)
    nat_rel.insert({"Name": "Bob"}, annotation=7)

    items = dict(nat_rel.items())
    assert items == {
        ("Alice",): 3,
        ("Bob",): 7,
    }


def test_items_includes_zero_annotation_rows(nat_rel):
    """TK-15: items() yields all raw rows, including those with zero annotation."""
    nat_rel._set_raw(("Alice",), 5)
    nat_rel._set_raw(("Ghost",), 0)

    keys = [k for k, _ in nat_rel.items()]
    assert ("Alice",) in keys
    assert ("Ghost",) in keys  # raw storage includes zero rows


def test_items_annotation_accuracy(poly_rel):
    """TK-16: items() returns accurate annotations matching what was stored."""
    t1 = Polynomial.from_var("t1")
    t2 = Polynomial.from_var("t2")
    poly_rel._set_raw(("Alice",), t1)
    poly_rel._set_raw(("Bob",), t2)

    items = dict(poly_rel.items())
    assert items[("Alice",)] == t1
    assert items[("Bob",)] == t2


# ──────────────────────────────────────────────────────────────────────
# TK-17 to TK-18: _set_raw()
# ──────────────────────────────────────────────────────────────────────

def test_set_raw_stores_without_accumulation(poly_rel):
    """TK-17: _set_raw() stores the annotation directly without invoking semiring.add()."""
    t1 = Polynomial.from_var("t1")
    # If insert() were used twice it would accumulate; _set_raw replaces without combining.
    poly_rel._set_raw(("Alice",), t1)
    assert poly_rel._data[("Alice",)] == t1
    assert poly_rel.support_size() == 1


def test_set_raw_overwrites_existing(nat_rel):
    """TK-18: _set_raw() unconditionally overwrites any prior annotation."""
    nat_rel.insert({"Name": "Alice"}, annotation=10)
    nat_rel._set_raw(("Alice",), 99)  # overwrites 10, does not add
    assert nat_rel.annotation_of(Name="Alice") == 99


# ──────────────────────────────────────────────────────────────────────
# TK-19 to TK-20: pretty() / __repr__()
# ──────────────────────────────────────────────────────────────────────

def test_pretty_contains_schema_and_semiring(bool_rel):
    """TK-19: pretty() output includes the schema and semiring name."""
    bool_rel.insert({"Name": "Alice", "Dept": "Eng"})
    output = bool_rel.pretty("Test Title")
    assert "Test Title" in output
    assert "Name" in output
    assert "Dept" in output
    assert bool_rel.semiring.name in output


def test_repr_contains_key_info(bool_rel):
    """TK-20: __repr__() includes class name, schema, semiring name, and support_size."""
    bool_rel.insert({"Name": "Alice", "Dept": "Eng"})
    r = repr(bool_rel)
    assert "KRelation" in r
    assert "Name" in r
    assert "Dept" in r
    assert "support_size" in r
    assert "1" in r  # one row in support
