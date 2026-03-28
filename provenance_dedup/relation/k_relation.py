"""
KRelation — a K-annotated relational table.

A K-relation over attribute set U is a function

    R : U-Tup → K

such that its *support*  supp(R) = { t | R(t) ≠ 0 }  is finite.

Tuples outside the support are conceptually present with annotation
semiring.zero() — they are simply not stored.

Implementation
--------------
Internally a Dict[row_tuple, annotation].
The row tuple is constructed by projecting each row dict onto
self.schema in order, giving a hashable, position-independent key.

insert() accumulates annotations via semiring.add() so that
inserting the same tuple twice naturally implements multiset union:

    insert("Alice", ann=t1)
    insert("Alice", ann=t2)
    → stored annotation: semiring.add(t1, t2) = t1 + t2
"""

from __future__ import annotations

from typing import Any, Dict, Iterator, List, Tuple

from provenance_dedup.semirings.base import Semiring


class KRelation:
    """An annotated relation over a fixed ordered schema."""

    def __init__(self, schema: List[str], semiring: Semiring) -> None:
        self.schema   = schema
        self.semiring = semiring
        self._data: Dict[Tuple, Any] = {}

    def insert(self, row: Dict[str, Any], annotation: Any = None) -> None:
        """
        Insert a tuple given as a column→value dict.

        If the tuple is already present, its existing annotation and the
        new one are combined with semiring.add().  This means you can call
        insert() multiple times with the same row to build a multiset.

        Omitting annotation defaults to semiring.one() (present once).
        """
        if annotation is None:
            annotation = self.semiring.one()
        key = tuple(row[c] for c in self.schema)
        existing = self._data.get(key)
        self._data[key] = (
            self.semiring.add(existing, annotation)
            if existing is not None
            else annotation
        )


    def _set_raw(self, key: Tuple, annotation: Any) -> None:
        """
        Directly set a row key → annotation without going through insert().
        Used internally (e.g. tests, operator implementations) when the
        row key is already in the canonical tuple form.
        """
        self._data[key] = annotation


    def annotation_of(self, **row_kwargs) -> Any:
        """
        Return the annotation for the given row (keyword = column name).
        Returns semiring.zero() if the row is not in the support.
        """
        key = tuple(row_kwargs[c] for c in self.schema)
        return self._data.get(key, self.semiring.zero())


    def items(self) -> Iterator[Tuple[Tuple, Any]]:
        """Iterate (row_key_tuple, annotation) pairs over the full storage."""
        return self._data.items()


    def support_size(self) -> int:
        """Number of tuples with a nonzero annotation."""
        return sum(
            1 for v in self._data.values()
            if not self.semiring.is_zero(v)
        )

    def pretty(self, title: str = "") -> str:
        """Return a formatted multi-line string of the relation."""
        sep  = "═" * 58
        dash = "─" * 58
        lines = ["\n" + sep]
        if title:
            lines.append(f"  {title}")
        lines.append(f"  Semiring : {self.semiring.name}")
        lines.append(f"  Schema   : {self.schema}")
        lines.append(f"  Support  : {self.support_size()} tuple(s)")
        lines.append(dash)
        for key, ann in self._data.items():
            if not self.semiring.is_zero(ann):
                row_d = dict(zip(self.schema, key))
                lines.append(f"    {row_d}  →  {ann}")
        lines.append(sep)
        return "\n".join(lines)


    def __repr__(self) -> str:
        return (
            f"KRelation(schema={self.schema}, "
            f"semiring={self.semiring.name!r}, "
            f"support_size={self.support_size()})"
        )
