"""Shared visual and behavioral constants for the textli editor."""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

# ── Typography ───────────────────────────────────────────────────
FONT_FAMILY = "JetBrainsMono Nerd Font"

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
ZEN_MD_FOCUS_CORE_LINES = 1.3
ZEN_MD_FOCUS_FALLOFF_LINES = 3.0
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

# ── Modifier helpers ─────────────────────────────────────────────
# Qt swaps Control/Meta on macOS: MetaModifier is the physical ⌃ key there.
_CTRL_MOD = (
    Qt.KeyboardModifier.MetaModifier
    if sys.platform == "darwin"
    else Qt.KeyboardModifier.ControlModifier
)
