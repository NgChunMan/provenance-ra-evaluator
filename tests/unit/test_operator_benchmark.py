"""Tests for Benchmark C: per-operator isolated provenance overhead benchmarks.

These tests verify:
  - Each workload returns a correctly typed OperatorBenchmarkRow
  - input_rows and output_rows match the design contracts
  - clause_count and literal_count match operator semantics exactly
  - overhead_x is computed as boolfunc_us / bool_us
  - Deduplication variant labels are correct
  - EXISTENCE collapses BoolFunc annotations to ⊤ (0 literals)
  - HOW_PROVENANCE preserves BoolFunc annotations unchanged
  - The full suite runner returns 6 rows in the expected order

All workloads run with repeat=1, warmup=0 to keep tests fast.
"""

from __future__ import annotations

import pytest

from benchmarks._common import OperatorBenchmarkRow
from benchmarks._operator import (
    _bench_cross_product,
    _bench_deduplication,
    _bench_multiset_sum,
    _bench_projection,
    _bench_selection,
    _benchmark_operator_workloads,
)
from src.strategies import DedupStrategy

# Shared fast settings: 1 timed repetition, no warmup.
_FAST = {"repeat": 1, "warmup": 0}
_SIZE = 10


# ---------------------------------------------------------------------------
# σ (Selection)
# ---------------------------------------------------------------------------

class TestBenchSelection:
    def test_returns_operator_benchmark_row(self):
        row = _bench_selection(_SIZE, **_FAST)
        assert isinstance(row, OperatorBenchmarkRow)

    def test_operator_name(self):
        row = _bench_selection(_SIZE, **_FAST)
        assert "Selection" in row.operator
        assert "σ" in row.operator

    def test_variant_is_none(self):
        row = _bench_selection(_SIZE, **_FAST)
        assert row.variant is None

    def test_input_rows(self):
        row = _bench_selection(10, **_FAST)
        assert row.input_rows == 10

    def test_output_rows_one_in_five(self):
        # Predicate ID % 5 == 0: with 10 rows, IDs 0 and 5 pass → 2 rows.
        row = _bench_selection(10, **_FAST)
        assert row.output_rows == 2

    def test_output_rows_scales_with_size(self):
        # size=20: IDs 0,5,10,15 pass → 4 rows.
        row = _bench_selection(20, **_FAST)
        assert row.output_rows == 4

    def test_no_annotation_merging_clause_count(self):
        # Selection never calls add() — each output keeps its single-variable
        # original BoolFunc: 1 clause and 1 literal per output row.
        row = _bench_selection(10, **_FAST)
        assert row.clause_count == row.output_rows
        assert row.literal_count == row.output_rows

    def test_timing_positive(self):
        row = _bench_selection(_SIZE, **_FAST)
        assert row.bool_us > 0
        assert row.boolfunc_us > 0

    def test_overhead_consistent_with_timings(self):
        row = _bench_selection(_SIZE, **_FAST)
        expected = row.boolfunc_us / row.bool_us
        assert abs(row.overhead_x - expected) < 1e-9


# ---------------------------------------------------------------------------
# π (Projection, no collision)
# ---------------------------------------------------------------------------

class TestBenchProjection:
    def test_returns_operator_benchmark_row(self):
        row = _bench_projection(_SIZE, **_FAST)
        assert isinstance(row, OperatorBenchmarkRow)

    def test_operator_name(self):
        row = _bench_projection(_SIZE, **_FAST)
        assert "Projection" in row.operator
        assert "π" in row.operator

    def test_variant_is_none(self):
        row = _bench_projection(_SIZE, **_FAST)
        assert row.variant is None

    def test_input_equals_output_no_collision(self):
        # All projected IDs are distinct → no add() called → input == output.
        row = _bench_projection(10, **_FAST)
        assert row.input_rows == 10
        assert row.output_rows == 10

    def test_no_annotation_merging_clause_count(self):
        # No key collisions → annotations pass through as single-variable BoolFuncs.
        row = _bench_projection(10, **_FAST)
        assert row.clause_count == 10    # one clause per output row
        assert row.literal_count == 10   # one literal per clause

    def test_timing_positive(self):
        row = _bench_projection(_SIZE, **_FAST)
        assert row.bool_us > 0
        assert row.boolfunc_us > 0

    def test_overhead_consistent_with_timings(self):
        row = _bench_projection(_SIZE, **_FAST)
        expected = row.boolfunc_us / row.bool_us
        assert abs(row.overhead_x - expected) < 1e-9


# ---------------------------------------------------------------------------
# × (Cross Product)
# ---------------------------------------------------------------------------

