"""
Entry point: worked example  →  correctness tests  →  benchmarks.

Tests are defined inline here (no pytest dependency) so this script
runs without any third-party packages.  The identical assertions are
also present in tests/test_deduplication.py for use with pytest.
"""

import sys

from src.semirings import BOOL_SR, NAT_SR, POLY_SR, Polynomial
from src.relation  import KRelation
from src.operators.deduplication import deduplication
from src.strategies import DedupStrategy
from benchmarks.bench_deduplication import main as run_benchmarks


# ──────────────────────────────────────────────────────────────────────
# Worked example
# ──────────────────────────────────────────────────────────────────────

def _run_worked_example() -> None:
    print("\n" + "═" * 60)
    print("  WORKED EXAMPLE")
    print("  Query: δ( π_Name( R ⋈_Dept R ) )")
    print("═" * 60)

    t1 = Polynomial.from_var("t1")
    t2 = Polynomial.from_var("t2")
    t3 = Polynomial.from_var("t3")

    alice_poly = t1.multiply(t1).add(t1.multiply(t3)).add(t2.multiply(t2))
    bob_poly   = t1.multiply(t3).add(t3.multiply(t3))

    print("""
  Input relation R:
    (Alice, Eng) → t1
    (Alice, HR)  → t2
    (Bob,   Eng) → t3

  After self-join ⋈_Dept + projection π(Name_L):
    Alice → t1² + t1·t3 + t2²
    Bob   → t1·t3 + t3²
    """)

    pre = KRelation(["Name"], POLY_SR)
    pre._set_raw(("Alice",), alice_poly)
    pre._set_raw(("Bob",),   bob_poly)
    print(pre.pretty("Input to δ  (polynomial annotations)"))

    # EXISTENCE
    r_ex = deduplication(pre, DedupStrategy.EXISTENCE)
    print(r_ex.pretty("After δ — strategy EXISTENCE (collapse to 1)"))
    print("""
  EXISTENCE reading:
    Both Alice and Bob are present (annotation 1).
    All provenance is lost — we cannot tell which inputs contributed
    or how many derivation paths existed.
    """)

    # LINEAGE
    r_lin = deduplication(pre, DedupStrategy.LINEAGE)
    print("  After δ — strategy LINEAGE (why-set extraction):")
    print("  " + "─" * 44)
    for key, ann in r_lin._data.items():
        row_d = dict(zip(["Name"], key))
        print(f"    {row_d}  →  {set(ann)}")
    print("""
  LINEAGE reading:
    Alice → {t1, t2, t3} — all three input tuples contributed.
    Bob   → {t1, t3}     — only Eng-dept tuples contributed.
                           t2 (Alice-HR) is absent because Bob has no
                           HR record, so no HR pair was formed in the join.

  This distinction is invisible with EXISTENCE but revealed by LINEAGE.
    """)


# ──────────────────────────────────────────────────────────────────────
# Inline correctness runner (no pytest dependency required)
# ──────────────────────────────────────────────────────────────────────

# ──────────────────────────────────────────────────────────────────────
# Correctness test helpers
# ──────────────────────────────────────────────────────────────────────

class _Tracker:
    """Minimal test result collector — no pytest required."""
    def __init__(self):
        self.passed   = 0
        self.failed   = 0
        self._failures = []

    def check(self, name: str, condition: bool, detail: str = "") -> None:
        if condition:
            self.passed += 1
            print(f"    PASS  {name}")
        else:
            self.failed += 1
            msg = f"    FAIL  {name}"
            if detail:
                msg += f"\n          {detail}"
            print(msg)
            self._failures.append(name)

    def summary(self) -> int:
        total = self.passed + self.failed
        print("\n  " + "─" * 58)
        print(f"  Results : {self.passed}/{total} passed", end="")
        if self.failed:
            print(f"   |  FAILED: {', '.join(self._failures)}")
        else:
            print("   |  all passed")
        print("  " + "─" * 58)
        return self.failed


def _worked_example_relation() -> KRelation:
    """Build the pre-dedup relation from the worked example."""
    t1 = Polynomial.from_var("t1")
    t2 = Polynomial.from_var("t2")
    t3 = Polynomial.from_var("t3")
    alice = t1.multiply(t1).add(t1.multiply(t3)).add(t2.multiply(t2))
    bob   = t1.multiply(t3).add(t3.multiply(t3))
    rel   = KRelation(["Name"], POLY_SR)
    rel._set_raw(("Alice",), alice)
    rel._set_raw(("Bob",),   bob)
    return rel


