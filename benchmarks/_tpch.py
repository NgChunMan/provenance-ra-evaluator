"""TPC-H data source resolution and per-tuple annotation factory."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Sequence

from src.io.tpch_loader import generate_tpch_csvs
from src.semirings import BoolFunc

from ._common import _progress


def _format_sf(sf: float) -> str:
    return format(sf, "g")


def _resolve_tpch_sources(
    csv_dir: Path,
    cache_dir: Path,
    scale_factors: Sequence[float] | None,
    limit: int | None,
) -> list[tuple[str, Path]]:
    if not scale_factors:
        return [("committed_csv_sf≈0.01", csv_dir)]

    sources: list[tuple[str, Path]] = []
    cache_dir.mkdir(parents=True, exist_ok=True)

    for sf in scale_factors:
        sf_label = _format_sf(sf)
        limit_label = str(limit) if limit is not None else "full"
        source_dir = cache_dir / f"sf_{sf_label}__limit_{limit_label}"

        required_csv = source_dir / "lineitem.csv"
        if not required_csv.exists():
            _progress(f"Preparing cached TPC-H CSVs for sf={sf_label} at {source_dir}")
            started = time.perf_counter()
            generate_tpch_csvs(sf=sf, output_dir=source_dir, limit=limit)
            _progress(
                f"Prepared cached TPC-H CSVs for sf={sf_label} in {time.perf_counter() - started:.2f}s"
            )
        else:
            _progress(f"Using cached TPC-H CSVs for sf={sf_label} at {source_dir}")

        sources.append((f"generated_sf={sf_label}", source_dir))

    return sources


def _tpch_boolfunc_annotation(table_name: str, row_index: int, row: dict[str, Any]) -> BoolFunc:
    return BoolFunc.var(f"{table_name}_{row_index}")
