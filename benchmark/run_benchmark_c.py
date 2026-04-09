"""
Benchmark C — Per-operator microbenchmarks.

Reproduces Table 7 of the paper: isolates provenance overhead for each
of the 5 operators (6 configs including both dedup strategies).

All K-Relations are constructed directly — no SQL translator involved.

Usage:
    python run_benchmark_c.py
"""

from __future__ import annotations

import argparse
import gc
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.relation.k_relation import KRelation
from src.semirings.boolean import BooleanSemiring, BOOL_SR
from src.semirings.boolean_function import BoolFuncSemiring, BoolFunc, BOOLFUNC_SR
from src.operators.selection import selection
from src.operators.projection import projection
from src.operators.cross_product import cross_product
from src.operators.multiset_sum import multiset_sum
from src.operators.deduplication import deduplication
from src.strategies import DedupStrategy


def timed_op(op_fn, n_reps=7):
    """Run op_fn n_reps+1 times (1 warmup), return median seconds."""
    op_fn()  # warm-up
    times = []
    for _ in range(n_reps):
        gc.disable()
        t0 = time.perf_counter()
        result = op_fn()
        t1 = time.perf_counter()
        gc.enable()
        times.append(t1 - t0)
    return statistics.median(times), result


def count_clauses_literals(rel):
    """Count total clauses and literals across all BoolFunc annotations."""
    total_clauses = 0
    total_literals = 0
    for _key, ann in rel.items():
        if isinstance(ann, BoolFunc):
            total_clauses += len(ann._formula)
            total_literals += sum(len(c) for c in ann._formula)
    return total_clauses, total_literals


def build_relation(semiring, schema, rows, var_prefix="t"):
    """Build a KRelation with unique tuple variables for BoolFunc."""
    rel = KRelation(schema, semiring)
    for i, row in enumerate(rows):
        if isinstance(semiring, BoolFuncSemiring):
            ann = BoolFunc.var(f"{var_prefix}{i}")
        else:
            ann = semiring.one()
        rel.insert(row, ann)
    return rel


