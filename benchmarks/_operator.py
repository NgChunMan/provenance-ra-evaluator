"""Per-operator isolated provenance overhead benchmarks (Benchmark C).

Each workload runs exactly one relational operator in isolation on a small
synthetic K-relation, comparing:

  Baseline : BOOL_SR  — Boolean / set semantics (True/False annotations)
  Provenance: BOOLFUNC_SR — positive Boolean formulas in DNF

The six workloads correspond to Table 3 in the paper:
  σ  (Selection)        — filters rows; annotations are never combined
  π  (Projection)       — drops a column; here all projected keys are distinct
                           so add() is never called (the add-heavy case is in
                           Benchmark D: projection_collision)
  ×  (Cross Product)    — all pairs; each pair calls mul() once
  ⊎  (Multiset Sum)     — complete overlap; each output calls add() once
  δ  EXISTENCE          — collapses every BoolFunc annotation to ⊤
  δ  HOW_PROVENANCE     — passes each annotation through unchanged

Design contract
---------------
Synthetic relations are built OUTSIDE the timed region.  Only the operator
call itself is measured.  This rules out CSV loading, annotation assignment,
and Python's object construction from affecting the per-operator numbers.

Timing unit: microseconds (μs).  The _measure() helper returns milliseconds;
we multiply by 1 000 before storing results.

Default sizes (--operator-size 10)
-----------------------------------
  σ  : 10 rows in, predicate ID%5==0 → 2 rows out
  π  : 10 rows in (ID unique after projection) → 10 rows out
  ×  : A(5) × B(10) → 50 pairs — left_size = operator_size // 2
  ⊎  : A(10) ⊎ B(10) complete overlap → 10 rows out
  δ  : 10 rows in → 10 rows out (all non-zero, strategies differ on annotation)

The cross-product left_size = operator_size // 2 is chosen so that
left × right = (size // 2) × size pairs, which equals 50 at the default
size of 10, matching the paper's "In: 50, Out: 50" cross-product numbers.
"""

from __future__ import annotations

import statistics

from src.operators.cross_product import cross_product
from src.operators.deduplication import deduplication
from src.operators.multiset_sum import multiset_sum
from src.operators.projection import projection
from src.operators.selection import selection
from src.relation.k_relation import KRelation
from src.semirings import BOOL_SR, BOOLFUNC_SR, BoolFunc
from src.strategies import DedupStrategy

from ._common import OperatorBenchmarkRow, _boolfunc_complexity, _measure


# ---------------------------------------------------------------------------
# Internal relation builders
# ---------------------------------------------------------------------------

def _bool_relation(schema: list[str], size: int, key_fn) -> KRelation:
    """Return a BOOL_SR relation with *size* rows; every annotation is True."""
    rel = KRelation(schema, BOOL_SR)
    for i in range(size):
        rel._set_raw(key_fn(i), BOOL_SR.one())
    return rel


def _bf_relation(schema: list[str], size: int, key_fn, prefix: str) -> KRelation:
    """Return a BOOLFUNC_SR relation; row i is annotated with BoolFunc.var(prefix+i)."""
    rel = KRelation(schema, BOOLFUNC_SR)
    for i in range(size):
        rel._set_raw(key_fn(i), BoolFunc.var(f"{prefix}{i}"))
    return rel


# ---------------------------------------------------------------------------
# Per-operator workload functions
# ---------------------------------------------------------------------------

def _bench_selection(size: int, repeat: int, warmup: int) -> OperatorBenchmarkRow:
    """σ (Selection): filter *size* rows; predicate retains 1 in 5.

    Predicate: ID % 5 == 0.  With size=10 → IDs 0 and 5 pass → 2 output rows.
    Annotations are never combined (no add() or mul()), so the annotation
    overhead over BOOL_SR is just the cost of carrying a BoolFunc object.
    """
    bool_rel = _bool_relation(["ID"], size, lambda i: (i,))
    bf_rel = _bf_relation(["ID"], size, lambda i: (i,), "sel")
    predicate = lambda row: row["ID"] % 5 == 0

    bool_samples, _ = _measure(lambda: selection(bool_rel, predicate), repeat, warmup)
    bf_samples, bf_result = _measure(lambda: selection(bf_rel, predicate), repeat, warmup)

    bool_us = statistics.median(bool_samples) * 1_000
    bf_us = statistics.median(bf_samples) * 1_000
    clause_count, literal_count = _boolfunc_complexity(bf_result)

    return OperatorBenchmarkRow(
        operator="σ (Selection)",
        variant=None,
        bool_us=bool_us,
        boolfunc_us=bf_us,
        overhead_x=bf_us / bool_us if bool_us > 0 else float("inf"),
        input_rows=size,
        output_rows=bf_result.support_size(),
        clause_count=clause_count,
        literal_count=literal_count,
        description=(
            f"{size} input rows; predicate ID%%5==0 retains 1 in 5 tuples. "
            "Annotations are copied unchanged — add() and mul() are never called."
        ),
    )


