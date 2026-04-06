"""Microbenchmarks on synthetic K-relations.

Isolates where provenance overhead comes from:
  - add-heavy projection collapse
  - add on already-wide formulas
  - mul-heavy cross products
  - cross product followed by projection collapse
  - deduplication strategy downstream cost: EXISTENCE vs HOW_PROVENANCE
"""

from __future__ import annotations

import statistics
from typing import Callable

from src.operators.cross_product import cross_product
from src.operators.deduplication import deduplication
from src.operators.multiset_sum import multiset_sum
from src.operators.projection import projection
from src.operators.selection import selection
from src.relation.k_relation import KRelation
from src.semirings import BOOLFUNC_SR, NAT_SR
from src.strategies import DedupStrategy

from ._common import (
    MicroBenchmarkRow,
    _annotation_for,
    _boolfunc_complexity,
    _build_disjunction,
    _measure,
)


def _selection_control_relation(size: int, use_boolfunc: bool) -> KRelation:
    relation = KRelation(["ID", "Flag"], BOOLFUNC_SR if use_boolfunc else NAT_SR)
    for index in range(size):
        relation._set_raw((index, index % 2), _annotation_for(index, "s", use_boolfunc))
    return relation


def _projection_collision_relation(size: int, use_boolfunc: bool) -> KRelation:
    relation = KRelation(["Group", "Witness"], BOOLFUNC_SR if use_boolfunc else NAT_SR)
    for index in range(size):
        relation._set_raw((0, index), _annotation_for(index, "p", use_boolfunc))
    return relation


def _dense_cross_relations(size: int, use_boolfunc: bool) -> tuple[KRelation, KRelation]:
    semiring = BOOLFUNC_SR if use_boolfunc else NAT_SR
    left = KRelation(["L"], semiring)
    right = KRelation(["R"], semiring)

    for index in range(size):
        left._set_raw((index,), _annotation_for(index, "l", use_boolfunc))
        right._set_raw((index,), _annotation_for(index, "r", use_boolfunc))

    return left, right


def _collapsed_cross_relations(size: int, use_boolfunc: bool) -> tuple[KRelation, KRelation]:
    semiring = BOOLFUNC_SR if use_boolfunc else NAT_SR
    left = KRelation(["GroupL", "L"], semiring)
    right = KRelation(["GroupR", "R"], semiring)

    for index in range(size):
        left._set_raw((0, index), _annotation_for(index, "cl", use_boolfunc))
        right._set_raw((0, index), _annotation_for(index, "cr", use_boolfunc))

    return left, right


def _wide_formula_relation(width: int, prefix: str, side: str, use_boolfunc: bool) -> KRelation:
    relation = KRelation(["Key"], BOOLFUNC_SR if use_boolfunc else NAT_SR)
    if use_boolfunc:
        annotation = _build_disjunction(f"{prefix}{side}", width)
    else:
        annotation = width
    relation._set_raw((0,), annotation)
    return relation


def _run_micro_workload(
    name: str,
    description: str,
    nat_fn: Callable[[], KRelation],
    boolfunc_fn: Callable[[], KRelation],
    repeat: int,
    warmup: int,
) -> MicroBenchmarkRow:
    nat_samples, _ = _measure(nat_fn, repeat=repeat, warmup=warmup)
    boolfunc_samples, boolfunc_result = _measure(boolfunc_fn, repeat=repeat, warmup=warmup)

    nat_ms = statistics.median(nat_samples)
    boolfunc_ms = statistics.median(boolfunc_samples)
    overhead_x = boolfunc_ms / nat_ms if nat_ms > 0 else float("inf")
    clause_count, literal_count = _boolfunc_complexity(boolfunc_result)

    return MicroBenchmarkRow(
        name=name,
        nat_ms=nat_ms,
        boolfunc_ms=boolfunc_ms,
        overhead_x=overhead_x,
        output_rows=boolfunc_result.support_size(),
        clause_count=clause_count,
        literal_count=literal_count,
        description=description,
    )


