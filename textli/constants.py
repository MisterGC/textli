"""Shared visual and behavioral constants for the textli editor."""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

# ── Typography ───────────────────────────────────────────────────
FONT_FAMILY = "JetBrainsMono Nerd Font"
# Reading face for the rendered read view (bundled Literata, OFL) — a warm,
# book-oriented serif so long-form prose reads like a typeset page rather than
# source code. Only the read view uses it; the write view keeps the monospace
# column, and code (fenced + inline) is pinned back to FONT_FAMILY.
READING_FONT_FAMILY = "Literata"
# Handwriting face for comment annotations (bundled Caveat, OFL) — a comment
# reads as a margin note, not a form field. The note wears the same tint a
# commented span gets in the text (ZEN_MD_COMMENT_NOTE_BG, below), inked in a
# dark warm red that sits on it. The small boost over body size keeps it
# proportional to the document (Caveat's x-height runs small).
COMMENT_FONT_FAMILY = "Caveat"
ZEN_MD_COMMENT_INK = QColor("#6E2A1C")
ZEN_MD_COMMENT_SIZE_BOOST = 4    # points added over the body size in the field
ZEN_MD_COMMENT_WIDTH = 360       # fixed width; text wraps within it
ZEN_MD_COMMENT_MIN_HEIGHT = 46   # starts small (about a line), then grows
ZEN_MD_COMMENT_MAX_HEIGHT = 200  # grows to here with content, then scrolls

# ── Zen palette ──────────────────────────────────────────────────
ZEN_TEXT_COLOR = QColor("#403A30")
ZEN_TITLE_COLOR = QColor("#004578")
ZEN_HINT_COLOR = QColor("#8A8580")

# ── Markdown editor ──────────────────────────────────────────────
ZEN_MD_MAX_WIDTH = 700          # default content-column width (user-adjustable)
ZEN_MD_MAX_WIDTH_MIN = 360      # narrowest the column can step to
ZEN_MD_MAX_WIDTH_MAX = 1400     # widest (further clamped to the window)
ZEN_MD_WIDTH_STEP = 80          # per-keystroke width increment
ZEN_MD_BG = QColor("#EEE5D0")
ZEN_MD_HEADING_SIZES = {1: 22, 2: 18, 3: 15}
ZEN_MD_CODE_BG = QColor("#EDE9E3")
# Read-view code blocks: a full-width band in a deeper paper shade — enough
# step-down from the page (#EEE5D0) to read as "code lives here" while
# staying warm — plus a calm token scheme drawn from the palette above:
# everything not listed stays body ink.
ZEN_MD_CODE_BLOCK_BG = QColor("#E5DAC0")
ZEN_MD_CODE_PAD_H = 14          # in-band breathing room left/right of the code
ZEN_CODE_KEYWORD = QColor("#004578")     # the zen blue (titles, links)
ZEN_CODE_STRING = QColor("#A83E2E")      # the warm suggestion red
ZEN_CODE_COMMENT = QColor("#8A8580")     # hint gray (rendered italic)
ZEN_CODE_NUMBER = QColor("#C9A227")      # the overlay-card amber
ZEN_MD_LINK_COLOR = QColor("#004578")
# Read-view caret: a soft block over the current glyph (vim-style), cool blue
# on the warm page so it reads at a glance without pulling all attention; the
# letter stays visible through it. Replaces Qt's near-invisible 1px line.
ZEN_MD_CARET = QColor(0, 69, 120, 72)
# Read-view focus reading mode (`f`): a spotlight centred on the caret line
# (not the paragraph — so brightness never snaps at block boundaries). A
# fully-bright band of CORE_LINES half-height each side of the caret, then a
# paper wash ramping to DIM_MAX over FALLOFF_LINES more line-heights. The
# caret is locked at centre, so this reads as a stable vignette the text
# flows through as it scrolls.
ZEN_MD_FOCUS_DIM_MAX = 212
ZEN_MD_FOCUS_CORE_LINES = 12.0
ZEN_MD_FOCUS_FALLOFF_LINES = 3.5
# Read-view tables: a header row in the code-band paper shade, thin gridlines
# in a warm gray that reads on the page without drawing the eye.
ZEN_MD_TABLE_HEADER_BG = QColor("#E5DAC0")
ZEN_MD_TABLE_BORDER = QColor("#C7B99B")
ZEN_MD_TABLE_PAD = 6            # cell breathing room (px)
ZEN_MD_MUTED_ALPHA = 100
ZEN_MD_SYNTAX_COLOR = QColor("#B8B3AB")
ZEN_MD_FONT_SIZE = 16
ZEN_MD_FONT_SIZE_MIN = 10
ZEN_MD_FONT_SIZE_MAX = 32
# Read-view long-form leading — proportional line height (%) applied to prose
# (not code, which reads better tight), paired with the proportional reading
# face so sustained reading breathes.
ZEN_MD_READING_LINE_HEIGHT = 145
# Modal card: width hugs the text column, height takes most of the window.
# Card chrome strips (the area outside the canvas) get the dim wash so a
# host's canvas itself stays fully saturated.
ZEN_MD_CARD_INNER_PAD_H = 64
ZEN_MD_CARD_INNER_PAD_V = 40
ZEN_MD_CARD_H_RATIO = 0.85
ZEN_MD_CARD_RADIUS = 12
ZEN_MD_DIM_COLOR = QColor(0, 0, 0, 115)         # chrome — full wash
ZEN_MD_CANVAS_DIM_COLOR = QColor(0, 0, 0, 165)  # canvas — strong step-back
# Light, muted-red marker behind a commented span in the rendered read view —
# translucent so it composites over the warm paper as a soft highlighter wash
# that accompanies the zen style without shouting.
ZEN_MD_COMMENT_HL = QColor(199, 92, 78, 72)


