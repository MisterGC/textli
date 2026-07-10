"""Locating the Markdown link under a caret column — pure text logic, no Qt.

The write view's Enter-to-follow needs to answer one question: given the
source line and the caret's column, which link (if any) covers that column,
and what is its target? Three source shapes count as a link, checked in this
order so an inline link wins over the bare URL inside its own parentheses:

- inline links ``[text](target)`` (optional ``"title"``) — the whole span,
  label and target alike, is followable
- autolinks ``<https://…>``
- bare URLs ``https://…`` / ``mailto:…`` (trailing sentence punctuation is
  not part of the target)
"""

from __future__ import annotations

import re

_RE_INLINE_LINK = re.compile(
    r"\[[^\]]*\]\(\s*([^)\s]+)(?:\s+\"[^\"]*\")?\s*\)"
)
_RE_AUTOLINK = re.compile(r"<((?:https?://|mailto:)[^ >]+)>")
_RE_BARE_URL = re.compile(r"(?:https?://|mailto:)[^\s<>()\[\]]+")


def link_at(line: str, col: int) -> str | None:
    """Return the target of the link whose source span covers ``col`` in
    ``line``, or None if the caret isn't on one."""
    for m in _RE_INLINE_LINK.finditer(line):
        if m.start() <= col < m.end():
            return m.group(1)
    for m in _RE_AUTOLINK.finditer(line):
        if m.start() <= col < m.end():
            return m.group(1)
    for m in _RE_BARE_URL.finditer(line):
        if m.start() <= col < m.end():
            return m.group(0).rstrip(".,;:!?")
    return None