class TestBenchCrossProduct:
    def test_returns_operator_benchmark_row(self):
        row = _bench_cross_product(5, 10, **_FAST)
        assert isinstance(row, OperatorBenchmarkRow)

    def test_operator_name(self):
        row = _bench_cross_product(5, 10, **_FAST)
        assert "Cross Product" in row.operator
        assert "×" in row.operator

    def test_variant_is_none(self):
        row = _bench_cross_product(5, 10, **_FAST)
        assert row.variant is None

    def test_input_rows_is_sum(self):
        # input_rows = left + right = 5 + 10 = 15.
        row = _bench_cross_product(5, 10, **_FAST)
        assert row.input_rows == 15

    def test_output_rows_is_product(self):
        # 5 × 10 = 50 output pairs.
        row = _bench_cross_product(5, 10, **_FAST)
        assert row.output_rows == 50

    def test_each_pair_is_single_two_literal_clause(self):
        # mul(cp_l_i, cp_r_j) = {frozenset({"cp_l_i", "cp_r_j"})}:
        # 1 clause per pair × 2 literals per clause.
        row = _bench_cross_product(5, 10, **_FAST)
        assert row.clause_count == 50
        assert row.literal_count == 100

    def test_different_sizes(self):
        row = _bench_cross_product(3, 4, **_FAST)
        assert row.input_rows == 7
        assert row.output_rows == 12
        assert row.clause_count == 12
        assert row.literal_count == 24

    def test_timing_positive(self):
        row = _bench_cross_product(5, 10, **_FAST)
        assert row.bool_us > 0
        assert row.boolfunc_us > 0

    def test_overhead_consistent_with_timings(self):
        row = _bench_cross_product(5, 10, **_FAST)
        expected = row.boolfunc_us / row.bool_us
        assert abs(row.overhead_x - expected) < 1e-9


# ---------------------------------------------------------------------------
# ⊎ (Multiset Sum)
# ---------------------------------------------------------------------------

class TestBenchMultisetSum:
    def test_returns_operator_benchmark_row(self):
        row = _bench_multiset_sum(_SIZE, **_FAST)
        assert isinstance(row, OperatorBenchmarkRow)

    def test_operator_name(self):
        row = _bench_multiset_sum(_SIZE, **_FAST)
        assert "Multiset Sum" in row.operator
        assert "⊎" in row.operator

    def test_variant_is_none(self):
        row = _bench_multiset_sum(_SIZE, **_FAST)
        assert row.variant is None

    def test_complete_key_overlap(self):
        # Both relations share keys 0..size-1 → output has size rows.
        row = _bench_multiset_sum(10, **_FAST)
        assert row.input_rows == 20   # 10 + 10
        assert row.output_rows == 10

    def test_disjunction_forms_two_clause_formula(self):
        # add(sl_i, sr_i) = sl_i ∨ sr_i: 2 clauses × 1 literal each.
        row = _bench_multiset_sum(10, **_FAST)
        assert row.clause_count == 20     # 2 clauses × 10 output rows
        assert row.literal_count == 20    # 1 literal × 2 clauses × 10 rows

    def test_timing_positive(self):
        row = _bench_multiset_sum(_SIZE, **_FAST)
        assert row.bool_us > 0
        assert row.boolfunc_us > 0

    def test_overhead_consistent_with_timings(self):
        row = _bench_multiset_sum(_SIZE, **_FAST)
        expected = row.boolfunc_us / row.bool_us
        assert abs(row.overhead_x - expected) < 1e-9


# ---------------------------------------------------------------------------
# δ (Deduplication) — EXISTENCE
# ---------------------------------------------------------------------------

class TestBenchDeduplicationExistence:
    def _row(self, size: int = 10) -> OperatorBenchmarkRow:
        return _bench_deduplication(size, repeat=1, warmup=0, strategy=DedupStrategy.EXISTENCE)

    def test_returns_operator_benchmark_row(self):
        assert isinstance(self._row(), OperatorBenchmarkRow)

    def test_operator_and_variant(self):
        row = self._row()
        assert "Deduplication" in row.operator
        assert "δ" in row.operator
        assert row.variant == "existence"

    def test_input_output_rows(self):
        row = self._row(10)
        assert row.input_rows == 10
        assert row.output_rows == 10    # all rows non-zero → all survive

    def test_existence_collapses_to_top(self):
        # EXISTENCE replaces each 2-clause formula with ⊤ = one empty clause.
        # one() = frozenset([frozenset()]) → 1 clause with 0 literals per row.
        row = self._row(10)
        assert row.clause_count == 10   # one empty clause per output row
        assert row.literal_count == 0   # empty clause has no literals

    def test_timing_positive(self):
        row = self._row()
        assert row.bool_us > 0
        assert row.boolfunc_us > 0

    def test_overhead_consistent_with_timings(self):
        row = self._row()
        expected = row.boolfunc_us / row.bool_us
        assert abs(row.overhead_x - expected) < 1e-9


