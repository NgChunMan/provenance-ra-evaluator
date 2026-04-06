"""SQL benchmarks on the simplified TPC-H queries under test_sql_script/.

Compares BOOL_SR against BOOLFUNC_SR on the same translated SQL workload.
The following costs are intentionally excluded from the timed region:
  - SQL comment stripping
  - SQL translation and RA parsing
  - CSV loading and tuple-variable assignment
  - optional SF CSV generation

The SQL layer is separate on purpose. The current evaluator has no join
optimizer, so translated TPC-H SQL plans can be dominated by large
cartesian products. That is still a useful comparison, but it answers a
different question from the curated pushdown-heavy macro workloads.
"""

from __future__ import annotations

import statistics
import time
from pathlib import Path
from typing import Sequence

from src.evaluator import Evaluator
from src.io.tpch_loader import load_tpch_csvs
from src.parser import parse
from src.parser.grammar import Cross as RACross
from src.parser.grammar import Dedup as RADedup
from src.parser.grammar import Project as RAProject
from src.parser.grammar import Select as RASelect
from src.parser.grammar import Table as RATable
from src.parser.grammar import Union as RAUnion
from src.relation.k_relation import KRelation
from src.semirings import BOOLFUNC_SR, BOOL_SR
from src.strategies import DedupStrategy
from src.sql_to_ra import sql_to_ra_with_aliases

from ._common import (
    SQLBenchmarkRow,
    SQLWorkload,
    _boolfunc_complexity,
    _measure,
    _progress,
    _support_keys,
)
from ._tpch import _tpch_boolfunc_annotation


def _strip_sql_comments(sql_text: str) -> str:
    cleaned_lines: list[str] = []
    for line in sql_text.splitlines():
        body = line.split("--", 1)[0].strip()
        if body:
            cleaned_lines.append(body)
    return "\n".join(cleaned_lines)


def _extract_sql_description(raw_sql_text: str, workload_name: str) -> str:
    for line in raw_sql_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("--"):
            return stripped[2:].strip()
    return f"Translated TPC-H SQL workload {workload_name}."


def _normalize_sql_workload_name(name: str) -> str:
    lowered = name.strip().lower()
    if lowered.startswith("q"):
        return lowered[1:]
    return lowered


def _validate_sql_cli_workloads(
    selected_names: Sequence[str] | None,
) -> tuple[str, ...]:
    if not selected_names:
        raise ValueError(
            "SQL benchmark mode requires exactly one --sql-workloads NAME. "
            "Running all SQL workloads in one invocation is intentionally disabled; "
            "run one script at a time, for example: --sql-workloads q3."
        )
    if len(selected_names) != 1:
        raise ValueError(
            "SQL benchmark mode requires exactly one --sql-workloads NAME so each "
            "query is benchmarked independently."
        )
    return tuple(selected_names)


def _collect_ra_table_refs(expression) -> list[str]:
    if isinstance(expression, RATable):
        return [expression.name]
    if isinstance(expression, (RASelect, RAProject, RADedup)):
        return _collect_ra_table_refs(expression.rel)
    if isinstance(expression, (RACross, RAUnion)):
        return _collect_ra_table_refs(expression.lhs) + _collect_ra_table_refs(expression.rhs)
    raise ValueError(f"Unsupported SQL benchmark expression node: {type(expression).__name__}")


def _default_sql_limit_for_workload(
    workload: SQLWorkload,
    max_cross_product: int,
) -> int:
    table_ref_count = len(workload.table_refs)
    limit = 1
    while (limit + 1) ** table_ref_count <= max_cross_product:
        limit += 1
    return limit


def _load_sql_workloads(
    sql_dir: Path,
    selected_names: Sequence[str] | None,
) -> list[SQLWorkload]:
    if not sql_dir.exists():
        raise ValueError(f"SQL workload directory does not exist: {sql_dir}")

    sql_files = sorted(
        (path for path in sql_dir.glob("*.sql") if path.is_file()),
        key=lambda path: (0, int(path.stem)) if path.stem.isdigit() else (1, path.stem),
    )
    if not sql_files:
        raise ValueError(f"No SQL workload files found in: {sql_dir}")

    workloads: list[SQLWorkload] = []
    for sql_file in sql_files:
        raw_sql_text = sql_file.read_text(encoding="utf-8")
        sql_text = _strip_sql_comments(raw_sql_text)
        workload_name = f"q{sql_file.stem}"
        description = _extract_sql_description(raw_sql_text, workload_name)
        ra_expression, alias_map = sql_to_ra_with_aliases(sql_text)
        parsed_expression = parse(ra_expression)
        table_refs = tuple(_collect_ra_table_refs(parsed_expression))
        base_tables = tuple(dict.fromkeys(alias_map.get(name, name) for name in table_refs))
        workloads.append(
            SQLWorkload(
                name=workload_name,
                description=description,
                sql_file=sql_file,
                sql_text=sql_text,
                ra_expression=ra_expression,
                parsed_expression=parsed_expression,
                alias_map=alias_map,
                table_refs=table_refs,
                base_tables=base_tables,
            )
        )

    if not selected_names:
        return workloads

    workload_by_name = {
        _normalize_sql_workload_name(workload.name): workload
        for workload in workloads
    }
    missing = [
        name for name in selected_names
        if _normalize_sql_workload_name(name) not in workload_by_name
    ]
    if missing:
        known = ", ".join(workload.name for workload in workloads)
        raise ValueError(
            f"Unknown SQL workload(s): {missing!r}. Known workloads: {known}"
        )

    return [
        workload_by_name[_normalize_sql_workload_name(name)]
        for name in selected_names
    ]


