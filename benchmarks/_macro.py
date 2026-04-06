"""Macrobenchmarks on real TPC-H CSV data.

Uses curated operator pipelines over the committed TPC-H tables, with the
timed region restricted to relational operator execution. The following costs
are intentionally excluded from timing:
  - CSV loading
  - tuple-variable assignment for BoolFunc annotations
  - optional TPC-H CSV generation for larger scale factors
"""

from __future__ import annotations

import statistics
import time
from pathlib import Path
from typing import Sequence

from src.io.tpch_loader import load_tpch_csvs
from src.operators.cross_product import cross_product
from src.operators.deduplication import deduplication
from src.operators.projection import projection
from src.operators.selection import selection
from src.relation.k_relation import KRelation
from src.semirings import BOOLFUNC_SR, NAT_SR
from src.strategies import DedupStrategy

from ._common import (
    MacroBenchmarkRow,
    MacroWorkload,
    _boolfunc_complexity,
    _measure,
    _progress,
)
from ._tpch import _tpch_boolfunc_annotation


def _load_macro_tables(
    csv_dir: Path,
    limit: int | None,
) -> tuple[dict[str, KRelation], dict[str, KRelation]]:
    nat_tables = load_tpch_csvs(csv_dir, NAT_SR, limit=limit)
    boolfunc_tables = load_tpch_csvs(
        csv_dir,
        BOOLFUNC_SR,
        limit=limit,
        annotation_factory=_tpch_boolfunc_annotation,
    )
    return nat_tables, boolfunc_tables


def _macro_nation_region_lookup(
    tables: dict[str, KRelation],
    strategy: DedupStrategy,
) -> KRelation:
    crossed = cross_product(tables["nation"], tables["region"])
    joined = selection(crossed, lambda row: row["n_regionkey"] == row["r_regionkey"])
    projected = projection(joined, ["r_name"])
    return deduplication(projected, strategy)


def _macro_supplier_region_collapse(
    tables: dict[str, KRelation],
    strategy: DedupStrategy,
) -> KRelation:
    supplier_nation = cross_product(tables["supplier"], tables["nation"])
    joined_1 = selection(
        supplier_nation,
        lambda row: row["s_nationkey"] == row["n_nationkey"],
    )
    supplier_nation_region = cross_product(joined_1, tables["region"])
    joined_2 = selection(
        supplier_nation_region,
        lambda row: row["n_regionkey"] == row["r_regionkey"],
    )
    projected = projection(joined_2, ["r_name"])
    return deduplication(projected, strategy)


def _macro_orders_lineitem_shipmode(
    tables: dict[str, KRelation],
    strategy: DedupStrategy,
) -> KRelation:
    orders = selection(tables["orders"], lambda row: row["o_orderkey"] % 100 == 0)
    lineitem = selection(
        tables["lineitem"],
        lambda row: row["l_orderkey"] % 100 == 0 and row["l_partkey"] % 4 == 0,
    )
    crossed = cross_product(orders, lineitem)
    joined = selection(crossed, lambda row: row["o_orderkey"] == row["l_orderkey"])
    projected = projection(joined, ["l_shipmode"])
    return deduplication(projected, strategy)


def _macro_building_segment_singleton(
    tables: dict[str, KRelation],
    strategy: DedupStrategy,
) -> KRelation:
    customers = selection(tables["customer"], lambda row: row["c_mktsegment"] == "BUILDING")
    orders = selection(tables["orders"], lambda row: row["o_orderkey"] % 50 == 0)
    crossed = cross_product(customers, orders)
    joined = selection(crossed, lambda row: row["c_custkey"] == row["o_custkey"])
    projected = projection(joined, ["c_mktsegment"])
    return deduplication(projected, strategy)


def _macro_asia_lineitem_supplier_singleton(
    tables: dict[str, KRelation],
    strategy: DedupStrategy,
) -> KRelation:
    lineitem = selection(tables["lineitem"], lambda row: row["l_partkey"] % 64 == 0)
    asia = selection(tables["region"], lambda row: row["r_name"] == "ASIA")

    supplier_nation = cross_product(tables["supplier"], tables["nation"])
    supplier_nation_joined = selection(
        supplier_nation,
        lambda row: row["s_nationkey"] == row["n_nationkey"],
    )

    supplier_geo = cross_product(supplier_nation_joined, asia)
    supplier_geo_joined = selection(
        supplier_geo,
        lambda row: row["n_regionkey"] == row["r_regionkey"],
    )

    crossed = cross_product(lineitem, supplier_geo_joined)
    joined = selection(crossed, lambda row: row["l_suppkey"] == row["s_suppkey"])
    projected = projection(joined, ["r_name"])
    return deduplication(projected, strategy)


def _macro_workloads(suite: str) -> list[MacroWorkload]:
    standard = [
        MacroWorkload(
            name="nation_region_lookup",
            description="Small control join over two TPC-H dimension tables.",
            execute=_macro_nation_region_lookup,
        ),
        MacroWorkload(
            name="supplier_region_collapse",
            description="Supplier-to-region lookup projected to five regions.",
            execute=_macro_supplier_region_collapse,
        ),
        MacroWorkload(
            name="building_segment_singleton",
            description="Customer-orders join collapsed to one market segment output tuple.",
            execute=_macro_building_segment_singleton,
        ),
    ]
    stress = [
        MacroWorkload(
            name="orders_lineitem_shipmode",
            description="Two-table fact join projected to low-cardinality ship modes.",
            execute=_macro_orders_lineitem_shipmode,
        ),
        MacroWorkload(
            name="asia_lineitem_supplier_singleton",
            description="Lineitem-supplier-region pipeline collapsed to one region output tuple.",
            execute=_macro_asia_lineitem_supplier_singleton,
        ),
    ]

    if suite == "standard":
        return standard
    if suite == "stress":
        return stress
    return standard + stress


