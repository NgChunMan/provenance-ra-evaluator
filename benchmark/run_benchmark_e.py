"""
Benchmark E — TPC-H macrobenchmarks across scale factors.

Reproduces Table 9 of the paper: 5 curated operator pipelines at SF 0.01, 0.05, 0.1.
Operators are called directly (no SQL translator). Selections are pushed before
cross products. Deduplication: How-Provenance strategy.

Baseline: NAT_SR; provenance: BOOLFUNC_SR.

Usage:
    python run_benchmark_e.py --sf 0.01 --data-dir ./tpch_data/sf001
    python run_benchmark_e.py --sf all
"""

from __future__ import annotations

import argparse
import gc
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.relation.k_relation import KRelation
from src.semirings.counting import NAT_SR
from src.semirings.boolean_function import BoolFuncSemiring, BoolFunc, BOOLFUNC_SR
from src.operators.selection import selection
from src.operators.projection import projection
from src.operators.cross_product import cross_product
from src.operators.deduplication import deduplication
from src.strategies import DedupStrategy
from src.io.tpch_loader import load_tpch_csvs

STRATEGY = DedupStrategy.HOW_PROVENANCE


def timed_op(op_fn, n_reps=7):
    """1 warmup + n_reps timed runs, return median seconds and last result."""
    op_fn()
    times = []
    for _ in range(n_reps):
        gc.disable()
        t0 = time.perf_counter()
        result = op_fn()
        t1 = time.perf_counter()
        gc.enable()
        times.append(t1 - t0)
    return statistics.median(times), result


def count_bf_stats(rel):
    rows = 0
    clauses = 0
    literals = 0
    for _key, ann in rel.items():
        if isinstance(ann, BoolFunc) and not ann.is_false():
            rows += 1
            clauses += len(ann._formula)
            literals += sum(len(c) for c in ann._formula)
        elif not isinstance(ann, BoolFunc):
            rows += 1
    return rows, clauses, literals


def count_rows(rel):
    return rel.support_size()


def make_annotation_factory(semiring):
    """Return an annotation_factory for load_tpch_csvs that assigns unique variables."""
    if isinstance(semiring, BoolFuncSemiring):
        def factory(table_name: str, row_index: int, row: Dict[str, Any]):
            return BoolFunc.var(f"{table_name}_{row_index}")
        return factory
    return None


def load_tables_with_vars(data_dir, semiring, tables=None, limit=None):
    """Load TPC-H tables, assigning unique tuple variables for BoolFunc."""
    factory = make_annotation_factory(semiring)
    return load_tpch_csvs(data_dir, semiring, tables=tables, limit=limit,
                          annotation_factory=factory)


# ── Pipeline definitions ─────────────────────────────────────────────
# Each pipeline is a function: tables_dict -> KRelation

def pipeline_nation_region_lookup(tables):
    """σ(regionkey match)(nation × region) → π(r_name) → δ"""
    nation = tables["nation"]
    region = tables["region"]
    cp = cross_product(nation, region)
    sel = selection(cp, lambda r: r["n_regionkey"] == r["r_regionkey"])
    proj = projection(sel, ["r_name"])
    return deduplication(proj, STRATEGY)


def pipeline_supplier_region_collapse(tables):
    """supplier × nation × region, filtered, projected to r_name, deduped."""
    supplier = tables["supplier"]
    nation = tables["nation"]
    region = tables["region"]
    # Push selection: first join supplier × nation on nationkey
    cp1 = cross_product(supplier, nation)
    sel1 = selection(cp1, lambda r: r["s_nationkey"] == r["n_nationkey"])
    # Then join with region on regionkey
    cp2 = cross_product(sel1, region)
    sel2 = selection(cp2, lambda r: r["n_regionkey"] == r["r_regionkey"])
    proj = projection(sel2, ["r_name"])
    return deduplication(proj, STRATEGY)


def pipeline_building_segment_singleton(tables):
    """customer × orders filtered to BUILDING segment, projected to c_mktsegment, deduped."""
    customer = tables["customer"]
    orders = tables["orders"]
    # Push selections
    cust_filtered = selection(customer, lambda r: r["c_mktsegment"] == "BUILDING")
    cp = cross_product(cust_filtered, orders)
    sel = selection(cp, lambda r: r["c_custkey"] == r["o_custkey"])
    proj = projection(sel, ["c_mktsegment"])
    return deduplication(proj, STRATEGY)


def pipeline_orders_lineitem_shipmode(tables):
    """orders × lineitem, filtered on orderkey match and a lineitem modulo filter, projected to l_shipmode, deduped."""
    orders = tables["orders"]
    lineitem = tables["lineitem"]
    # Push lineitem modulo filter; no pre-filter on orders
    # (an orders pre-filter o_orderkey % 100 == 0 was designed for the
    # full 15 000-row SF 0.01 dataset and leaves only 1 row in the
    # truncated 150-row committed data, reducing output to 1 pair.)
    lineitem_f = selection(lineitem, lambda r: r["l_partkey"] % 4 == 0)
    cp = cross_product(orders, lineitem_f)
    sel = selection(cp, lambda r: r["o_orderkey"] == r["l_orderkey"])
    proj = projection(sel, ["l_shipmode"])
    return deduplication(proj, STRATEGY)