# ---------------------------------------------------------------------------
# Dedup downstream helpers and workloads
# ---------------------------------------------------------------------------

def _dedup_downstream_left_relation(
    size: int,
    formula_width: int,
    use_boolfunc: bool,
) -> KRelation:
    """Pre-build a relation where each row carries a formula_width-clause BoolFunc.

    This simulates the output of a HOW_PROVENANCE deduplication applied to a
    relation where each key accumulated formula_width alternative witnesses
    (e.g. from a prior projection collision).  In NAT_SR the annotation is
    always 1, keeping the integer baseline cheaply comparable.
    """
    semiring = BOOLFUNC_SR if use_boolfunc else NAT_SR
    rel = KRelation(["Key"], semiring)
    for i in range(size):
        ann = _build_disjunction(f"dd{i}_", formula_width) if use_boolfunc else 1
        rel._set_raw((i,), ann)
    return rel


def _dedup_downstream_right_relation(size: int, use_boolfunc: bool) -> KRelation:
    """Right-hand relation for dedup-downstream cross products (singleton annotations)."""
    semiring = BOOLFUNC_SR if use_boolfunc else NAT_SR
    rel = KRelation(["Cross"], semiring)
    for i in range(size):
        rel._set_raw((i,), _annotation_for(i, "cr", use_boolfunc))
    return rel


def _bench_dedup_existence_downstream(
    dd_size: int,
    formula_width: int,
    repeat: int,
    warmup: int,
) -> MicroBenchmarkRow:
    """dedup(EXISTENCE) → ×: collapsing to ⊤ makes the downstream cross product near-free.

    The left relation carries formula_width-clause formulas (simulating HOW_PROV
    dedup output from a many-to-one accumulation).  EXISTENCE replaces every
    annotation with ⊤ before the cross product, so each output pair evaluates
    mul(⊤, var_j) = var_j: one 1-literal clause per pair regardless of formula_width.

    Overhead over NAT is dominated only by BoolFunc object allocation, which is
    essentially the same as cross_dense with singleton annotations.
    """
    left_nat = _dedup_downstream_left_relation(dd_size, formula_width, use_boolfunc=False)
    left_bf = _dedup_downstream_left_relation(dd_size, formula_width, use_boolfunc=True)
    right_nat = _dedup_downstream_right_relation(dd_size, use_boolfunc=False)
    right_bf = _dedup_downstream_right_relation(dd_size, use_boolfunc=True)
    return _run_micro_workload(
        name="dedup_existence_downstream",
        description=(
            f"{dd_size}×{dd_size} cross after δ EXISTENCE. "
            "⊤ ∧ var(j) = var(j): 1 clause, 1 literal per pair. "
            "Provenance discarded by δ; downstream cost ≈ plain cross_dense."
        ),
        nat_fn=lambda: cross_product(
            deduplication(left_nat, DedupStrategy.EXISTENCE), right_nat
        ),
        boolfunc_fn=lambda: cross_product(
            deduplication(left_bf, DedupStrategy.EXISTENCE), right_bf
        ),
        repeat=repeat,
        warmup=warmup,
    )


def _bench_dedup_howprov_downstream(
    dd_size: int,
    formula_width: int,
    repeat: int,
    warmup: int,
) -> MicroBenchmarkRow:
    """dedup(HOW_PROVENANCE) → ×: retained formulas compound in downstream mul().

    Structurally identical to dedup_existence_downstream except the dedup
    strategy is HOW_PROVENANCE.  The left relation keeps its formula_width-clause
    formulas through δ, so the cross product evaluates
    mul(formula_width-clause formula, var_j) → formula_width 2-literal clauses
    per output pair instead of one.

    Any overhead gap between this workload and dedup_existence_downstream is
    entirely attributable to the downstream cost of HOW_PROV’s retained
    provenance feeding into a subsequent operator.
    """
    left_nat = _dedup_downstream_left_relation(dd_size, formula_width, use_boolfunc=False)
    left_bf = _dedup_downstream_left_relation(dd_size, formula_width, use_boolfunc=True)
    right_nat = _dedup_downstream_right_relation(dd_size, use_boolfunc=False)
    right_bf = _dedup_downstream_right_relation(dd_size, use_boolfunc=True)
    return _run_micro_workload(
        name="dedup_howprov_downstream",
        description=(
            f"{dd_size}×{dd_size} cross after δ HOW_PROV. "
            f"Each left row retains its {formula_width}-clause formula; "
            "mul() distributes into formula_width 2-literal clauses per pair. "
            "Directly shows downstream annotation cost of retained provenance."
        ),
        nat_fn=lambda: cross_product(
            deduplication(left_nat, DedupStrategy.HOW_PROVENANCE), right_nat
        ),
        boolfunc_fn=lambda: cross_product(
            deduplication(left_bf, DedupStrategy.HOW_PROVENANCE), right_bf
        ),
        repeat=repeat,
        warmup=warmup,
    )