def _select_macro_workloads(
    suite: str,
    selected_names: Sequence[str] | None,
) -> list[MacroWorkload]:
    workloads = _macro_workloads(suite)
    if not selected_names:
        return workloads

    workload_by_name = {workload.name: workload for workload in workloads}
    missing = [name for name in selected_names if name not in workload_by_name]
    if missing:
        known = ", ".join(sorted(workload_by_name))
        raise ValueError(
            f"Unknown macro workload(s): {missing!r}. Known workloads: {known}"
        )

    return [workload_by_name[name] for name in selected_names]


def _run_macro_workload(
    source: str,
    workload: MacroWorkload,
    nat_tables: dict[str, KRelation],
    boolfunc_tables: dict[str, KRelation],
    strategy: DedupStrategy,
    repeat: int,
    warmup: int,
    progress_prefix: str | None = None,
) -> MacroBenchmarkRow:
    nat_fn = lambda: workload.execute(nat_tables, strategy)
    boolfunc_fn = lambda: workload.execute(boolfunc_tables, strategy)

    nat_samples, _ = _measure(
        nat_fn,
        repeat=repeat,
        warmup=warmup,
        progress_label=(f"{progress_prefix} NAT_SR" if progress_prefix is not None else None),
    )
    boolfunc_samples, boolfunc_result = _measure(
        boolfunc_fn,
        repeat=repeat,
        warmup=warmup,
        progress_label=(
            f"{progress_prefix} BOOLFUNC_SR" if progress_prefix is not None else None
        ),
    )

    nat_ms = statistics.median(nat_samples)
    boolfunc_ms = statistics.median(boolfunc_samples)
    overhead_x = boolfunc_ms / nat_ms if nat_ms > 0 else float("inf")
    clause_count, literal_count = _boolfunc_complexity(boolfunc_result)

    return MacroBenchmarkRow(
        source=source,
        name=workload.name,
        nat_ms=nat_ms,
        boolfunc_ms=boolfunc_ms,
        overhead_x=overhead_x,
        output_rows=boolfunc_result.support_size(),
        clause_count=clause_count,
        literal_count=literal_count,
        description=workload.description,
    )


def _benchmark_macro_workloads(
    workloads: Sequence[MacroWorkload],
    sources: Sequence[tuple[str, Path]],
    strategy: DedupStrategy,
    repeat: int,
    warmup: int,
    limit: int | None,
) -> list[MacroBenchmarkRow]:
    rows: list[MacroBenchmarkRow] = []
    total_workloads = len(workloads) * len(sources)
    completed = 0

    for source_label, source_dir in sources:
        _progress(f"[macro] loading source {source_label} from {source_dir}")
        load_started = time.perf_counter()
        nat_tables, boolfunc_tables = _load_macro_tables(source_dir, limit=limit)
        _progress(
            f"[macro] loaded source {source_label} in {time.perf_counter() - load_started:.2f}s"
        )
        for workload in workloads:
            completed += 1
            progress_prefix = f"[macro {completed}/{total_workloads}] {source_label} / {workload.name}"
            _progress(f"{progress_prefix} started")
            rows.append(
                _run_macro_workload(
                    source=source_label,
                    workload=workload,
                    nat_tables=nat_tables,
                    boolfunc_tables=boolfunc_tables,
                    strategy=strategy,
                    repeat=repeat,
                    warmup=warmup,
                    progress_prefix=progress_prefix,
                )
            )
            row = rows[-1]
            _progress(
                f"{progress_prefix} finished: NAT {row.nat_ms:.3f} ms, "
                f"BoolFunc {row.boolfunc_ms:.3f} ms, overhead {row.overhead_x:.2f}x"
            )

    return rows


def _print_macro_benchmark_rows(
    rows: list[MacroBenchmarkRow],
    strategy: DedupStrategy,
) -> None:
    print("\n" + "=" * 132)
    print("TPC-H MACROBENCHMARKS")
    print("=" * 132)
    print("Baseline semiring: NAT_SR (bag semantics, integer annotations, no symbolic provenance)")
    print("Provenance run: BOOLFUNC_SR with one provenance variable per loaded TPC-H tuple")
    print(f"Dedup strategy: {strategy.name}")
    print("Timed region: relational operator execution only")
    print("Excluded costs: CSV loading, tuple-variable assignment, optional SF CSV generation")
    print()

    header = (
        f"{'Source':<22}"
        f"{'Workload':<32}"
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
            f"{row.source:<22}"
            f"{row.name:<32}"
            f"{row.nat_ms:>10.3f}"
            f"{row.boolfunc_ms:>14.3f}"
            f"{row.overhead_x:>11.2f}x"
            f"{row.output_rows:>8}"
            f"{row.clause_count:>10}"
            f"{row.literal_count:>10}"
        )

    print("\nMacrobenchmark notes")
    print("- These workloads use real TPC-H CSV data but avoid full SQL query plans that would explode under naive cross-product evaluation.")
    print("- Low-cardinality projections are deliberate: they concentrate many witnesses into a few output tuples and surface provenance growth clearly.")
    print("- For worst BoolFunc growth, use the stress suite with HOW_PROVENANCE and sweep scale factors, for example: --tpch-sf 0.01 0.05 0.1 --macro-suite stress.")