def _load_sql_tables(
    csv_dir: Path,
    tables: Sequence[str],
    limit: int | None,
) -> tuple[dict[str, KRelation], dict[str, KRelation]]:
    bool_tables = load_tpch_csvs(csv_dir, BOOL_SR, tables=list(tables), limit=limit)
    boolfunc_tables = load_tpch_csvs(
        csv_dir,
        BOOLFUNC_SR,
        tables=list(tables),
        limit=limit,
        annotation_factory=_tpch_boolfunc_annotation,
    )
    return bool_tables, boolfunc_tables


def _run_sql_workload(
    source: str,
    workload: SQLWorkload,
    limit: int,
    bool_tables: dict[str, KRelation],
    boolfunc_tables: dict[str, KRelation],
    strategy: DedupStrategy,
    repeat: int,
    warmup: int,
    progress_prefix: str | None = None,
) -> SQLBenchmarkRow:
    bool_evaluator = Evaluator(
        bool_tables,
        BOOL_SR,
        strategy,
        alias_map=workload.alias_map,
    )
    boolfunc_evaluator = Evaluator(
        boolfunc_tables,
        BOOLFUNC_SR,
        strategy,
        alias_map=workload.alias_map,
    )

    bool_fn = lambda: bool_evaluator.evaluate(workload.parsed_expression)
    boolfunc_fn = lambda: boolfunc_evaluator.evaluate(workload.parsed_expression)

    bool_samples, bool_result = _measure(
        bool_fn,
        repeat=repeat,
        warmup=warmup,
        progress_label=(f"{progress_prefix} BOOL_SR" if progress_prefix is not None else None),
    )
    boolfunc_samples, boolfunc_result = _measure(
        boolfunc_fn,
        repeat=repeat,
        warmup=warmup,
        progress_label=(
            f"{progress_prefix} BOOLFUNC_SR" if progress_prefix is not None else None
        ),
    )

    if _support_keys(bool_result) != _support_keys(boolfunc_result):
        raise ValueError(
            f"Semiring result support mismatch for SQL workload {workload.name!r} from {source}"
        )

    bool_ms = statistics.median(bool_samples)
    boolfunc_ms = statistics.median(boolfunc_samples)
    overhead_x = boolfunc_ms / bool_ms if bool_ms > 0 else float("inf")
    clause_count, literal_count = _boolfunc_complexity(boolfunc_result)

    return SQLBenchmarkRow(
        source=source,
        name=workload.name,
        limit=limit,
        bool_ms=bool_ms,
        boolfunc_ms=boolfunc_ms,
        overhead_x=overhead_x,
        output_rows=boolfunc_result.support_size(),
        clause_count=clause_count,
        literal_count=literal_count,
        description=workload.description,
    )


