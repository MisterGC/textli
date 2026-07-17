"""Inline TeX math for the markdown editor — pandoc-style ``$…$`` / ``$$…$$``.

Math lives in the source exactly as pandoc reads it, so a draft written here
converts to LaTeX/PDF untouched::

    The relation $E = mc^2$ holds, and in general

    $$\\int_0^\\infty e^{-x^2}\\,dx = \\frac{\\sqrt{\\pi}}{2}$$

``$…$`` is inline math, ``$$…$$`` display math. The delimiter rules are
pandoc's, deliberately strict so prose dollars never turn into formulas: the
opening ``$`` must be followed by a non-space, the closing ``$`` preceded by
one and not followed by a digit ("costs $5 and $10" stays prose), and ``\\$``
escapes a literal dollar. ``$`` inside code spans or fenced blocks is always
code (via :func:`comments.code_ranges`).

This module only *finds and rebuilds* — turning a formula into pixels is the
editor's business (`mathrender.py`). Pure text logic, no Qt, same design line
as `comments.py`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .comments import SENTINEL_END, SENTINEL_START, code_ranges


@dataclass(frozen=True)
class Formula:
    """One math span, with offsets into the string it was parsed from."""

    start: int      # offset of the opening delimiter
    end: int        # offset just past the closing delimiter
    tex: str        # the TeX between the delimiters
    display: bool   # True for $$…$$ (display), False for $…$ (inline)


# The sentinel code points never belong to a formula: a span crossing one
# would straddle a comment-highlight boundary in the rendered markdown.
_NOT_IN_MATH = f"{SENTINEL_START}{SENTINEL_END}"

# $$…$$ display math. Content is tempered (no ``$$`` inside) and may wrap
# lines but not cross a blank line — that's a paragraph break, not a formula.
_RE_DISPLAY = re.compile(
    rf"(?<![\\$])\$\$"
    rf"(?P<tex>(?:(?!\$\$|\n[ \t]*\n)[^{_NOT_IN_MATH}])+?)"
    rf"\$\$(?!\$)"
)

# $…$ inline math, single line. Opening ``$`` not escaped, not part of ``$$``,
# followed by non-space; closing ``$`` preceded by a non-space non-backslash,
# not followed by a digit.
_RE_INLINE = re.compile(
    rf"(?<![\\$])\$(?![\s$])"
    rf"(?P<tex>(?:(?!\$)[^\n{_NOT_IN_MATH}])*?[^\s\\])"
    rf"\$(?![\d$])"
)


def parse(source: str) -> list[Formula]:
    """Every math span in ``source``, in document order. ``$`` inside code
    regions stays literal; display spans win over inline ones on overlap (a
    lone ``$`` inside ``$$…$$`` content can't spawn a phantom inline span)."""
    ranges = code_ranges(source)

    def in_code(pos: int) -> bool:
        return any(a <= pos < b for a, b in ranges)

    out: list[Formula] = []
    display: list[tuple[int, int]] = []
    for m in _RE_DISPLAY.finditer(source):
        if in_code(m.start()) or in_code(m.end() - 1):
            continue
        if not m.group("tex").strip():
            continue
        out.append(Formula(m.start(), m.end(), m.group("tex").strip(), True))
        display.append((m.start(), m.end()))
    for m in _RE_INLINE.finditer(source):
        if in_code(m.start()) or in_code(m.end() - 1):
            continue
        if any(not (m.end() <= a or m.start() >= b) for a, b in display):
            continue
        out.append(Formula(m.start(), m.end(), m.group("tex"), False))
    out.sort(key=lambda f: f.start)
    return out


def spans_in_line(line: str) -> list[tuple[int, int, bool]]:
    """Math spans in one line of text, as ``(start, end, display)`` — the
    write-view highlighter's per-line view. No cross-line context: fenced
    code and multi-line ``$$`` blocks are out of its scope (the read view
    still renders those; the highlighter is a hint, not a parser)."""
    out: list[tuple[int, int, bool]] = []
    display: list[tuple[int, int]] = []
    for m in _RE_DISPLAY.finditer(line):
        if m.group("tex").strip():
            out.append((m.start(), m.end(), True))
            display.append((m.start(), m.end()))
    for m in _RE_INLINE.finditer(line):
        if any(not (m.end() <= a or m.start() >= b) for a, b in display):
            continue
        out.append((m.start(), m.end(), False))
    out.sort()
    return out


def substitute(source: str, formulas: list[Formula], replacement) -> str:
    """Rebuild ``source`` with each formula replaced by ``replacement(i, f)``
    and everything else untouched. ``formulas`` must be :func:`parse` output
    for this same ``source`` (document order, non-overlapping)."""
    out: list[str] = []
    pos = 0
    for i, f in enumerate(formulas):
        out.append(source[pos:f.start])
        out.append(replacement(i, f))
        pos = f.end
    out.append(source[pos:])
    return "".join(out)


def code_span(text: str) -> str:
    """``text`` wrapped as a markdown code span whose backtick run is longer
    than any run inside — the styled-raw-TeX form for a formula the renderer
    couldn't parse. Only valid for single-line ``text``."""
    longest = max((len(m.group()) for m in re.finditer(r"`+", text)), default=0)
    run = "`" * (longest + 1)
    pad = " " if text.startswith("`") or text.endswith("`") else ""
    return f"{run}{pad}{text}{pad}{run}"
