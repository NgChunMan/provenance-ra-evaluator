"""
CSV loader: reads CSV files from data/ into KRelation objects.
Each loaded tuple receives annotation semiring.one(), meaning it is
present exactly once before any operators are applied.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Union

from src.semirings.base import Semiring
from src.relation.k_relation import KRelation


def load_csv(
    filepath: Union[str, Path],
    semiring: Semiring,
) -> KRelation:
    """
    Load a CSV file into a KRelation.

    Each data row is inserted with annotation semiring.one().
    If a row key appears more than once in the file, annotations are
    accumulated via semiring.add() (matching KRelation.insert behaviour).

    Parameters
    ----------
    filepath : str or Path
        Path to the CSV file.
    semiring : Semiring
        The semiring to annotate tuples with.

    Returns
    -------
    KRelation
        Loaded relation with schema derived from the CSV header row.

    Raises
    ------
    FileNotFoundError
        If the file does not exist at the given path.
    ValueError
        If the file has fewer than two rows (no header or no data).
    """
    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"CSV file not found: {filepath}")

    with open(filepath, "r", encoding="utf-8-sig") as f:
        lines = [line.strip() for line in f if line.strip()]

    if len(lines) < 2:
        raise ValueError(
            f"CSV file must have at least a type row and a header row; "
            f"got {len(lines)} line(s)"
        )

    type_hints = [t.strip() for t in lines[0].split(",")]

    schema = [col.strip() for col in lines[1].split(",")]

    rel = KRelation(schema, semiring)

    # Row 2+: data rows
    for line in lines[2:]:
        values = [v.strip() for v in line.split(",")]
        row = {}
        for col, val, hint in zip(schema, values, type_hints):
            if hint == "INT":
                row[col] = int(val)
            elif hint == "DATE":
                row[col] = date.fromisoformat(val)
            elif hint == "DECIMAL":
                row[col] = Decimal(val)
            else:
                row[col] = val
        rel.insert(row)

    return rel

