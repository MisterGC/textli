"""Whisper status line content for the zen editor — pure text, no Qt.

The status line is a single faint line in the corner of the card: in the
write view it whispers the vim mode, the word count, and what this session
added; in the read view, how far through the piece the reader is, roughly
how much reading is left, and what still awaits review. All formatting
lives here, Qt-free, so it stays cheap to unit-test — the editor only
paints the string.
"""

from __future__ import annotations

import math
import re

from textli import comments

# A calm middle of the silent-reading estimates — the "time left" whisper
# only needs to be honest, not exact.
WORDS_PER_MINUTE = 220

_RE_WORDS = re.compile(r"\S+")

SEP = " · "


def word_count(source: str) -> int:
    """Words a reader would actually read: suggestions resolved as accepted,
    comment markup unwrapped (spans stay, bodies go)."""
    return len(_RE_WORDS.findall(comments.strip(comments.accepted(source))))


def write_status(mode: str, words: int, session_delta: int) -> str:
    """The write-view whisper: ``NORMAL · 1,234 words · +56``. The delta
    only appears once the session has changed the count."""
    parts = [mode, f"{words:,} words"]
    if session_delta:
        parts.append(f"{session_delta:+,}")
    return SEP.join(parts)


# Longest section name the whisper carries before eliding — a breadcrumb, not
# a headline; anything past this earns an ellipsis rather than pushing the
# progress and review counts off the card.
_SECTION_MAX = 48


def _crumb(text: str) -> str:
    """Elide a leading breadcrumb (section or link) to keep the whisper from
    crowding out the progress and review counts."""
    text = text.strip()
    if len(text) > _SECTION_MAX:
        text = text[:_SECTION_MAX - 1].rstrip() + "…"
    return text


def read_status(progress: float, words_total: int,
                changes: int = 0, comment_count: int = 0,
                section: str = "", link: str = "") -> str:
    """The read-view whisper: ``§ Design · 42% · ~7 min left · 2 comments``.
    ``progress`` is the fraction of the document the view has scrolled past
    (0..1); ``section`` is the heading under the caret (empty before the first
    heading). When the caret is on a link, ``link`` leads instead — ``→ where
    Enter goes`` — since that's the salient thing. Review parts appear only
    while there is something to review."""
    progress = min(1.0, max(0.0, progress))
    parts = [f"{round(progress * 100)}%"]
    minutes = math.ceil(words_total * (1.0 - progress) / WORDS_PER_MINUTE)
    if progress < 1.0 and minutes:
        parts.append(f"~{minutes} min left")
    if changes:
        parts.append(f"{changes} change{'s' if changes != 1 else ''}")
    if comment_count:
        parts.append(f"{comment_count} comment{'s' if comment_count != 1 else ''}")
    if link.strip():
        parts.insert(0, f"→ {_crumb(link)}")
    elif section.strip():
        parts.insert(0, f"§ {_crumb(section)}")
    return SEP.join(parts)