def _benchmark_sql_workloads(
    workloads: Sequence[SQLWorkload],
    sources: Sequence[tuple[str, Path]],
    strategy: DedupStrategy,
    repeat: int,
    warmup: int,
    limit: int | None,
    max_cross_product: int,
) -> list[SQLBenchmarkRow]:
    rows: list[SQLBenchmarkRow] = []
    total_workloads = len(workloads) * len(sources)
    completed = 0

    for source_label, source_dir in sources:
        for workload in workloads:
            completed += 1
            effective_limit = (
                limit
                if limit is not None
                else _default_sql_limit_for_workload(workload, max_cross_product=max_cross_product)
            )
            progress_prefix = f"[sql {completed}/{total_workloads}] {source_label} / {workload.name}"
            _progress(
                f"[sql] loading source {source_label} from {source_dir} "
                f"for {workload.name} with per-table limit {effective_limit}"
            )
            load_started = time.perf_counter()
            bool_tables, boolfunc_tables = _load_sql_tables(
                source_dir,
                tables=workload.base_tables,
                limit=effective_limit,
            )
            _progress(
                f"[sql] loaded source {source_label} for {workload.name} in "
                f"{time.perf_counter() - load_started:.2f}s"
            )
            _progress(f"{progress_prefix} started")
            rows.append(
                _run_sql_workload(
                    source=source_label,
                    workload=workload,
                    limit=effective_limit,
                    bool_tables=bool_tables,
                    boolfunc_tables=boolfunc_tables,
                    strategy=strategy,
                    repeat=repeat,
                    warmup=warmup,
                    progress_prefix=progress_prefix,
                )
            )
            row = rows[-1]
            _progress(
                f"{progress_prefix} finished: BOOL {row.bool_ms:.3f} ms, "
                f"BoolFunc {row.boolfunc_ms:.3f} ms, overhead {row.overhead_x:.2f}x"
            )

    return rows


def _build_sql_benchmark_table_lines(rows: list[SQLBenchmarkRow]) -> list[str]:
    rendered_rows = [
        (
            row.source,
            row.name,
            str(row.limit),
            f"{row.bool_ms:.3f}",
            f"{row.boolfunc_ms:.3f}",
            f"{row.overhead_x:.2f}x",
            str(row.output_rows),
            str(row.clause_count),
            str(row.literal_count),
        )
        for row in rows
    ]
    headers = (
        "Source",
        "Query",
        "Limit",
        "BOOL ms",
        "BoolFunc ms",
        "Overhead",
        "Rows",
        "Clauses",
        "Literals",
    )
    alignments = ("<", "<", ">", ">", ">", ">", ">", ">", ">")

    widths = []
    for index, header in enumerate(headers):
        widths.append(
            max(
                len(header),
                *(len(values[index]) for values in rendered_rows),
            )
        )

    def _format_line(values: tuple[str, ...]) -> str:
        parts: list[str] = []
        for value, width, alignment in zip(values, widths, alignments):
            if alignment == "<":
                parts.append(f"{value:<{width}}")
            else:
                parts.append(f"{value:>{width}}")
        return "  ".join(parts)

    header_line = _format_line(headers)
    table_lines = [header_line, "-" * len(header_line)]
    table_lines.extend(_format_line(values) for values in rendered_rows)
    return table_lines


def _sql_zero_output_note(rows: list[SQLBenchmarkRow]) -> str | None:
    zero_output_rows = [row for row in rows if row.output_rows == 0]
    if not zero_output_rows:
        return None

    affected = ", ".join(f"{row.name} (limit {row.limit})" for row in zero_output_rows)
    return (
        "Rows=0 means the query produced an empty output relation for the loaded table "
        "slice at that limit. With no surviving output tuples, there are no BoolFunc "
        f"annotations to count, so Clauses and Literals are also 0. Affected workloads: {affected}."
    )


def _print_sql_benchmark_rows(
    rows: list[SQLBenchmarkRow],
    strategy: DedupStrategy,
) -> None:
    table_lines = _build_sql_benchmark_table_lines(rows)
    rule_width = max(
        len("TPC-H SQL SEMIRING BENCHMARKS"),
        *(len(line) for line in table_lines),
    )

    print("\n" + "=" * rule_width)
    print("TPC-H SQL SEMIRING BENCHMARKS")
    print("=" * rule_width)
    print("Baseline semiring: BOOL_SR (set semantics, tuple presence only)")
    print("Provenance run: BOOLFUNC_SR with one provenance variable per loaded TPC-H tuple")
    print(f"Dedup strategy: {strategy.name}")
    print("Timed region: translated RA evaluation only")
    print(
        "Excluded costs: CSV loading, tuple-variable assignment, SQL comment stripping, "
        "SQL translation, RA parsing, optional SF CSV generation"
    )
    print()

    for line in table_lines:
        print(line)

    print("\nSQL benchmark notes")
    print("- These workloads use the committed simplified TPC-H SQL scripts under test_sql_script/ and measure the marginal cost of symbolic provenance over the same query support.")
    print("- If --tpch-limit is omitted, SQL mode applies an automatic per-workload row cap so the naive translated cross-product plans stay runnable.")
    zero_output_note = _sql_zero_output_note(rows)
    if zero_output_note is not None:
        print(f"- {zero_output_note}")
    print("- BOOL_SR is the right floor for translated SQL because DISTINCT-heavy TPC-H rewrites mostly ask presence questions at the output.")
    print("- Queries with low-cardinality outputs and many joins usually show the largest BoolFunc blow-up because many witnesses collapse into a small output support.")
