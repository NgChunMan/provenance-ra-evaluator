"""
CSV loader: reads CSV files from data/ into KRelation objects.

File format
-----------
The CSV files follow the convention established by the cs4221 framework:

    Row 1 — column type hints (e.g. INT, TEXT)
    Row 2 — column names (the schema header)
    Row 3+ — data rows

Each loaded tuple receives annotation semiring.one(), meaning it is
present exactly once before any operators are applied.
"""

from __future__ import annotations

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
    raise NotImplementedError