def _bench_projection(size: int, repeat: int, warmup: int) -> OperatorBenchmarkRow:
    """π (Projection): project *size* rows; all projected keys are distinct.

    Input schema is [ID, Extra]; projection drops Extra.  Because every ID is
    unique, no two rows share a projected key, so add() is never called and
    annotations pass through exactly as in selection.  This workload isolates
    the pure per-tuple cost of the projection loop.
    """
    bool_rel = _bool_relation(["ID", "Extra"], size, lambda i: (i, i))
    bf_rel = _bf_relation(["ID", "Extra"], size, lambda i: (i, i), "pi")

    bool_samples, _ = _measure(lambda: projection(bool_rel, ["ID"]), repeat, warmup)
    bf_samples, bf_result = _measure(lambda: projection(bf_rel, ["ID"]), repeat, warmup)

    bool_us = statistics.median(bool_samples) * 1_000
    bf_us = statistics.median(bf_samples) * 1_000
    clause_count, literal_count = _boolfunc_complexity(bf_result)

    return OperatorBenchmarkRow(
        operator="π (Projection)",
        variant=None,
        bool_us=bool_us,
        boolfunc_us=bf_us,
        overhead_x=bf_us / bool_us if bool_us > 0 else float("inf"),
        input_rows=size,
        output_rows=bf_result.support_size(),
        clause_count=clause_count,
        literal_count=literal_count,
        description=(
            f"{size} rows projected to distinct IDs — no key collisions, "
            "so add() is never called and annotations pass through unchanged."
        ),
    )


def _bench_cross_product(
    left_size: int,
    right_size: int,
    repeat: int,
    warmup: int,
) -> OperatorBenchmarkRow:
    """× (Cross Product): full Cartesian A × B.

    With the default left_size=5, right_size=10 → 50 output pairs.
    Each pair calls mul() once.  In BOOLFUNC_SR, multiplying two
    singleton-variable formulas produces a single 2-literal clause,
    so clause_count == output_pairs and literal_count == 2 * output_pairs.
    """
    bool_left = _bool_relation(["L"], left_size, lambda i: (i,))
    bool_right = _bool_relation(["R"], right_size, lambda i: (i,))
    bf_left = _bf_relation(["L"], left_size, lambda i: (i,), "cp_l")
    bf_right = _bf_relation(["R"], right_size, lambda i: (i,), "cp_r")

    bool_samples, _ = _measure(
        lambda: cross_product(bool_left, bool_right), repeat, warmup
    )
    bf_samples, bf_result = _measure(
        lambda: cross_product(bf_left, bf_right), repeat, warmup
    )

    bool_us = statistics.median(bool_samples) * 1_000
    bf_us = statistics.median(bf_samples) * 1_000
    clause_count, literal_count = _boolfunc_complexity(bf_result)
    output_pairs = left_size * right_size

    return OperatorBenchmarkRow(
        operator="× (Cross Product)",
        variant=None,
        bool_us=bool_us,
        boolfunc_us=bf_us,
        overhead_x=bf_us / bool_us if bool_us > 0 else float("inf"),
        input_rows=left_size + right_size,
        output_rows=bf_result.support_size(),
        clause_count=clause_count,
        literal_count=literal_count,
        description=(
            f"{left_size}×{right_size} cross product → {output_pairs} pairs. "
            "Each pair calls mul() once; two singleton formulas conjoin into "
            "a single 2-literal clause."
        ),
    )


