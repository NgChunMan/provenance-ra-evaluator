"""Tests for the dedup downstream workloads added to Benchmark D.

These two workloads exist to demonstrate that HOW_PROVENANCE's extra cost
is NOT in the deduplication operator itself, but in subsequent operators
that receive and process the retained annotations.

Design contracts verified here:
  dedup_existence_downstream:
    - δ EXISTENCE collapses every formula to ⊤ before the cross product
    - mul(⊤, var_j) = var_j  →  1 clause, 1 literal per output pair
    - clause_count == output_rows == dd_size²
    - literal_count == dd_size²

  dedup_howprov_downstream:
    - δ HOW_PROV retains each formula_width-clause formula intact
    - mul(formula_width-clause formula, var_j) → formula_width 2-literal
      clauses per output pair
    - clause_count  == dd_size² × formula_width
    - literal_count == dd_size² × formula_width × 2

Comparing the two workloads directly gives the downstream cost of
choosing HOW_PROVENANCE instead of EXISTENCE — the only structural
difference is the strategy passed to δ.
"""

from __future__ import annotations

import pytest

from benchmarks._common import MicroBenchmarkRow
from benchmarks._micro import (
    _bench_dedup_existence_downstream,
    _bench_dedup_howprov_downstream,
)

_FAST = {"repeat": 1, "warmup": 0}


# ---------------------------------------------------------------------------
# dedup_existence_downstream
# ---------------------------------------------------------------------------

class TestDedupExistenceDownstream:
    def test_returns_micro_benchmark_row(self):
        row = _bench_dedup_existence_downstream(4, 8, **_FAST)
        assert isinstance(row, MicroBenchmarkRow)

    def test_name(self):
        row = _bench_dedup_existence_downstream(4, 8, **_FAST)
        assert row.name == "dedup_existence_downstream"

    def test_output_rows_is_cross_product_count(self):
        # dd_size=4 left × dd_size=4 right → 16 pairs
        row = _bench_dedup_existence_downstream(4, 8, **_FAST)
        assert row.output_rows == 16

    def test_existence_collapses_formula_before_cross(self):
        # ⊤ ∧ var(j) = var(j): 1 clause, 1 literal per output pair.
        # clause_count and literal_count both == dd_size².
        row = _bench_dedup_existence_downstream(4, 8, **_FAST)
        assert row.clause_count == 16   # 1 clause × 16 pairs
        assert row.literal_count == 16  # 1 literal × 16 pairs

    def test_clause_count_equals_output_rows(self):
        # The key property: existence downstream has no annotation growth.
        for dd_size in (4, 6, 8):
            row = _bench_dedup_existence_downstream(dd_size, 16, **_FAST)
            assert row.clause_count == row.output_rows, (
                f"dd_size={dd_size}: clause_count should equal output_rows"
            )

    def test_clause_count_independent_of_formula_width(self):
        # EXISTENCE discards the formula_width-clause formula before the cross.
        # Clause count must be the same for formula_width=4 and formula_width=48.
        row4 = _bench_dedup_existence_downstream(4, 4, **_FAST)
        row48 = _bench_dedup_existence_downstream(4, 48, **_FAST)
        assert row4.clause_count == row48.clause_count

    def test_timing_positive(self):
        row = _bench_dedup_existence_downstream(4, 8, **_FAST)
        assert row.nat_ms > 0
        assert row.boolfunc_ms > 0

    def test_overhead_consistent_with_timings(self):
        row = _bench_dedup_existence_downstream(4, 8, **_FAST)
        expected = row.boolfunc_ms / row.nat_ms
        assert abs(row.overhead_x - expected) < 1e-9


# ---------------------------------------------------------------------------
# dedup_howprov_downstream
# ---------------------------------------------------------------------------