def _flatten(fg: QColor, bg: QColor) -> QColor:
    """Composite translucent ``fg`` over opaque ``bg`` → an opaque color."""
    a = fg.alphaF()
    return QColor(
        round(bg.red() * (1 - a) + fg.red() * a),
        round(bg.green() * (1 - a) + fg.green() * a),
        round(bg.blue() * (1 - a) + fg.blue() * a),
    )


# The comment note editor wears the exact tint a commented span gets in the
# text — the highlight wash flattened over the page — so the note you write
# and the mark it leaves read as one thing.
ZEN_MD_COMMENT_NOTE_BG = _flatten(ZEN_MD_COMMENT_HL, ZEN_MD_BG)

# Suggestion (track-changes) styling in the rendered read view. Removed text is
# struck through with a strong (bold-weight) line so it's unmistakable, while
# keeping the body ink; added text stays in the body font but in a subtle zen
# red — warm and calm, yet high-contrast enough to read comfortably, the same for
# an inline edit or a whole block rewrite.
ZEN_MD_SUGGEST_ADD = QColor("#A83E2E")

# In-document search (`/`): hit highlights via ExtraSelections — never
# document mutations. Amber, matching the overlay cards' accent, so hits read
# as navigation aids and don't collide with the comment wash.
ZEN_SEARCH_HIT = QColor(201, 162, 39, 60)        # every hit — soft wash
ZEN_SEARCH_CURRENT = QColor(201, 162, 39, 135)   # the current hit — stronger

# Read-view source pages (#37): a followed `path:line` reference opens the
# file as one code band, and the referenced lines lift back out of it onto the
# bright page — the anchor marked by *removing* shade rather than adding a
# color, so nothing new enters the palette and the page stays calm.
ZEN_MD_SRC_ANCHOR_BG = ZEN_MD_BG
# Code is a denser medium than prose, and it needs a different page. Two
# adjustments, both only while a source page is up:
#   * the size steps down to what an editor would use (16 → 13) — the reading
#     size is chosen for a proportional face and leaves code enormous;
#   * the column grows to fit SRC_COLUMNS of it. The prose measure (700px)
#     holds ~50 characters of mono at the reading size and ~60 at the code
#     size, while source is written for ~80: without the wider sheet, wrapping
#     would be the rule instead of the exception it should be. The card snaps
#     back the moment `gb` returns to the document.
# ⌘+/⌘- still ride on top of both, and a column already wider than this keeps
# its width.
ZEN_MD_SRC_FONT_SCALE = 0.82
ZEN_MD_SRC_COLUMNS = 88

# ── Paper surface (grain + light) ────────────────────────────────
# The page is material, not a flat hex: paper.py paints whisper-level grain
# and a horizontal light falloff under the text of both views — tuned to sit
# below conscious notice (texture felt, not seen). ⌘⇧P toggles the surface
# off for the flat page.
ZEN_MD_PAPER_GRAIN = 3         # max ± luminance step of the grain (of 255)
ZEN_MD_PAPER_TILE = 144        # grain tile side (logical px)
ZEN_MD_PAPER_SEED = 0x7311     # fixed — the sheet looks the same every launch
ZEN_MD_PAPER_EDGE_ALPHA = 16   # falloff ink alpha at the window edges
ZEN_MD_PAPER_PLATEAU = 0.5     # central width fraction kept fully bright

# ── Modifier helpers ─────────────────────────────────────────────
# Qt swaps Control/Meta on macOS: MetaModifier is the physical ⌃ key there.
_CTRL_MOD = (
    Qt.KeyboardModifier.MetaModifier
    if sys.platform == "darwin"
    else Qt.KeyboardModifier.ControlModifier
)
