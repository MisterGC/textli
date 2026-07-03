"""Open-file matching for the `go` dialog — history fuzzy + filesystem segments.

Two deliberately different matching modes, so results stay predictable:

* **History** (files you opened before, and the directories that contained
  them) is matched *fuzzily over the full path* — typing ``special`` finds
  ``/my/cool/special_path/notes.md`` because you've been there. Scoring
  rewards matches at segment boundaries (``/ _ - .``) and in the basename,
  with the history's own recency order as the tie-break.

* **The filesystem** is only completed *per segment*, shell-style — ``/Ho``
  suggests ``/Home`` but never digs up ``/some/other/dir/Home``. A query
  engages filesystem completion only when it looks like a path (contains a
  ``/`` or starts with ``~``); a bare word searches history alone.

Directory candidates carry a trailing ``/`` so callers (and the reader) can
tell them from files at a glance. Pure Python — no Qt — so the ranking is
cheap to unit-test and independent of the overlay that displays it.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

# History keeps this many files (LRU). Together with the directories derived
# from them this stays a personal, high-signal candidate set — large enough to
# cover months of writing, small enough that fuzzy results never feel noisy.
HISTORY_MAX = 200

# Characters that start a new "word" inside a path — matches here score high.
_BOUNDARIES = set("/_-. ")


# ── History (LRU list of file paths, most recent first) ──


def push_history(entries: list[str], path: str) -> list[str]:
    """Return ``entries`` with ``path`` promoted to the front (LRU, deduped,
    capped at :data:`HISTORY_MAX`). ``entries`` itself is left untouched."""
    path = os.path.abspath(os.path.expanduser(path))
    out = [path] + [e for e in entries if e != path]
    return out[:HISTORY_MAX]


def history_dirs(entries: list[str]) -> list[str]:
    """The directories that contained the history's files, most recent first,
    deduped, each with a trailing ``/``."""
    seen: dict[str, None] = {}
    for e in entries:
        d = os.path.dirname(e)
        if d:
            seen.setdefault(d.rstrip("/") + "/", None)
    return list(seen)


# ── Fuzzy scoring (history candidates) ──


def fuzzy_score(query: str, candidate: str) -> float | None:
    """Score ``candidate`` against ``query`` (higher is better); ``None`` when
    the query isn't a subsequence of the candidate at all.

    Case-insensitive. A contiguous-substring hit scores far above a scattered
    subsequence; boundary starts (segment/word starts) and basename hits are
    boosted; longer candidates pay a mild penalty so short paths win ties."""
    if not query:
        return 0.0
    q, c = query.lower(), candidate.lower()
    base = os.path.basename(c.rstrip("/"))
    length_penalty = len(c) * 0.01

    # Contiguous substring — the common, high-confidence case.
    idx = c.find(q)
    if idx >= 0:
        score = 100.0
        if idx == 0 or c[idx - 1] in _BOUNDARIES:
            score += 40.0                      # starts a segment/word
        if q in base:
            score += 40.0                      # sits in the basename
        return score - length_penalty

    # Scattered subsequence — walk the query through the candidate, preferring
    # boundary matches (a lookahead per char, not a full DP — plenty for paths
    # and prose lines). The boundary jump can overshoot and consume characters
    # a later query char needs, so a failed walk falls back to the plain
    # leftmost walk — which succeeds for every true subsequence.
    def walk(prefer_boundary: bool) -> float | None:
        score, ci, prev = 0.0, 0, -2
        for qch in q:
            i = c.find(qch, ci)
            if i < 0:
                return None
            if prefer_boundary:
                # Jump to the next *boundary* occurrence if there is one ahead.
                j = i
                while j >= 0 and not (j == 0 or c[j - 1] in _BOUNDARIES):
                    j = c.find(qch, j + 1)
                if j >= 0:
                    i = j
            if i == 0 or c[i - 1] in _BOUNDARIES:
                score += 6.0                   # boundary hit
            elif i == prev + 1:
                score += 4.0                   # run continues
            else:
                score += 1.0
            prev, ci = i, i + 1
        return score

    score = walk(True)
    if score is None:
        score = walk(False)
    if score is None:
        return None
    return score - length_penalty


def rank_history(query: str, entries: list[str]) -> list[str]:
    """History candidates (files first-class, their dirs too) ranked for
    ``query``: score descending, history recency as the tie-break. Scores are
    quantized to whole points here so the mild length penalty can't drown the
    recency order — a *recently* opened long path must beat a stale short one
    that matches equally well. Non-matching candidates are dropped."""
    candidates = list(entries) + history_dirs(entries)
    scored = []
    for recency, cand in enumerate(candidates):
        s = fuzzy_score(query, cand)
        if s is not None:
            scored.append((-round(s), recency, cand))
    scored.sort()
    return [cand for (_s, _r, cand) in scored]


# ── Filesystem (per-segment completion only) ──


def looks_like_path(query: str) -> bool:
    """Whether ``query`` engages filesystem completion — it contains a ``/`` or
    reaches for home. Bare words stay history-only."""
    return "/" in query or query.startswith("~")


def segment_complete(typed: str) -> list[str]:
    """Shell-style completion of the *last segment* of ``typed``: entries of the
    parent directory whose name starts with the partial segment
    (case-insensitive). Directories (trailing ``/``) and ``.md`` files only;
    hidden entries only when explicitly asked for (partial starts with ``.``).
    Sorted directories-first, then by name. Anything unreadable yields ``[]``."""
    if not looks_like_path(typed):
        return []
    expanded = os.path.expanduser(typed)
    if typed.endswith("/"):
        d, part = expanded, ""
    else:
        d, part = os.path.split(expanded)
    if not os.path.isdir(d):
        return []
    part_l = part.lower()
    dirs, files = [], []
    try:
        names = os.listdir(d)
    except OSError:
        return []
    for name in names:
        if name.startswith(".") and not part.startswith("."):
            continue
        if not name.lower().startswith(part_l):
            continue
        full = os.path.join(d, name)
        if os.path.isdir(full):
            dirs.append(full.rstrip("/") + "/")
        elif name.lower().endswith(".md"):
            files.append(full)
    return sorted(dirs, key=str.lower) + sorted(files, key=str.lower)


# ── Combined suggestions for the dialog ──


@dataclass(frozen=True)
class Candidate:
    """One row the dialog offers: an absolute ``path`` (trailing ``/`` for a
    directory) and where it came from (history entries render with a marker)."""
    path: str
    from_history: bool

    @property
    def is_dir(self) -> bool:
        return self.path.endswith("/")


def suggestions(query: str, entries: list[str],
                limit: int = 50) -> list[Candidate]:
    """The dialog's ranked rows for ``query``: history fuzzy matches first
    (personal and recency-aware), then filesystem segment completions, deduped,
    capped at ``limit``. An empty query shows recent history as-is."""
    rows: list[Candidate] = []
    seen: set[str] = set()
    hist = rank_history(query, entries) if query else (
        list(entries) + history_dirs(entries))
    for path in hist:
        if path not in seen:
            seen.add(path)
            rows.append(Candidate(path, from_history=True))
    for path in segment_complete(query):
        if path not in seen:
            seen.add(path)
            rows.append(Candidate(path, from_history=False))
    return rows[:limit]


def common_prefix(paths: list[str]) -> str:
    """Longest common prefix of ``paths`` (case-preserving from the first) —
    what Tab extends the typed text to."""
    if not paths:
        return ""
    first, rest = paths[0], paths[1:]
    lo = [p.lower() for p in rest]
    n = len(first)
    for p in lo:
        n = min(n, len(p))
    i = 0
    while i < n and all(p[i] == first.lower()[i] for p in lo):
        i += 1
    return first[:i] if rest else first
