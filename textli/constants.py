"""Shared layout, typography and behavioral constants for the textli editor.

Colours live in :mod:`textli.theme`, which swaps them at runtime — everything
here is theme-independent: sizes, fonts, alphas and the platform modifier.
"""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt

# ── Typography ───────────────────────────────────────────────────
FONT_FAMILY = "JetBrainsMono Nerd Font"
# Reading face for the rendered read view (bundled Literata, OFL) — a warm,
# book-oriented serif so long-form prose reads like a typeset page rather than
# source code. Only the read view uses it; the write view keeps the monospace
# column, and code (fenced + inline) is pinned back to FONT_FAMILY.
READING_FONT_FAMILY = "Literata"
# Handwriting face for comment annotations (bundled Caveat, OFL) — a comment
# reads as a margin note, not a form field. The note wears the same tint a
# commented span gets in the text (theme.ZEN_MD_COMMENT_NOTE_BG), inked in a
# dark warm red that sits on it. The small boost over body size keeps it
# proportional to the document (Caveat's x-height runs small).
COMMENT_FONT_FAMILY = "Caveat"
ZEN_MD_COMMENT_SIZE_BOOST = 4    # points added over the body size in the field
ZEN_MD_COMMENT_WIDTH = 360       # fixed width; text wraps within it
ZEN_MD_COMMENT_MIN_HEIGHT = 46   # starts small (about a line), then grows
ZEN_MD_COMMENT_MAX_HEIGHT = 200  # grows to here with content, then scrolls

# ── Markdown editor ──────────────────────────────────────────────
ZEN_MD_MAX_WIDTH = 700          # default content-column width (user-adjustable)
ZEN_MD_MAX_WIDTH_MIN = 360      # narrowest the column can step to
ZEN_MD_MAX_WIDTH_MAX = 1400     # widest (further clamped to the window)
ZEN_MD_WIDTH_STEP = 80          # per-keystroke width increment
ZEN_MD_HEADING_SIZES = {1: 22, 2: 18, 3: 15}
ZEN_MD_CODE_PAD_H = 14          # in-band breathing room left/right of the code
# Read-view focus reading mode (`f`): a spotlight centred on the caret line
# (not the paragraph — so brightness never snaps at block boundaries). A
# fully-bright band of CORE_LINES half-height each side of the caret, then a
# paper wash ramping to DIM_MAX over FALLOFF_LINES more line-heights. The
# caret is locked at centre, so this reads as a stable vignette the text
# flows through as it scrolls.
ZEN_MD_FOCUS_DIM_MAX = 212
ZEN_MD_FOCUS_CORE_LINES = 12.0
ZEN_MD_FOCUS_FALLOFF_LINES = 3.5
ZEN_MD_TABLE_PAD = 6            # cell breathing room (px)
ZEN_MD_MUTED_ALPHA = 100
ZEN_MD_FONT_SIZE = 16
ZEN_MD_FONT_SIZE_MIN = 10
ZEN_MD_FONT_SIZE_MAX = 32
# Read-view long-form rhythm (#33, #54) — all three are multiples of the body
# em, resolved to pixels against the view's own font metrics so the numbers
# mean the same thing at every zoom, on every platform, and under a different
# reading face.
#
# The leading is applied as an *absolute* line height. Qt's ProportionalHeight
# is a percentage of the font's natural line box, not of the em — Literata's
# box is 1.485em, so the 145 this replaces landed near 2.2em, far past the
# ~1.4-1.6em at which consecutive lines still read as one block. It also
# scaled each line by the tallest fragment on it, so a line carrying inline
# code (mono, 1.32em) came out shorter than a plain one and the leading
# wobbled inside a single paragraph.
#
# Both gaps sit above the line gap, so a break *between* blocks always reads
# larger than a break *inside* one. List items get the smaller of the two:
# they had no gap at all, which left a wrapped bullet's continuation line
# indistinguishable from the start of the next bullet.
ZEN_MD_READING_LEADING = 1.55    # × body em — the line box
ZEN_MD_READING_PARA_GAP = 0.9    # × body em — after a plain paragraph
ZEN_MD_READING_ITEM_GAP = 0.6    # × body em — after a list item
# Modal card: width hugs the text column, height takes most of the window.
# Card chrome strips (the area outside the canvas) get the dim wash so a
# host's canvas itself stays fully saturated.
ZEN_MD_CARD_INNER_PAD_H = 64
ZEN_MD_CARD_INNER_PAD_V = 40
ZEN_MD_CARD_H_RATIO = 0.85
ZEN_MD_CARD_RADIUS = 12

# Read-view source pages (#37): code is a denser medium than prose, and it
# needs a different page. Two adjustments, both only while a source page is up:
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