# ---------------------------------------------------------------------------
# δ (Deduplication) — HOW_PROVENANCE
# ---------------------------------------------------------------------------

class TestBenchDeduplicationHowProvenance:
    def _row(self, size: int = 10) -> OperatorBenchmarkRow:
        return _bench_deduplication(size, repeat=1, warmup=0, strategy=DedupStrategy.HOW_PROVENANCE)

    def test_returns_operator_benchmark_row(self):
        assert isinstance(self._row(), OperatorBenchmarkRow)

    def test_operator_and_variant(self):
        row = self._row()
        assert "Deduplication" in row.operator
        assert "δ" in row.operator
        assert row.variant == "how_provenance"

    def test_input_output_rows(self):
        row = self._row(10)
        assert row.input_rows == 10
        assert row.output_rows == 10

    def test_how_provenance_preserves_annotations(self):
        # Input: 2-clause formula (da_i ∨ db_i) per row.
        # HOW_PROVENANCE passes them through unchanged.
        row = self._row(10)
        assert row.clause_count == 20    # 2 clauses × 10 rows
        assert row.literal_count == 20   # 1 literal per clause

    def test_timing_positive(self):
        row = self._row()
        assert row.bool_us > 0
        assert row.boolfunc_us > 0

    def test_overhead_consistent_with_timings(self):
        row = self._row()
        expected = row.boolfunc_us / row.bool_us
        assert abs(row.overhead_x - expected) < 1e-9


# ---------------------------------------------------------------------------
# Full suite runner
# ---------------------------------------------------------------------------

class TestBenchmarkOperatorWorkloads:
    def _suite(self, size: int = 10) -> list[OperatorBenchmarkRow]:
        return _benchmark_operator_workloads(size, repeat=1, warmup=0)

    def test_returns_six_rows(self):
        rows = self._suite()
        assert len(rows) == 6

    def test_paper_order(self):
        # Order must match paper Table 3: σ, π, ×, ⊎, δ-exist, δ-how.
        rows = self._suite()
        assert "σ" in rows[0].operator
        assert "π" in rows[1].operator
        assert "×" in rows[2].operator
        assert "⊎" in rows[3].operator
        assert "δ" in rows[4].operator and rows[4].variant == "existence"
        assert "δ" in rows[5].operator and rows[5].variant == "how_provenance"

    def test_all_operators_present(self):
        rows = self._suite()
        operators = {row.operator for row in rows}
        assert any("Selection" in op for op in operators)
        assert any("Projection" in op for op in operators)
        assert any("Cross Product" in op for op in operators)
        assert any("Multiset Sum" in op for op in operators)
        assert any("Deduplication" in op for op in operators)

    def test_exactly_two_dedup_strategies(self):
        rows = self._suite()
        dedup_rows = [r for r in rows if "Deduplication" in r.operator]
        assert len(dedup_rows) == 2
        variants = {r.variant for r in dedup_rows}
        assert variants == {"existence", "how_provenance"}

    def test_all_rows_typed(self):
        for row in self._suite():
            assert isinstance(row, OperatorBenchmarkRow)

    def test_all_timings_positive(self):
        for row in self._suite():
            assert row.bool_us > 0, f"{row.operator}: bool_us should be > 0"
            assert row.boolfunc_us > 0, f"{row.operator}: boolfunc_us should be > 0"

    def test_all_overhead_positive(self):
        for row in self._suite():
            assert row.overhead_x > 0, f"{row.operator}: overhead_x should be > 0"

    def test_cross_product_sizes_at_default_10(self):
        # left_size = 10 // 2 = 5, right = 10 → output = 50.
        rows = self._suite(size=10)
        cross_row = next(r for r in rows if "Cross Product" in r.operator)
        assert cross_row.input_rows == 15    # 5 + 10
        assert cross_row.output_rows == 50   # 5 × 10

    def test_raises_on_size_less_than_2(self):
        with pytest.raises(ValueError, match="operator_size must be at least 2"):
            _benchmark_operator_workloads(1, repeat=1, warmup=0)

    def test_dedup_existence_has_zero_literals(self):
        rows = self._suite()
        exist_row = next(r for r in rows if r.variant == "existence")
        assert exist_row.literal_count == 0

    def test_dedup_how_prov_has_nonzero_literals(self):
        rows = self._suite()
        how_row = next(r for r in rows if r.variant == "how_provenance")
        assert how_row.literal_count > 0
