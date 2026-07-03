"""In-document search for the zen editor — fuzzy, line-based, word-bounded.

A line is a hit in one of two ways, ranked in that order:

* **Phrase** — the query appears contiguously in the line (case-insensitive),
  spaces included. The strongest signal, always ranked above word matches.
* **Words** — every whitespace-separated query token fuzzy-matches *inside a
  single word* of the line (``vrfy`` finds ``verify``). Fuzzy never crosses a
  word boundary, so a query can't be assembled from one stray character per
  word across the line — that's noise, not a match.

The hit list ranks by score (see :func:`rank`); ``n``/``N`` navigation stays
spatial over the document-ordered hits. Pure Python — no Qt — so matching and
navigation are cheap to unit-test and independent of the overlay that
displays them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from textli.openfile import fuzzy_score

_RE_WORD = re.compile(r"\S+")

# Word-level scores are damped so that a phrase hit — the exact thing the
# reader typed — always outranks a line that merely contains each query word.
_WORD_MATCH_DAMPEN = 0.6


@dataclass(frozen=True)
class Hit:
    """One matching line: absolute character offsets into the searched text
    (``end`` excludes the newline), the line itself for preview, the match
    score (for ranking), and the emphasis ``spans`` (line-relative ranges of
    the phrase or of each matched word)."""
    line_no: int
    start: int
    end: int
    text: str
    score: float
    spans: tuple[tuple[int, int], ...]


def line_match(query: str,
               line: str) -> tuple[float, tuple[tuple[int, int], ...]] | None:
    """Score ``line`` against ``query`` — ``(score, spans)`` or ``None``.
    Phrase hits first; else every query token must match within one word."""
    q = query.strip()
    if not q:
        return None
    i = line.lower().find(q.lower())
    if i >= 0:                              # phrase — contiguous substring
        return fuzzy_score(q, line), ((i, i + len(q)),)
    total = 0.0
    spans: set[tuple[int, int]] = set()
    for token in q.split():
        best = None
        for m in _RE_WORD.finditer(line):
            s = fuzzy_score(token, m.group())
            if s is not None and (best is None or s > best[0]):
                best = (s, m.start(), m.end())
        if best is None:
            return None                     # a token no word can carry
        total += best[0]
        spans.add((best[1], best[2]))
    score = (total / len(q.split())) * _WORD_MATCH_DAMPEN
    return score, tuple(sorted(spans))


def find_hits(text: str, query: str) -> list[Hit]:
    """Every matching line, in document order — ``n``/``N`` walk this list
    spatially. An empty query matches nothing."""
    if not query.strip():
        return []
    hits = []
    pos = 0
    for i, line in enumerate(text.split("\n")):
        if line.strip():
            m = line_match(query, line)
            if m is not None:
                hits.append(Hit(i, pos, pos + len(line), line, m[0], m[1]))
        pos += len(line) + 1
    return hits


def rank(hits: list[Hit]) -> list[Hit]:
    """The hit-list order the overlay shows: best score first — a phrase hit
    far outranks word-level matches — document position as the tie-break.
    Navigation (``n``/``N``) stays spatial; only the list ranks."""
    return sorted(hits, key=lambda h: (-h.score, h.line_no))


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
