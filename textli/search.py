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


# A hit must earn at least this much score per query character. A scattered
# one-char-here-one-char-there subsequence ("right" "matching" `soRts dynamIc
# … paGes alpHabeTically`) scores ≈1 per char; genuine matches — substrings,
# word starts, consecutive runs — score ≥3. Below the bar it's noise, not a
# hit.
MIN_SCORE_PER_CHAR = 3.0


@dataclass(frozen=True)
class Hit:
    """One matching line: absolute character offsets into the searched text
    (``end`` excludes the newline), the line itself for preview, and its
    match score (for ranking the list)."""
    line_no: int
    start: int
    end: int
    text: str
    score: float


def find_hits(text: str, query: str) -> list[Hit]:
    """Every line of ``text`` the query matches *well enough* (see
    :data:`MIN_SCORE_PER_CHAR`), in document order — ``n``/``N`` walk this
    list spatially. An empty query matches nothing."""
    q = query.strip()
    if not q:
        return []
    bar = MIN_SCORE_PER_CHAR * len(q)
    hits = []
    pos = 0
    for i, line in enumerate(text.split("\n")):
        if line.strip():
            score = fuzzy_score(query, line)
            if score is not None and score >= bar:
                hits.append(Hit(i, pos, pos + len(line), line, score))
        pos += len(line) + 1
    return hits


def rank(hits: list[Hit]) -> list[Hit]:
    """The hit-list order the overlay shows: best score first — an exact
    substring far outranks a scattered fuzzy match — document position as the
    tie-break. Navigation (``n``/``N``) stays spatial; only the list ranks."""
    return sorted(hits, key=lambda h: (-h.score, h.line_no))


def match_range(query: str, line: str) -> tuple[int, int] | None:
    """The emphasis region within a hit line: the (case-insensitive)
    contiguous-substring match when there is one, else ``None`` (a scattered
    fuzzy hit — the whole line is the preview)."""
    i = line.lower().find(query.lower())
    return (i, i + len(query)) if i >= 0 else None


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