def _benchmark_micro_workloads(
    size: int,
    cross_size: int,
    formula_width: int,
    repeat: int,
    warmup: int,
) -> list[MicroBenchmarkRow]:
    rows: list[MicroBenchmarkRow] = []

    selection_nat = _selection_control_relation(size, use_boolfunc=False)
    selection_bf = _selection_control_relation(size, use_boolfunc=True)
    rows.append(
        _run_micro_workload(
            name="selection_control",
            description="Control workload: row filtering without formula growth.",
            nat_fn=lambda: selection(selection_nat, lambda row: row["ID"] % 2 == 0),
            boolfunc_fn=lambda: selection(selection_bf, lambda row: row["ID"] % 2 == 0),
            repeat=repeat,
            warmup=warmup,
        )
    )

    projection_nat = _projection_collision_relation(size, use_boolfunc=False)
    projection_bf = _projection_collision_relation(size, use_boolfunc=True)
    rows.append(
        _run_micro_workload(
            name="projection_collision",
            description="Add-heavy workload: many rows collapse to one projected key.",
            nat_fn=lambda: projection(projection_nat, ["Group"]),
            boolfunc_fn=lambda: projection(projection_bf, ["Group"]),
            repeat=repeat,
            warmup=warmup,
        )
    )

    union_nat_left = _wide_formula_relation(formula_width, "u", "L", use_boolfunc=False)
    union_nat_right = _wide_formula_relation(formula_width, "u", "R", use_boolfunc=False)
    union_bf_left = _wide_formula_relation(formula_width, "u", "L", use_boolfunc=True)
    union_bf_right = _wide_formula_relation(formula_width, "u", "R", use_boolfunc=True)
    rows.append(
        _run_micro_workload(
            name="union_wide_formulas",
            description="Add on already-wide annotations for one overlapping tuple.",
            nat_fn=lambda: multiset_sum(union_nat_left, union_nat_right),
            boolfunc_fn=lambda: multiset_sum(union_bf_left, union_bf_right),
            repeat=repeat,
            warmup=warmup,
        )
    )

    cross_nat_left, cross_nat_right = _dense_cross_relations(cross_size, use_boolfunc=False)
    cross_bf_left, cross_bf_right = _dense_cross_relations(cross_size, use_boolfunc=True)
    rows.append(
        _run_micro_workload(
            name="cross_dense",
            description="Mul-heavy workload: dense cross product with simple tuple annotations.",
            nat_fn=lambda: cross_product(cross_nat_left, cross_nat_right),
            boolfunc_fn=lambda: cross_product(cross_bf_left, cross_bf_right),
            repeat=repeat,
            warmup=warmup,
        )
    )

    # Collapse workload: projection merges all cross-product pairs into one formula.
    # Cost is O(n^4) in cross_size (n^2 pairs, each adding to a growing n^2-clause formula),
    # so cap to keep the benchmark tractable at any --cross-size value.
    collapse_size = min(cross_size, 12)
    collapse_nat_left, collapse_nat_right = _collapsed_cross_relations(collapse_size, use_boolfunc=False)
    collapse_bf_left, collapse_bf_right = _collapsed_cross_relations(collapse_size, use_boolfunc=True)
    rows.append(
        _run_micro_workload(
            name="cross_then_projection",
            description=f"Realistic choke-point ({collapse_size}×{collapse_size}): cross product followed by full projection collapse.",
            nat_fn=lambda: projection(
                cross_product(collapse_nat_left, collapse_nat_right),
                ["GroupL"],
            ),
            boolfunc_fn=lambda: projection(
                cross_product(collapse_bf_left, collapse_bf_right),
                ["GroupL"],
            ),
            repeat=repeat,
            warmup=warmup,
        )
    )

    symbolic_nat_left = _wide_formula_relation(formula_width, "m", "L", use_boolfunc=False)
    symbolic_nat_right = _wide_formula_relation(formula_width, "m", "R", use_boolfunc=False)
    symbolic_bf_left = _wide_formula_relation(formula_width, "m", "L", use_boolfunc=True)
    symbolic_bf_right = _wide_formula_relation(formula_width, "m", "R", use_boolfunc=True)
    rows.append(
        _run_micro_workload(
            name="symbolic_mul_choke_point",
            description="Pure BoolFunc stress: multiply two wide disjunctions so clause count becomes width^2.",
            nat_fn=lambda: cross_product(symbolic_nat_left, symbolic_nat_right),
            boolfunc_fn=lambda: cross_product(symbolic_bf_left, symbolic_bf_right),
            repeat=repeat,
            warmup=warmup,
        )
    )

    # Dedup downstream pair: same pipeline, only strategy differs.
    # Comparing these two side-by-side isolates the downstream cost of HOW_PROV.
    dd_size = max(4, cross_size // 6)
    rows.append(_bench_dedup_existence_downstream(dd_size, formula_width, repeat, warmup))
    rows.append(_bench_dedup_howprov_downstream(dd_size, formula_width, repeat, warmup))

    return rows


def _print_micro_benchmark_rows(rows: list[MicroBenchmarkRow]) -> None:
    print("\n" + "=" * 108)
    print("PROVENANCE OVERHEAD MICROBENCHMARKS")
    print("=" * 108)
    print("Baseline semiring: NAT_SR (bag semantics, integer annotations, no symbolic provenance)")
    print("Provenance run  : BOOLFUNC_SR (positive Boolean formulas in DNF)")
    print()

    header = (
        f"{'Workload':<26}"
        f"{'NAT ms':>10}"
        f"{'BoolFunc ms':>14}"
        f"{'Overhead':>12}"
        f"{'Rows':>8}"
        f"{'Clauses':>10}"
        f"{'Literals':>10}"
    )
    print(header)
    print("-" * len(header))

    for row in rows:
        print(
            f"{row.name:<26}"
            f"{row.nat_ms:>10.3f}"
            f"{row.boolfunc_ms:>14.3f}"
            f"{row.overhead_x:>11.2f}x"
            f"{row.output_rows:>8}"
            f"{row.clause_count:>10}"
            f"{row.literal_count:>10}"
        )

    print("\nMicrobenchmark notes")
    print("- selection_control is the floor cost for core RA execution with almost no provenance growth.")
    print("- projection_collision isolates semiring.add under key collisions.")
    print("- union_wide_formulas isolates add on already-large Boolean formulas.")
    print("- cross_dense isolates tuple materialization plus semiring.mul on simple witnesses.")
    print("- cross_then_projection is the most realistic DNF blow-up pattern for this evaluator.")
    print("- symbolic_mul_choke_point isolates clause distribution: width clauses times width clauses gives width^2 clauses.")
    print("- dedup_existence_downstream: δ EXISTENCE collapses all formulas to ⊤ before ×; downstream cost ≈ plain cross_dense (1 clause per pair).")
    print("- dedup_howprov_downstream: δ HOW_PROV retains each formula; subsequent × distributes them, compounding annotation growth.")
    print("  Compare these two side-by-side: the overhead gap between them isolates the downstream cost of choosing HOW_PROV over EXISTENCE.")
