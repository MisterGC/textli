"""Callout markers — ``> [!NOTE]`` and friends — over a plain string.

GitHub and Obsidian both spell an admonition as a blockquote whose first line
carries a ``[!KIND]`` marker. Qt's Markdown reader knows nothing of the
convention: the marker survives as literal text at the head of the quote, and
the box reads as an undifferentiated aside (#35).

Qt-free on purpose, like :mod:`textli.links` and :mod:`textli.srcref` — what
counts as a marker and where it ends is plain string work, so it is unit-tested
without a widget. :mod:`textli.editor` keeps the half that turns an answer into
a label block and a tint.

Deliberately narrow, in three ways:

* only the five kinds GitHub defines are recognised. An unknown ``[!X]`` is
  left exactly as it was and renders as the plain blockquote it already is, so
  a document that writes ``[!TODO]`` on purpose is never silently restyled;
* the marker only counts at the very start of the quote's first line, which is
  where both conventions put it — ``[!NOTE]`` mid-sentence stays prose;
* the kind matches case-insensitively (both conventions accept ``[!note]``),
  but :attr:`Callout.kind` is always the canonical upper-case word, so the page
  reads the same however the source was typed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

#: The recognised kinds, canonical spelling. Order is GitHub's, escalating.
KINDS = ("NOTE", "TIP", "IMPORTANT", "WARNING", "CAUTION")

# The trailing run of blanks belongs to the marker: Qt folds a callout's
# ``> [!NOTE]\n> body`` into one paragraph, so the space that used to be a line
# break sits between the marker and the body and would otherwise open the
# body's own text.
_MARKER_RE = re.compile(r"\[!([A-Za-z]+)\][ \t]*")


@dataclass(frozen=True)
class Callout:
    """A recognised marker at the head of a blockquote's first line."""

    kind: str
    """Canonical upper-case kind, one of :data:`KINDS`."""

    end: int
    """Offset just past the marker and the blanks after it — the caller
    replaces ``line[:end]`` with the label."""


def match(text: str) -> Callout | None:
    """The callout ``text`` opens with, or None when it opens with none.

    ``text`` is the blockquote's first line with the quote markers already
    stripped — for the read view, the first rendered block's text.
    """
    m = _MARKER_RE.match(text)
    if m is None:
        return None
    kind = m.group(1).upper()
    if kind not in KINDS:
        return None
    return Callout(kind=kind, end=m.end())