def _bench_multiset_sum(size: int, repeat: int, warmup: int) -> OperatorBenchmarkRow:
    """⊎ (Multiset Sum): two *size*-row relations with complete key overlap.

    Both relations share the same keys 0..size-1, so every key appears in
    both and triggers one add() call in BOOLFUNC_SR.  add() forms the
    disjunction sl_i ∨ sr_i: each output tuple gets a 2-clause formula,
    giving clause_count == 2*size and literal_count == 2*size.
    """
    bool_left = _bool_relation(["Key"], size, lambda i: (i,))
    bool_right = _bool_relation(["Key"], size, lambda i: (i,))
    bf_left = _bf_relation(["Key"], size, lambda i: (i,), "sl")
    bf_right = _bf_relation(["Key"], size, lambda i: (i,), "sr")

    bool_samples, _ = _measure(
        lambda: multiset_sum(bool_left, bool_right), repeat, warmup
    )
    bf_samples, bf_result = _measure(
        lambda: multiset_sum(bf_left, bf_right), repeat, warmup
    )

    bool_us = statistics.median(bool_samples) * 1_000
    bf_us = statistics.median(bf_samples) * 1_000
    clause_count, literal_count = _boolfunc_complexity(bf_result)

    return OperatorBenchmarkRow(
        operator="⊎ (Multiset Sum)",
        variant=None,
        bool_us=bool_us,
        boolfunc_us=bf_us,
        overhead_x=bf_us / bool_us if bool_us > 0 else float("inf"),
        input_rows=size + size,
        output_rows=bf_result.support_size(),
        clause_count=clause_count,
        literal_count=literal_count,
        description=(
            f"Two {size}-row relations with complete key overlap. "
            "Each output calls add() once, forming a 2-clause disjunction (sl_i ∨ sr_i)."
        ),
    )


def _bench_deduplication(
    size: int,
    repeat: int,
    warmup: int,
    strategy: DedupStrategy,
) -> OperatorBenchmarkRow:
    """δ (Deduplication): deduplicate *size* rows, each with a 2-clause BoolFunc.

    The input relation is pre-built OUTSIDE the timed region so that only the
    deduplication call itself is measured.

    Each BOOLFUNC_SR input annotation is (da_i ∨ db_i) — a 2-clause disjunction
    modelling a tuple derived from two alternative witnesses.

    EXISTENCE replaces every formula with ⊤ (= BOOLFUNC_SR.one() = one empty
    clause), discarding provenance.  HOW_PROVENANCE leaves each formula unchanged.

    For BOOL_SR, both strategies are essentially a no-op (True → True), so the
    baseline is flat and the overhead reflects only BoolFunc manipulation.
    """
    # Pre-build relations outside the timed region.
    bool_rel = KRelation(["ID"], BOOL_SR)
    for i in range(size):
        bool_rel._set_raw((i,), BOOL_SR.one())

    bf_rel = KRelation(["ID"], BOOLFUNC_SR)
    for i in range(size):
        # 2-clause pre-built disjunction: da_i ∨ db_i
        formula = BOOLFUNC_SR.add(BoolFunc.var(f"da{i}"), BoolFunc.var(f"db{i}"))
        bf_rel._set_raw((i,), formula)

    variant_name = (
        "existence" if strategy == DedupStrategy.EXISTENCE else "how_provenance"
    )

    bool_samples, _ = _measure(
        lambda: deduplication(bool_rel, strategy), repeat, warmup
    )
    bf_samples, bf_result = _measure(
        lambda: deduplication(bf_rel, strategy), repeat, warmup
    )

    bool_us = statistics.median(bool_samples) * 1_000
    bf_us = statistics.median(bf_samples) * 1_000
    clause_count, literal_count = _boolfunc_complexity(bf_result)

    if strategy == DedupStrategy.EXISTENCE:
        annotation_note = (
            "EXISTENCE collapses each 2-clause formula to ⊤ "
            "(one empty clause, 0 literals — provenance discarded)."
        )
    else:
        annotation_note = (
            "HOW_PROVENANCE passes each 2-clause formula through unchanged "
            "(2 clauses × 1 literal each — provenance preserved)."
        )

    return OperatorBenchmarkRow(
        operator="δ (Deduplication)",
        variant=variant_name,
        bool_us=bool_us,
        boolfunc_us=bf_us,
        overhead_x=bf_us / bool_us if bool_us > 0 else float("inf"),
        input_rows=size,
        output_rows=bf_result.support_size(),
        clause_count=clause_count,
        literal_count=literal_count,
        description=(
            f"{size} rows with pre-built 2-clause BoolFunc annotations. "
            f"{annotation_note}"
        ),
    )


