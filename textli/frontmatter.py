"""What a document declares about itself in its YAML frontmatter — pure text,
no Qt.

Only one thing is read here so far: the document's **status**. A document opts
in by listing its own legal values under ``statuses:``; one without that line
has no state to show and nothing for ``gs`` to change. The current value lives
in ``status:``.

    ---
    status: draft
    statuses: draft, review, final
    ---

The fence is parsed exactly the way Qt's Markdown reader parses it — a line
that is exactly ``---`` at the very top of the file, closed by another line
that is exactly ``---`` — so the whisper never claims a state for text the
reading view renders as raw prose.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

FENCE = "---"

# The frontmatter keys this module reads. `statuses` is the opt-in: without it
# a document has no declared state, and textli leaves it alone.
STATUS_KEY = "status"
VALUES_KEY = "statuses"

_RE_LINE_END = re.compile(r"\r?\n")
# A top-level `key: value` line — no indentation, so a key nested under another
# mapping is not mistaken for the document's own.
_RE_KEY = re.compile(r"^([A-Za-z0-9_-]+)[ \t]*:[ \t]*(.*)$")
# One entry of a YAML block sequence (`  - draft`).
_RE_ITEM = re.compile(r"^[ \t]+-[ \t]*(.*)$")
# A value that has to be quoted to survive a round trip through YAML.
_RE_NEEDS_QUOTES = re.compile(r"[:#\[\]{},&*!|>'\"%@`]|^\s|\s$|^$")


@dataclass(frozen=True)
class Status:
    """A document's declared status. ``values`` is what the document lists, in
    the order it lists them; ``current`` is what ``status:`` says — the empty
    string when the document declares values but sets none. ``current`` may sit
    outside ``values`` (a document is free to carry a state it no longer lists);
    reporting it is more honest than hiding it."""

    current: str
    values: tuple[str, ...]

    @property
    def index(self) -> int:
        """Where a picker should open: on the current value, or on the first
        declared one when the current value is unset or no longer listed."""
        try:
            return self.values.index(self.current)
        except ValueError:
            return 0


def body_span(source: str) -> tuple[int, int] | None:
    """``(start, end)`` character offsets of the frontmatter body — everything
    between the opening and closing fences, closing newline excluded. ``None``
    when the document has no frontmatter Qt would recognise."""
    if not source.startswith(FENCE):
        return None
    rest = source[len(FENCE):]
    if not (rest.startswith("\n") or rest.startswith("\r\n")):
        return None
    start = len(source) - len(rest) + (2 if rest.startswith("\r\n") else 1)
    pos = start
    while pos <= len(source):
        m = _RE_LINE_END.search(source, pos)
        line_end = m.start() if m else len(source)
        if source[pos:line_end] == FENCE:
            return (start, pos)
        if m is None:
            return None          # ran off the end with no closing fence
        pos = m.end()
    return None


def _lines(body: str) -> list[str]:
    return _RE_LINE_END.split(body)


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def _split_inline(value: str) -> list[str]:
    """``draft, review`` or ``[draft, review]`` → the entries, in order."""
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        value = value[1:-1]
    return [_unquote(part) for part in value.split(",")]


def _read_values(lines: list[str], idx: int) -> list[str]:
    """The values declared by the ``statuses:`` line at ``lines[idx]``: inline
    (``a, b``), flow (``[a, b]``), or the block sequence that follows it."""
    inline = _RE_KEY.match(lines[idx]).group(2)
    raw = _split_inline(inline) if inline.strip() else [
        _unquote(m.group(1))
        for line in _take_items(lines, idx + 1)
        if (m := _RE_ITEM.match(line))
    ]
    out: list[str] = []
    for value in raw:
        if value and value not in out:
            out.append(value)
    return out


def _take_items(lines: list[str], idx: int) -> list[str]:
    """The block-sequence lines starting at ``idx`` — indented ``-`` entries,
    stopping at the first line that is anything else."""
    out = []
    for line in lines[idx:]:
        if not line.strip():
            continue
        if not _RE_ITEM.match(line):
            break
        out.append(line)
    return out


def status(source: str) -> Status | None:
    """The document's declared status, or ``None`` when it declares none — no
    frontmatter, no ``statuses:`` line, or an empty list."""
    span = body_span(source)
    if span is None:
        return None
    lines = _lines(source[span[0]:span[1]])
    current, values = "", []
    for i, line in enumerate(lines):
        m = _RE_KEY.match(line)
        if m is None:
            continue
        if m.group(1) == STATUS_KEY and not current:
            current = _unquote(m.group(2))
        elif m.group(1) == VALUES_KEY and not values:
            values = _read_values(lines, i)
    if not values:
        return None
    return Status(current, tuple(values))


def _quote(value: str) -> str:
    """``value`` as a YAML scalar — quoted only when it would otherwise parse
    as something else."""
    if _RE_NEEDS_QUOTES.search(value):
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return value


def with_status(source: str, value: str) -> str:
    """``source`` with its frontmatter ``status:`` set to ``value``, everything
    else untouched. The line is rewritten in place if it exists, else added
    just above ``statuses:`` so the pair reads together. Returns ``source``
    unchanged for a document with no frontmatter."""
    span = body_span(source)
    if span is None:
        return source
    start, end = span
    body = source[start:end]
    nl = "\r\n" if "\r\n" in source[:end] else "\n"
    lines = _lines(body)
    line = f"{STATUS_KEY}: {_quote(value)}"
    for i, text in enumerate(lines):
        m = _RE_KEY.match(text)
        if m is not None and m.group(1) == STATUS_KEY:
            lines[i] = line
            break
    else:
        at = next((i for i, text in enumerate(lines)
                   if (m := _RE_KEY.match(text)) and m.group(1) == VALUES_KEY),
                  len(lines))
        lines.insert(at, line)
    return source[:start] + nl.join(lines) + source[end:]