def main():
    parser = argparse.ArgumentParser(description="Benchmark C: Per-operator microbenchmarks.")
    parser.add_argument("--reps", type=int, default=7, help="Timed repetitions (default: 7).")
    args = parser.parse_args()

    print("Benchmark C: Per-operator provenance overhead")
    print(f"Repetitions: {args.reps} timed runs after 1 warm-up, GC disabled\n")

    results = []

    # ── 1. Selection (10-row input, even/odd filter) ──────────────────
    for label, semiring in [("BOOL", BOOL_SR), ("BF", BOOLFUNC_SR)]:
        schema = ["id", "val"]
        rows = [{"id": i, "val": f"v{i}"} for i in range(10)]
        rel = build_relation(semiring, schema, rows, "sel")
        predicate = lambda row: row["id"] % 2 == 0

        t, res = timed_op(lambda: selection(rel, predicate), args.reps)
        if label == "BOOL":
            t_bool_sel = t
            out_sel = res.support_size()
        else:
            t_bf_sel = t
            cl, li = count_clauses_literals(res)
            clauses_sel, lits_sel = cl, li

    results.append(("σ (Selection)", t_bool_sel, t_bf_sel, 10, out_sel, clauses_sel, lits_sel))

    # ── 2. Projection (10-row input, no collisions) ───────────────────
    for label, semiring in [("BOOL", BOOL_SR), ("BF", BOOLFUNC_SR)]:
        schema = ["id", "val"]
        rows = [{"id": i, "val": f"v{i}"} for i in range(10)]
        rel = build_relation(semiring, schema, rows, "proj")

        t, res = timed_op(lambda: projection(rel, ["id", "val"]), args.reps)
        if label == "BOOL":
            t_bool_proj = t
            out_proj = res.support_size()
        else:
            t_bf_proj = t
            cl, li = count_clauses_literals(res)
            clauses_proj, lits_proj = cl, li

    results.append(("π (Projection)", t_bool_proj, t_bf_proj, 10, out_proj, clauses_proj, lits_proj))

    # ── 3. Cross Product (5 × 10) ────────────────────────────────────
    for label, semiring in [("BOOL", BOOL_SR), ("BF", BOOLFUNC_SR)]:
        schema_l = ["a"]
        schema_r = ["b"]
        rows_l = [{"a": i} for i in range(5)]
        rows_r = [{"b": j} for j in range(10)]
        rel_l = build_relation(semiring, schema_l, rows_l, "xl")
        rel_r = build_relation(semiring, schema_r, rows_r, "xr")

        t, res = timed_op(lambda: cross_product(rel_l, rel_r), args.reps)
        if label == "BOOL":
            t_bool_cross = t
            out_cross = res.support_size()
        else:
            t_bf_cross = t
            cl, li = count_clauses_literals(res)
            clauses_cross, lits_cross = cl, li

    results.append(("× (Cross Product)", t_bool_cross, t_bf_cross, 15, out_cross, clauses_cross, lits_cross))

    # ── 4. Multiset Sum (two 10-row inputs, overlapping keys) ─────────
    for label, semiring in [("BOOL", BOOL_SR), ("BF", BOOLFUNC_SR)]:
        schema = ["id", "val"]
        rows_a = [{"id": i, "val": f"a{i}"} for i in range(10)]
        rows_b = [{"id": i, "val": f"a{i}"} for i in range(10)]  # same keys
        rel_a = build_relation(semiring, schema, rows_a, "ua")
        rel_b = build_relation(semiring, schema, rows_b, "ub")

        t, res = timed_op(lambda: multiset_sum(rel_a, rel_b), args.reps)
        if label == "BOOL":
            t_bool_union = t
            out_union = res.support_size()
        else:
            t_bf_union = t
            cl, li = count_clauses_literals(res)
            clauses_union, lits_union = cl, li

    results.append(("⊎ (Multiset Sum)", t_bool_union, t_bf_union, 20, out_union, clauses_union, lits_union))

    # ── 5. δ∃ (Existence deduplication) ───────────────────────────────
    for label, semiring in [("BOOL", BOOL_SR), ("BF", BOOLFUNC_SR)]:
        schema = ["id", "val"]
        rows = [{"id": i, "val": f"v{i}"} for i in range(10)]
        rel = build_relation(semiring, schema, rows, "de")

        t, res = timed_op(lambda: deduplication(rel, DedupStrategy.EXISTENCE), args.reps)
        if label == "BOOL":
            t_bool_dex = t
            out_dex = res.support_size()
        else:
            t_bf_dex = t
            cl, li = count_clauses_literals(res)
            clauses_dex, lits_dex = cl, li

    results.append(("δ∃ (Existence)", t_bool_dex, t_bf_dex, 10, out_dex, clauses_dex, lits_dex))

    # ── 6. δhow (How-Provenance deduplication) ────────────────────────
    for label, semiring in [("BOOL", BOOL_SR), ("BF", BOOLFUNC_SR)]:
        schema = ["id", "val"]
        # Build a relation where each row has a 2-clause annotation (to see difference)
        rel = KRelation(schema, semiring)
        for i in range(10):
            row = {"id": i, "val": f"v{i}"}
            if isinstance(semiring, BoolFuncSemiring):
                # 2-clause annotation per row to show how-prov passes them through
                ann = BoolFunc.var(f"dh{i}a").disjoin(BoolFunc.var(f"dh{i}b"))
            else:
                ann = semiring.one()
            rel.insert(row, ann)

        t, res = timed_op(lambda: deduplication(rel, DedupStrategy.HOW_PROVENANCE), args.reps)
        if label == "BOOL":
            t_bool_dhow = t
            out_dhow = res.support_size()
        else:
            t_bf_dhow = t
            cl, li = count_clauses_literals(res)
            clauses_dhow, lits_dhow = cl, li

    results.append(("δhow (How-Prov.)", t_bool_dhow, t_bf_dhow, 10, out_dhow, clauses_dhow, lits_dhow))

    # ── Print table ───────────────────────────────────────────────────
    print(f"{'Operator':<22} {'BOOL (µs)':>10} {'BF (µs)':>10} {'Time x':>8} "
          f"{'In':>4} {'Out':>4} {'Clauses':>8} {'Literals':>9}")
    print("-" * 85)
    for name, t_b, t_bf, inp, out, cl, li in results:
        t_b_us = t_b * 1_000_000
        t_bf_us = t_bf * 1_000_000
        ratio = t_bf / t_b if t_b > 0 else float("inf")
        print(f"{name:<22} {t_b_us:>10.1f} {t_bf_us:>10.1f} {ratio:>7.1f}x "
              f"{inp:>4} {out:>4} {cl:>8} {li:>9}")

    print("\nBenchmark C complete.")


if __name__ == "__main__":
    main()
