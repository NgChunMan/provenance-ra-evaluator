"""Shared dataclasses, utilities, and path constants for all benchmark layers."""

from __future__ import annotations

import gc
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from src.relation.k_relation import KRelation
from src.semirings import BOOLFUNC_SR, BoolFunc
from src.strategies import DedupStrategy

_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_TPCH_DIR = _ROOT / "data" / "tpch"
_DEFAULT_TPCH_CACHE_DIR = _ROOT / ".bench_cache" / "tpch"
_DEFAULT_SQL_DIR = _ROOT / "test_sql_script"


@dataclass(frozen=True)
class OperatorBenchmarkRow:
    operator: str         # operator symbol + name, e.g. "σ (Selection)"
    variant: str | None   # dedup strategy ("existence"/"how_provenance"); None for other ops
    bool_us: float        # BOOL_SR median time in microseconds
    boolfunc_us: float    # BOOLFUNC_SR median time in microseconds
    overhead_x: float     # boolfunc_us / bool_us
    input_rows: int       # total input tuples (sum across all inputs for binary ops)
    output_rows: int      # tuples in the BoolFunc output support
    clause_count: int     # total clauses across all BoolFunc output annotations
    literal_count: int    # total literals across all BoolFunc output annotations
    description: str


@dataclass(frozen=True)
class MicroBenchmarkRow:
    name: str
    nat_ms: float
    boolfunc_ms: float
    overhead_x: float
    output_rows: int
    clause_count: int
    literal_count: int
    description: str


@dataclass(frozen=True)
class MacroWorkload:
    name: str
    description: str
    execute: Callable[[dict[str, KRelation], DedupStrategy], KRelation]


@dataclass(frozen=True)
class MacroBenchmarkRow:
    source: str
    name: str
    nat_ms: float
    boolfunc_ms: float
    overhead_x: float
    output_rows: int
    clause_count: int
    literal_count: int
    description: str


@dataclass(frozen=True)
class SQLWorkload:
    name: str
    description: str
    sql_file: Path
    sql_text: str
    ra_expression: str
    parsed_expression: Any
    alias_map: dict[str, str]
    table_refs: tuple[str, ...]
    base_tables: tuple[str, ...]


@dataclass(frozen=True)
class SQLBenchmarkRow:
    source: str
    name: str
    limit: int
    bool_ms: float
    boolfunc_ms: float
    overhead_x: float
    output_rows: int
    clause_count: int
    literal_count: int
    description: str


def _progress(message: str) -> None:
    print(message, flush=True)


def _measure(
    fn: Callable[[], KRelation],
    repeat: int,
    warmup: int,
    progress_label: str | None = None,
) -> tuple[list[float], KRelation]:
    """Return wall-clock timings in milliseconds and the final result."""
    result: KRelation | None = None

    for warmup_index in range(warmup):
        if progress_label is not None:
            _progress(f"{progress_label} warmup {warmup_index + 1}/{warmup} started")
        result = fn()
        if progress_label is not None:
            _progress(f"{progress_label} warmup {warmup_index + 1}/{warmup} finished")

    samples: list[float] = []
    for sample_index in range(repeat):
        gc.collect()
        if progress_label is not None:
            _progress(f"{progress_label} sample {sample_index + 1}/{repeat} started")
        started = time.perf_counter_ns()
        gc_enabled = gc.isenabled()
        if gc_enabled:
            gc.disable()
        try:
            result = fn()
        finally:
            if gc_enabled:
                gc.enable()
        elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000
        samples.append(elapsed_ms)
        if progress_label is not None:
            _progress(
                f"{progress_label} sample {sample_index + 1}/{repeat} finished in {elapsed_ms:.3f} ms"
            )

    assert result is not None
    return samples, result


def _annotation_for(index: int, prefix: str, use_boolfunc: bool):
    if use_boolfunc:
        return BoolFunc.var(f"{prefix}{index}")
    return 1


def _build_disjunction(prefix: str, width: int) -> BoolFunc:
    formula = BOOLFUNC_SR.zero()
    for index in range(width):
        formula = BOOLFUNC_SR.add(formula, BoolFunc.var(f"{prefix}{index}"))
    return formula


def _boolfunc_complexity(relation: KRelation) -> tuple[int, int]:
    """Return total clause count and total literal count for a BoolFunc result."""
    clauses = 0
    literals = 0

    for annotation in relation._data.values():
        if relation.semiring.is_zero(annotation):
            continue
        formula = annotation._formula
        clauses += len(formula)
        literals += sum(len(clause) for clause in formula)

    return clauses, literals


def _support_keys(relation: KRelation) -> set[tuple[Any, ...]]:
    return {
        key for key, annotation in relation.items()
        if not relation.semiring.is_zero(annotation)
    }
