from pathlib import Path

import pytest

from benchmarks._sql import (
    _default_sql_limit_for_workload,
    _load_sql_workloads,
    _strip_sql_comments,
    _validate_sql_cli_workloads,
)


_ROOT = Path(__file__).resolve().parents[2]


def test_strip_sql_comments_removes_full_line_and_inline_comments():
    raw_sql = """
    -- header comment
    SELECT *
    FROM nation -- inline comment
    WHERE n_name = 'GERMANY'
    """

    assert _strip_sql_comments(raw_sql) == "SELECT *\nFROM nation\nWHERE n_name = 'GERMANY'"


def test_load_sql_workloads_translates_committed_sql_scripts():
    workloads = _load_sql_workloads(_ROOT / "test_sql_script", selected_names=None)

    assert [workload.name for workload in workloads] == [
        "q3",
        "q5",
        "q7",
        "q10",
        "q11",
        "q16",
        "q18",
        "q19",
    ]
    assert all(workload.sql_text for workload in workloads)
    assert all("--" not in workload.sql_text for workload in workloads)
    assert all(workload.ra_expression for workload in workloads)
    assert all(workload.parsed_expression is not None for workload in workloads)

    q3 = next(workload for workload in workloads if workload.name == "q3")
    q7 = next(workload for workload in workloads if workload.name == "q7")

    assert q3.table_refs == ("customer", "orders", "lineitem")
    assert q3.base_tables == ("customer", "orders", "lineitem")
    assert q7.table_refs == ("supplier", "lineitem", "orders", "customer", "n1", "n2")
    assert q7.base_tables == ("supplier", "lineitem", "orders", "customer", "nation")


def test_load_sql_workloads_accepts_q_prefix_and_numeric_names():
    workloads = _load_sql_workloads(
        _ROOT / "test_sql_script",
        selected_names=["q3", "11", "q19"],
    )

    assert [workload.name for workload in workloads] == ["q3", "q11", "q19"]


def test_load_sql_workloads_rejects_unknown_name():
    with pytest.raises(ValueError, match="Unknown SQL workload"):
        _load_sql_workloads(_ROOT / "test_sql_script", selected_names=["q999"])


def test_default_sql_limit_for_workload_scales_with_table_count():
    workloads = _load_sql_workloads(_ROOT / "test_sql_script", selected_names=["q3", "q7", "q10"])

    by_name = {workload.name: workload for workload in workloads}

    assert _default_sql_limit_for_workload(by_name["q3"], max_cross_product=1_000_000) == 100
    assert _default_sql_limit_for_workload(by_name["q10"], max_cross_product=1_000_000) == 31
    assert _default_sql_limit_for_workload(by_name["q7"], max_cross_product=1_000_000) == 10


def test_validate_sql_cli_workloads_requires_exactly_one_name():
    assert _validate_sql_cli_workloads(["q3"]) == ("q3",)

    with pytest.raises(ValueError, match="requires exactly one --sql-workloads"):
        _validate_sql_cli_workloads(None)

    with pytest.raises(ValueError, match="requires exactly one --sql-workloads"):
        _validate_sql_cli_workloads(["q3", "q5"])