def _run_correctness_tests() -> int:
    print("\n" + "═" * 60)
    print("  CORRECTNESS TESTS")
    print("═" * 60)
    tr = _Tracker()
    one = Polynomial.one()

    # ── TC-1: EXISTENCE collapses polynomial annotations to one() ─────
    print("\n  [TC-1] EXISTENCE collapses polynomial annotations to one()")
    pre = _worked_example_relation()
    r = deduplication(pre, DedupStrategy.EXISTENCE)
    tr.check("Alice annotation == Polynomial.one()",
             r._data.get(("Alice",)) == one,
             f"got {r._data.get(('Alice',))}")
    tr.check("Bob annotation == Polynomial.one()",
             r._data.get(("Bob",)) == one,
             f"got {r._data.get(('Bob',))}")
    tr.check("Support size unchanged (still 2)",
             r.support_size() == 2,
             f"got {r.support_size()}")

    # ── TC-2: LINEAGE extracts correct variable sets ──────────────────
    print("\n  [TC-2] LINEAGE extracts correct why-sets")
    pre = _worked_example_relation()
    r   = deduplication(pre, DedupStrategy.LINEAGE)
    alice_why = r._data.get(("Alice",))
    bob_why = r._data.get(("Bob",))
    tr.check("Alice why-set == {t1, t2, t3}",
             alice_why == frozenset({"t1", "t2", "t3"}),
             f"got {alice_why}")
    tr.check("Bob why-set == {t1, t3}",
             bob_why == frozenset({"t1", "t3"}),
             f"got {bob_why}")
    tr.check("t2 absent from Bob's why-set",
             "t2" not in (bob_why or set()),
             f"Bob why-set: {bob_why}")

    # ── TC-3: Zero-annotation tuples excluded from both strategies ────
    print("\n  [TC-3] Zero-annotation tuples excluded from the result")
    rel = KRelation(["Name"], POLY_SR)
    rel._set_raw(("Alice",), Polynomial.from_var("t1"))
    rel._set_raw(("Ghost",), Polynomial.zero())
    for strat, label in [(DedupStrategy.EXISTENCE, "EXISTENCE"),
                         (DedupStrategy.LINEAGE,   "LINEAGE")]:
        r = deduplication(rel, strat)
        tr.check(f"{label}: Ghost (zero annotation) absent from result",
                 ("Ghost",) not in r._data,
                 f"Ghost found: {r._data.get(('Ghost',))}")

    # ── TC-4: Boolean semiring — EXISTENCE is a no-op ─────────────────
    print("\n  [TC-4] Boolean semiring — EXISTENCE is a no-op")
    brel = KRelation(["Name"], BOOL_SR)
    brel._set_raw(("Alice",), True)
    brel._set_raw(("Bob",),   True)
    rb = deduplication(brel, DedupStrategy.EXISTENCE)
    tr.check("Alice: True → True", rb._data.get(("Alice",)) is True)
    tr.check("Bob:   True → True", rb._data.get(("Bob",))   is True)

    # ── TC-5: Counting semiring — EXISTENCE discards multiplicity ─────
    print("\n  [TC-5] Counting semiring — multiplicity collapsed to 1")
    nrel = KRelation(["Name"], NAT_SR)
    nrel._set_raw(("Alice",), 42)
    nrel._set_raw(("Bob",),    7)
    rn = deduplication(nrel, DedupStrategy.EXISTENCE)
    tr.check("Alice: 42 → 1", rn._data.get(("Alice",)) == 1,
             f"got {rn._data.get(('Alice',))}")
    tr.check("Bob:    7 → 1", rn._data.get(("Bob",))   == 1,
             f"got {rn._data.get(('Bob',))}")

    # ── TC-6: Idempotence — δ(δ(R)) == δ(R) for EXISTENCE ────────────
    print("\n  [TC-6] Idempotence — EXISTENCE(EXISTENCE(R)) == EXISTENCE(R)")
    r1 = deduplication(_worked_example_relation(), DedupStrategy.EXISTENCE)
    r1_again = deduplication(r1, DedupStrategy.EXISTENCE)
    tr.check("Alice unchanged after second δ",
             r1_again._data.get(("Alice",)) == one)
    tr.check("Bob unchanged after second δ",
             r1_again._data.get(("Bob",))   == one)

    # ── TC-7: Single-variable polynomial (minimal nontrivial case) ────
    print("\n  [TC-7] Single-variable polynomial (simplest case)")
    srel = KRelation(["Name"], POLY_SR)
    srel._set_raw(("Carol",), Polynomial.from_var("t5"))
    tr.check("EXISTENCE: t5 → Polynomial.one()",
             deduplication(srel, DedupStrategy.EXISTENCE)._data.get(("Carol",)) == one,
             f"got {deduplication(srel, DedupStrategy.EXISTENCE)._data.get(('Carol',))}")
    tr.check("LINEAGE:   t5 → frozenset({'t5'})",
             deduplication(srel, DedupStrategy.LINEAGE)._data.get(("Carol",)) == frozenset({"t5"}),
             f"got {deduplication(srel, DedupStrategy.LINEAGE)._data.get(('Carol',))}")

    # ── TC-8: LINEAGE raises TypeError for non-Polynomial annotations ─
    print("\n  [TC-8] LINEAGE raises TypeError on non-Polynomial annotation")
    nrel2 = KRelation(["Name"], NAT_SR)
    nrel2._set_raw(("Alice",), 5)
    try:
        deduplication(nrel2, DedupStrategy.LINEAGE)
        tr.check("TypeError raised", False, "no exception was raised")
    except TypeError:
        tr.check("TypeError raised correctly", True)

    # ── TC-9: Empty relation → empty result ───────────────────────────
    print("\n  [TC-9] Empty relation → empty result")
    erel = KRelation(["Name"], POLY_SR)
    tr.check("EXISTENCE on empty → support_size == 0",
             deduplication(erel, DedupStrategy.EXISTENCE).support_size() == 0)
    tr.check("LINEAGE on empty → support_size == 0",
             deduplication(erel, DedupStrategy.LINEAGE).support_size()   == 0)

    return tr.summary()


# ──────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("Provenance-Aware Relational Algebra — Deduplication Module")
    print("Python", sys.version.split()[0])

    _run_worked_example()
    failures = _run_correctness_tests()
    run_benchmarks()

    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