class TestDedupHowprovDownstream:
    def test_returns_micro_benchmark_row(self):
        row = _bench_dedup_howprov_downstream(4, 8, **_FAST)
        assert isinstance(row, MicroBenchmarkRow)

    def test_name(self):
        row = _bench_dedup_howprov_downstream(4, 8, **_FAST)
        assert row.name == "dedup_howprov_downstream"

    def test_output_rows_is_cross_product_count(self):
        row = _bench_dedup_howprov_downstream(4, 8, **_FAST)
        assert row.output_rows == 16  # 4×4 pairs

    def test_howprov_retains_formula_through_dedup(self):
        # mul(8-clause formula, var_j) → 8 two-literal clauses per pair.
        # dd_size=4: 16 pairs × 8 clauses × 2 literals.
        row = _bench_dedup_howprov_downstream(4, 8, **_FAST)
        assert row.clause_count == 128   # 16 pairs × 8 clauses
        assert row.literal_count == 256  # 128 clauses × 2 literals

    def test_clause_count_formula_is_pairs_times_width(self):
        # clause_count == dd_size² × formula_width exactly.
        for dd_size, fw in ((4, 4), (4, 12), (6, 8)):
            row = _bench_dedup_howprov_downstream(dd_size, fw, **_FAST)
            expected_clauses = (dd_size * dd_size) * fw
            expected_literals = expected_clauses * 2
            assert row.clause_count == expected_clauses, (
                f"dd_size={dd_size}, fw={fw}: got {row.clause_count}, want {expected_clauses}"
            )
            assert row.literal_count == expected_literals, (
                f"dd_size={dd_size}, fw={fw}: got {row.literal_count}, want {expected_literals}"
            )

    def test_clause_count_scales_with_formula_width(self):
        # Doubling formula_width doubles the clause count.
        row_fw4 = _bench_dedup_howprov_downstream(4, 4, **_FAST)
        row_fw8 = _bench_dedup_howprov_downstream(4, 8, **_FAST)
        assert row_fw8.clause_count == 2 * row_fw4.clause_count

    def test_clause_count_scales_with_dd_size(self):
        # (dd_size × 2)² = 4 × dd_size² → 4× more output pairs → 4× clause count.
        row_s4 = _bench_dedup_howprov_downstream(4, 8, **_FAST)
        row_s8 = _bench_dedup_howprov_downstream(8, 8, **_FAST)
        assert row_s8.clause_count == 4 * row_s4.clause_count

    def test_timing_positive(self):
        row = _bench_dedup_howprov_downstream(4, 8, **_FAST)
        assert row.nat_ms > 0
        assert row.boolfunc_ms > 0

    def test_overhead_consistent_with_timings(self):
        row = _bench_dedup_howprov_downstream(4, 8, **_FAST)
        expected = row.boolfunc_ms / row.nat_ms
        assert abs(row.overhead_x - expected) < 1e-9


# ---------------------------------------------------------------------------
# Head-to-head comparison: isolates the downstream cost of HOW_PROV
# ---------------------------------------------------------------------------

class TestDownstreamStrategyComparison:
    """Compare existence vs howprov downstream directly.

    The two workloads are structurally identical except for the dedup
    strategy.  Any difference in clause_count or boolfunc_ms is caused
    solely by the downstream effect of HOW_PROV retaining large formulas.
    """

    def test_howprov_has_formula_width_times_more_clauses(self):
        # Existence: 1 clause per pair.  HOW_PROV: formula_width clauses per pair.
        formula_width = 8
        exist_row = _bench_dedup_existence_downstream(4, formula_width, **_FAST)
        howprov_row = _bench_dedup_howprov_downstream(4, formula_width, **_FAST)
        assert howprov_row.clause_count == formula_width * exist_row.clause_count

    def test_howprov_has_double_literals_per_clause(self):
        # Existence: 1-literal clauses.  HOW_PROV: 2-literal clauses per pair.
        # So literal ratio == 2 × clause ratio.
        formula_width = 8
        exist_row = _bench_dedup_existence_downstream(4, formula_width, **_FAST)
        howprov_row = _bench_dedup_howprov_downstream(4, formula_width, **_FAST)
        assert howprov_row.literal_count == 2 * formula_width * exist_row.literal_count

    def test_same_output_row_count(self):
        # Both use the same dd_size — the number of output pairs is equal.
        exist_row = _bench_dedup_existence_downstream(4, 8, **_FAST)
        howprov_row = _bench_dedup_howprov_downstream(4, 8, **_FAST)
        assert exist_row.output_rows == howprov_row.output_rows

    def test_existence_has_zero_annotation_growth(self):
        # Existence: clause_count == output_rows (exactly 1 clause per pair).
        exist_row = _bench_dedup_existence_downstream(4, 8, **_FAST)
        assert exist_row.clause_count == exist_row.output_rows

    def test_howprov_boolfunc_time_exceeds_existence_boolfunc_time(self):
        # With formula_width=16 the HOW_PROV downstream must process 16×
        # more clauses per pair — BoolFunc time should be clearly higher.
        # We use repeat=3 for a more stable signal.
        exist_row = _bench_dedup_existence_downstream(8, 16, repeat=3, warmup=1)
        howprov_row = _bench_dedup_howprov_downstream(8, 16, repeat=3, warmup=1)
        assert howprov_row.boolfunc_ms > exist_row.boolfunc_ms, (
            "HOW_PROV downstream should be slower than EXISTENCE downstream "
            f"(got existence={exist_row.boolfunc_ms:.4f}ms, "
            f"howprov={howprov_row.boolfunc_ms:.4f}ms)"
        )