# ---------------------------------------------------------------------------
# Suite runner
# ---------------------------------------------------------------------------

def _benchmark_operator_workloads(
    operator_size: int,
    repeat: int,
    warmup: int,
) -> list[OperatorBenchmarkRow]:
    """Run all six per-operator benchmarks and return results in paper order.

    Parameters
    ----------
    operator_size:
        Number of rows per input relation.  Default 10 reproduces the
        "10 rows/table" setup of the paper's Table 3.  The cross-product
        left relation uses operator_size // 2 rows so that the output has
        (operator_size // 2) × operator_size pairs (50 at the default of 10).
    repeat:
        Timed repetitions per workload (median is reported).
    warmup:
        Untimed warm-up runs before timing begins.
    """
    if operator_size < 2:
        raise ValueError("operator_size must be at least 2 (cross product needs left_size >= 1).")

    left_size = max(1, operator_size // 2)
    rows: list[OperatorBenchmarkRow] = []

    rows.append(_bench_selection(operator_size, repeat, warmup))
    rows.append(_bench_projection(operator_size, repeat, warmup))
    rows.append(_bench_cross_product(left_size, operator_size, repeat, warmup))
    rows.append(_bench_multiset_sum(operator_size, repeat, warmup))
    rows.append(
        _bench_deduplication(operator_size, repeat, warmup, DedupStrategy.EXISTENCE)
    )
    rows.append(
        _bench_deduplication(operator_size, repeat, warmup, DedupStrategy.HOW_PROVENANCE)
    )

    return rows


# ---------------------------------------------------------------------------
# Pretty printer
# ---------------------------------------------------------------------------

def _print_operator_benchmark_rows(
    rows: list[OperatorBenchmarkRow],
    repeat: int = 7,
    warmup: int = 1,
) -> None:
    """Print Benchmark C results in a formatted table."""
    print()
    print("=" * 110)
    print("BENCHMARK C — PER-OPERATOR MICROBENCHMARKS")
    print("=" * 110)
    print("Baseline : BOOL_SR    (Boolean / set semantics — True/False annotations)")
    print("Provenance: BOOLFUNC_SR (positive Boolean formulas in DNF, one variable per base tuple)")
    print(f"Timing   : median of {repeat} timed run(s) after {warmup} warmup, GC disabled. Unit: microseconds (μs).")
    print()

    # Header
    op_w, var_w = 20, 14
    header = (
        f"{'Operator':<{op_w}}"
        f"{'Variant':<{var_w}}"
        f"{'BOOL μs':>10}"
        f"{'BoolFunc μs':>13}"
        f"{'Overhead':>11}"
        f"{'In':>6}"
        f"{'Out':>6}"
        f"{'Clauses':>9}"
        f"{'Literals':>10}"
    )
    print(header)
    print("-" * len(header))

    for row in rows:
        variant_str = row.variant if row.variant is not None else ""
        overhead_str = (
            f"{row.overhead_x:.2f}x"
            if row.overhead_x != float("inf")
            else "inf"
        )
        print(
            f"{row.operator:<{op_w}}"
            f"{variant_str:<{var_w}}"
            f"{row.bool_us:>10.1f}"
            f"{row.boolfunc_us:>13.1f}"
            f"{overhead_str:>11}"
            f"{row.input_rows:>6}"
            f"{row.output_rows:>6}"
            f"{row.clause_count:>9}"
            f"{row.literal_count:>10}"
        )

    print()
    print("Notes (Benchmark C — per-operator isolation):")
    print("  σ  : annotations are never combined → overhead ≈ 1.0× (BoolFunc object copy only).")
    print("  π  : no projected-key collisions → add() never called → same floor as σ.")
    print("  ×  : every pair calls mul(); two singleton formulas conjoin into one 2-literal clause.")
    print("       mul() is the costliest per-tuple operation in BOOLFUNC_SR.")
    print("  ⊎  : every overlapping key calls add(); two singleton formulas form a 2-clause disjunction.")
    print("  δ  EXISTENCE    : replaces each formula with ⊤ (semiring.one()) — allocation dominates.")
    print("  δ  HOW_PROV.    : passes annotation unchanged — identity copy, typically faster than EXISTENCE.")
    print("  Cross-product overhead is highest because mul() distributes clause pairs, growing formula size.")
    print("  All other operators call add() or just copy, which is cheaper than full clause distribution.")