def pipeline_asia_lineitem_supplier_singleton(tables):
    """lineitem × supplier × nation × region, filtered to ASIA, projected to region name, deduped."""
    lineitem = tables["lineitem"]
    supplier = tables["supplier"]
    nation = tables["nation"]
    region = tables["region"]
    li_f = lineitem
    region_f = selection(region, lambda r: r["r_name"] == "ASIA")
    # supplier × nation
    cp1 = cross_product(supplier, nation)
    sel1 = selection(cp1, lambda r: r["s_nationkey"] == r["n_nationkey"])
    # × region (filtered)
    cp2 = cross_product(sel1, region_f)
    sel2 = selection(cp2, lambda r: r["n_regionkey"] == r["r_regionkey"])
    # × lineitem (filtered)
    cp3 = cross_product(sel2, li_f)
    sel3 = selection(cp3, lambda r: r["s_suppkey"] == r["l_suppkey"])
    proj = projection(sel3, ["r_name"])
    return deduplication(proj, STRATEGY)


PIPELINES = [
    ("nation_region_lookup", pipeline_nation_region_lookup),
    ("supplier_region_collapse", pipeline_supplier_region_collapse),
    ("building_segment_singleton", pipeline_building_segment_singleton),
    ("orders_lineitem_shipmode", pipeline_orders_lineitem_shipmode),
    ("asia_lineitem_supplier_singleton", pipeline_asia_lineitem_supplier_singleton),
]


def resolve_data_dir(sf: float, base_dir: str | None) -> Path:
    """Find the data directory for a given scale factor."""
    if base_dir:
        return Path(base_dir)
    sf_tag = str(sf).replace(".", "")
    return ROOT / "benchmark" / "tpch_data" / f"sf{sf_tag}"


def run_sf(sf: float, data_dir: Path, reps: int):
    """Run all pipelines at one scale factor, return list of result tuples."""
    print(f"\n  Loading tables from {data_dir} ...")
    results = []

    for name, pipeline_fn in PIPELINES:
        print(f"  Running {name} ...")

        # NAT_SR baseline
        tables_nat = load_tables_with_vars(data_dir, NAT_SR)
        t_nat, res_nat = timed_op(lambda: pipeline_fn(tables_nat), reps)
        rows_nat = count_rows(res_nat)

        # BOOLFUNC_SR provenance
        tables_bf = load_tables_with_vars(data_dir, BOOLFUNC_SR)
        t_bf, res_bf = timed_op(lambda: pipeline_fn(tables_bf), reps)
        rows_bf, cl, li = count_bf_stats(res_bf)

        ratio = t_bf / t_nat if t_nat > 0 else float("inf")
        results.append((name, t_nat, t_bf, ratio, rows_bf, cl, li))

    return results


def main():
    parser = argparse.ArgumentParser(description="Benchmark E: TPC-H macrobenchmarks.")
    parser.add_argument("--sf", type=str, default="all",
                        help="Scale factor: 0.01, 0.05, 0.1, or 'all' (default: all).")
    parser.add_argument("--data-dir", type=str, default=None,
                        help="Base data directory (auto-detected if not given).")
    parser.add_argument("--reps", type=int, default=7, help="Timed repetitions (default: 7).")
    args = parser.parse_args()

    if args.sf == "all":
        scale_factors = [0.01, 0.05, 0.1]
    else:
        scale_factors = [float(args.sf)]

    print("Benchmark E: TPC-H macrobenchmarks across scale factors")
    print(f"Strategy: How-Provenance | Reps: {args.reps} after 1 warm-up, GC disabled")

    all_results = {}
    for sf in scale_factors:
        data_dir = resolve_data_dir(sf, args.data_dir)
        if not data_dir.is_dir():
            print(f"\n  WARNING: Data directory not found for SF {sf}: {data_dir}")
            print(f"  Run: python generate_tpch_data.py --sf {sf} --output-dir {data_dir}")
            continue

        print(f"\n{'='*80}")
        print(f"  Scale Factor: {sf}")
        print(f"{'='*80}")

        sf_results = run_sf(sf, data_dir, args.reps)
        all_results[sf] = sf_results

    # Print final summary table
    for sf, sf_results in all_results.items():
        print(f"\n{'='*80}")
        print(f"  SF {sf}")
        print(f"{'='*80}")
        print(f"{'Workload':<40} {'NAT (ms)':>10} {'BF (ms)':>12} {'Overhead':>10} "
              f"{'Rows':>6} {'Clauses':>8} {'Literals':>9}")
        print("-" * 99)
        for name, t_nat, t_bf, ratio, rows, cl, li in sf_results:
            t_nat_ms = t_nat * 1000
            t_bf_ms = t_bf * 1000
            if ratio >= 100:
                ratio_str = f"{ratio:.1f}x"
            else:
                ratio_str = f"{ratio:.1f}x"
            print(f"{name:<40} {t_nat_ms:>10.3f} {t_bf_ms:>12.3f} {ratio_str:>10} "
                  f"{rows:>6} {cl:>8} {li:>9}")

    print("\nBenchmark E complete.")


if __name__ == "__main__":
    main()
