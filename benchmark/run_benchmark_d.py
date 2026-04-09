"""
Benchmark D — Synthetic stress tests: 8 workloads isolating specific overhead sources.

Reproduces Table 8 of the paper. All K-Relations are constructed directly
(no SQL translator). Baseline: NAT_SR; provenance: BOOLFUNC_SR.

Usage:
    python run_benchmark_d.py
    python run_benchmark_d.py --size 128 --cross-size 48 --formula-width 48
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
from src.semirings.counting import CountingSemiring, NAT_SR
from src.semirings.boolean_function import BoolFuncSemiring, BoolFunc, BOOLFUNC_SR
from src.operators.selection import selection
from src.operators.projection import projection
from src.operators.cross_product import cross_product
from src.operators.multiset_sum import multiset_sum
from src.operators.deduplication import deduplication
from src.strategies import DedupStrategy


def timed_op(op_fn, n_reps=7):
    """Run op_fn n_reps+1 times (1 warmup), return median seconds and last result."""
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


def count_bf_stats(rel):
    """Count output rows, total clauses, total literals for a BoolFunc-annotated relation."""
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


def build_rel(semiring, schema, rows, var_prefix="t"):
    """Build a KRelation with unique tuple variables for BoolFunc."""
    rel = KRelation(schema, semiring)
    for i, row in enumerate(rows):
        if isinstance(semiring, BoolFuncSemiring):
            ann = BoolFunc.var(f"{var_prefix}{i}")
        else:
            ann = semiring.one()
        rel.insert(row, ann)
    return rel


def run_workloads(args):
    SIZE = args.size
    CROSS_SIZE = args.cross_size
    FW = args.formula_width
    REPS = args.reps

    results = []

    # ── 1. selection_control ──────────────────────────────────────────
    print("  Running selection_control ...")
    for label, semiring in [("NAT", NAT_SR), ("BF", BOOLFUNC_SR)]:
        schema = ["id", "val"]
        rows = [{"id": i, "val": f"v{i}"} for i in range(SIZE * 2)]
        rel = build_rel(semiring, schema, rows, "sc")
        t, res = timed_op(lambda: selection(rel, lambda r: r["id"] % 2 == 0), REPS)
        if label == "NAT":
            t_nat = t
        else:
            t_bf = t
            rr, cl, li = count_bf_stats(res)
    results.append(("selection_control", t_nat, t_bf, rr, cl, li))

    # ── 2. projection_collision ───────────────────────────────────────
    print("  Running projection_collision ...")
    for label, semiring in [("NAT", NAT_SR), ("BF", BOOLFUNC_SR)]:
        schema = ["key", "varying"]
        # All rows share key="K", differ only in varying column
        rows = [{"key": "K", "varying": f"v{i}"} for i in range(SIZE * 2)]
        rel = build_rel(semiring, schema, rows, "pc")
        t, res = timed_op(lambda: projection(rel, ["key"]), REPS)
        if label == "NAT":
            t_nat = t
        else:
            t_bf = t
            rr, cl, li = count_bf_stats(res)
    results.append(("projection_collision", t_nat, t_bf, rr, cl, li))

    # ── 3. union_wide_formulas ────────────────────────────────────────
    print("  Running union_wide_formulas ...")
    for label, semiring in [("NAT", NAT_SR), ("BF", BOOLFUNC_SR)]:
        schema = ["key"]
        rel_a = KRelation(schema, semiring)
        rel_b = KRelation(schema, semiring)
        row = {"key": "K"}
        if isinstance(semiring, BoolFuncSemiring):
            # Build a 48-clause formula for each side
            formula_a = BoolFunc.false_()
            for i in range(FW):
                formula_a = formula_a.disjoin(BoolFunc.var(f"wa{i}"))
            formula_b = BoolFunc.false_()
            for i in range(FW):
                formula_b = formula_b.disjoin(BoolFunc.var(f"wb{i}"))
            rel_a.insert(row, formula_a)
            rel_b.insert(row, formula_b)
        else:
            rel_a.insert(row, semiring.one())
            rel_b.insert(row, semiring.one())
        t, res = timed_op(lambda: multiset_sum(rel_a, rel_b), REPS)
        if label == "NAT":
            t_nat = t
        else:
            t_bf = t
            rr, cl, li = count_bf_stats(res)
    results.append(("union_wide_formulas", t_nat, t_bf, rr, cl, li))

    # ── 4. cross_dense ────────────────────────────────────────────────
    print("  Running cross_dense ...")
    for label, semiring in [("NAT", NAT_SR), ("BF", BOOLFUNC_SR)]:
        schema_l = ["a"]
        schema_r = ["b"]
        rows_l = [{"a": i} for i in range(CROSS_SIZE)]
        rows_r = [{"b": j} for j in range(CROSS_SIZE)]
        rel_l = build_rel(semiring, schema_l, rows_l, "cdl")
        rel_r = build_rel(semiring, schema_r, rows_r, "cdr")
        t, res = timed_op(lambda: cross_product(rel_l, rel_r), REPS)
        if label == "NAT":
            t_nat = t
        else:
            t_bf = t
            rr, cl, li = count_bf_stats(res)
    results.append(("cross_dense", t_nat, t_bf, rr, cl, li))

    # ── 5. cross_then_projection ──────────────────────────────────────
    # 12×12 input grid, project to single key
    CP_SIZE = 12
    print("  Running cross_then_projection ...")
    for label, semiring in [("NAT", NAT_SR), ("BF", BOOLFUNC_SR)]:
        schema_l = ["a"]
        schema_r = ["b"]
        rows_l = [{"a": i} for i in range(CP_SIZE)]
        rows_r = [{"b": j} for j in range(CP_SIZE)]
        rel_l = build_rel(semiring, schema_l, rows_l, "cpl")
        rel_r = build_rel(semiring, schema_r, rows_r, "cpr")

        def _cp_then_proj():
            cp = cross_product(rel_l, rel_r)
            # Add a constant column to project onto
            projected = KRelation(["const"], semiring)
            for key, ann in cp.items():
                row = {"const": "X"}
                projected.insert(row, ann)
            return projected

        t, res = timed_op(_cp_then_proj, REPS)
        if label == "NAT":
            t_nat = t
        else:
            t_bf = t
            rr, cl, li = count_bf_stats(res)
    results.append(("cross_then_projection", t_nat, t_bf, rr, cl, li))

    # ── 6. symbolic_mul_choke_point ───────────────────────────────────
    print("  Running symbolic_mul_choke_point (may take a while) ...")
    for label, semiring in [("NAT", NAT_SR), ("BF", BOOLFUNC_SR)]:
        if isinstance(semiring, BoolFuncSemiring):
            formula_a = BoolFunc.false_()
            for i in range(FW):
                formula_a = formula_a.disjoin(BoolFunc.var(f"ma{i}"))
            formula_b = BoolFunc.false_()
            for i in range(FW):
                formula_b = formula_b.disjoin(BoolFunc.var(f"mb{i}"))

            def _mul_bf():
                return semiring.mul(formula_a, formula_b)

            t, res_val = timed_op(_mul_bf, REPS)
            t_bf = t
            # res_val is a BoolFunc
            cl = len(res_val._formula)
            li = sum(len(c) for c in res_val._formula)
            rr = 1
        else:
            def _mul_nat():
                return semiring.mul(semiring.one(), semiring.one())
            t, _ = timed_op(_mul_nat, REPS)
            t_nat = t
    results.append(("symbolic_mul_choke_point", t_nat, t_bf, rr, cl, li))

    # ── 7 & 8. dedup_existence/howprov_downstream ─────────────────────
    # rel_l: GRID rows each with a FW-clause formula (wide annotation).
    # After dedup, EXISTENCE collapses each to TRUE (one()); HOW_PROVENANCE
    # retains the 48-clause formula.  The downstream cross_product(deduped_l,
    # rel_r) then reveals the true annotation cost of each strategy:
    #   EXISTENCE  → TRUE × var_j = var_j   (1 clause, 1 literal per output row)
    #   HOW_PROV   → 48-clause × var_j = 48 clauses, 2 literals each
    GRID = 8
    for dedup_label, strategy in [
        ("dedup_existence_downstream", DedupStrategy.EXISTENCE),
        ("dedup_howprov_downstream", DedupStrategy.HOW_PROVENANCE),
    ]:
        print(f"  Running {dedup_label} ...")
        for label, semiring in [("NAT", NAT_SR), ("BF", BOOLFUNC_SR)]:
            schema_l = ["a"]
            schema_r = ["b"]
            # Build rel_l with wide FW-clause formulas (one per row)
            rel_l = KRelation(schema_l, semiring)
            for i in range(GRID):
                if isinstance(semiring, BoolFuncSemiring):
                    formula = BoolFunc.false_()
                    for k in range(FW):
                        formula = formula.disjoin(BoolFunc.var(f"wdl{i}_{k}"))
                    rel_l.insert({"a": i}, formula)
                else:
                    rel_l.insert({"a": i}, semiring.one())
            # rel_r: GRID rows with single-variable annotations
            rel_r = build_rel(semiring, schema_r, [{"b": j} for j in range(GRID)], "gr")
            deduped_l = deduplication(rel_l, strategy)

            def _downstream(dl=deduped_l, dr=rel_r):
                return cross_product(dl, dr)

            t, res = timed_op(_downstream, REPS)
            if label == "NAT":
                t_nat = t
            else:
                t_bf = t
                rr, cl, li = count_bf_stats(res)
        results.append((dedup_label, t_nat, t_bf, rr, cl, li))

    return results


def main():
    parser = argparse.ArgumentParser(description="Benchmark D: Synthetic stress tests.")
    parser.add_argument("--size", type=int, default=128, help="Base workload size (default: 128).")
    parser.add_argument("--cross-size", type=int, default=48, help="Cross product dimension (default: 48).")
    parser.add_argument("--formula-width", type=int, default=48, help="Formula clause count (default: 48).")
    parser.add_argument("--reps", type=int, default=7, help="Timed repetitions (default: 7).")
    args = parser.parse_args()

    print("Benchmark D: Provenance overhead microbenchmarks")
    print(f"Parameters: --size {args.size}, --cross-size {args.cross_size}, "
          f"--formula-width {args.formula_width}")
    print(f"Repetitions: {args.reps} timed runs after 1 warm-up, GC disabled\n")

    results = run_workloads(args)

    # Print table
    print(f"\n{'Workload':<36} {'NAT (ms)':>10} {'BF (ms)':>12} {'Overhead':>10} "
          f"{'Rows':>6} {'Clauses':>8} {'Literals':>9}")
    print("-" * 95)
    for name, t_nat, t_bf, rows, cl, li in results:
        t_nat_ms = t_nat * 1000
        t_bf_ms = t_bf * 1000
        ratio = t_bf / t_nat if t_nat > 0 else float("inf")
        if ratio >= 1000:
            ratio_str = f"{ratio:,.0f}x"
        else:
            ratio_str = f"{ratio:.1f}x"
        print(f"{name:<36} {t_nat_ms:>10.3f} {t_bf_ms:>12.3f} {ratio_str:>10} "
              f"{rows:>6} {cl:>8} {li:>9}")

    print("\nBenchmark D complete.")


if __name__ == "__main__":
    main()
