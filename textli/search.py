"""In-document search for the zen editor — fuzzy, line-based, document order.

The same matching feel as the ``go`` open-file dialog (the shared scorer from
:mod:`textli.openfile`), applied per *line*: a hit is a line whose text the
query fuzzy-matches. Hits are kept in document order — the list doubles as an
outline of where matches sit, and ``n`` / ``N`` need a stable spatial
sequence — not in score order.

Pure Python — no Qt — so ranking and navigation are cheap to unit-test and
independent of the overlay that displays them.
"""

from __future__ import annotations

from dataclasses import dataclass

from textli.openfile import fuzzy_score


@dataclass(frozen=True)
class Hit:
    """One matching line: absolute character offsets into the searched text
    (``end`` excludes the newline) plus the line itself for preview."""
    line_no: int
    start: int
    end: int
    text: str


def find_hits(text: str, query: str) -> list[Hit]:
    """Every line of ``text`` the query fuzzy-matches, in document order.
    An empty query matches nothing (the overlay shows hits as you type)."""
    if not query.strip():
        return []
    hits = []
    pos = 0
    for i, line in enumerate(text.split("\n")):
        if line.strip() and fuzzy_score(query, line) is not None:
            hits.append(Hit(i, pos, pos + len(line), line))
        pos += len(line) + 1
    return hits


def match_range(query: str, line: str) -> tuple[int, int] | None:
    """The emphasis region within a hit line: the (case-insensitive)
    contiguous-substring match when there is one, else ``None`` (a scattered
    fuzzy hit — the whole line is the preview)."""
    i = line.lower().find(query.lower())
    return (i, i + len(query)) if i >= 0 else None


def initial_index(hits: list[Hit], pos: int) -> int:
    """Where the selection starts: the first hit at or after ``pos`` — search
    feels anchored to where the reader is — wrapping to the first hit."""
    for i, h in enumerate(hits):
        if h.end >= pos:
            return i
    return 0


def next_hit(hits: list[Hit], pos: int, direction: int) -> Hit | None:
    """The hit ``n``/``N`` lands on from ``pos``: the nearest hit strictly
    after (``direction=+1``) or before (``-1``), wrapping around the document
    like vim. ``None`` when there are no hits."""
    if not hits:
        return None
    if direction >= 0:
        for h in hits:
            if h.start > pos:
                return h
        return hits[0]
    for h in reversed(hits):
        if h.start < pos:
            return h
    return hits[-1]
