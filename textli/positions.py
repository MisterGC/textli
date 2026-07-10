"""Per-file position memory for the zen editor — pure record logic, no Qt.

Each entry remembers where a file was left: the view mode (``read`` /
``write``), the write-view caret offset, and the read-view top position
(a character offset into the rendered text). Entries are most-recent-first
and LRU-capped, like the open-file history; the editor persists the encoded
list via QSettings and this module never sees Qt.

The record is ``mode<TAB>caret<TAB>top<TAB>path`` — the path goes last so
the fixed fields survive any path a filesystem can throw at us.
"""

from __future__ import annotations

POSITIONS_MAX = 200

_SEP = "\t"


def encode(path: str, mode: str, caret: int, top: int) -> str:
    """One stored record for ``path``."""
    return f"{mode}{_SEP}{caret}{_SEP}{top}{_SEP}{path}"


def decode(entry: str) -> tuple[str, str, int, int] | None:
    """``(path, mode, caret, top)`` — or ``None`` for a record that doesn't
    parse (settings survive versions; a bad record is skipped, not fatal)."""
    parts = entry.split(_SEP, 3)
    if len(parts) != 4 or parts[0] not in ("read", "write"):
        return None
    mode, caret, top, path = parts
    try:
        return path, mode, int(caret), int(top)
    except ValueError:
        return None


def remember(entries: list[str], path: str, mode: str,
             caret: int, top: int) -> list[str]:
    """The entries with ``path``'s record set (moved to the front), capped at
    ``POSITIONS_MAX`` — the least recently touched files fall off the end."""
    kept = [e for e in entries
            if (d := decode(e)) is None or d[0] != path]
    return [encode(path, mode, caret, top)] + kept[:POSITIONS_MAX - 1]


def lookup(entries: list[str], path: str) -> tuple[str, int, int] | None:
    """``(mode, caret, top)`` stored for ``path``, or ``None``."""
    for e in entries:
        d = decode(e)
        if d is not None and d[0] == path:
            return d[1], d[2], d[3]
    return None
