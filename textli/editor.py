"""Zen markdown editor — a full-window, distraction-free editing experience."""

from __future__ import annotations

import os
import re
from collections import namedtuple
from pathlib import Path

from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QEventLoop,
    QFileSystemWatcher,
    QPoint,
    QPointF,
    QPropertyAnimation,
    QRect,
    QRectF,
    Qt,
    QUrl,
    Signal,
    QTimer,
)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QDesktopServices,
    QFont,
    QFontMetricsF,
    QGradient,
    QKeyEvent,
    QLinearGradient,
    QPainter,
    QPen,
    QTextBlockFormat,
    QTextCharFormat,
    QTextCursor,
    QTextDocument,
    QTextFormat,
    QTextFrameFormat,
    QTextLength,
    QTextTable,
    QTextTableFormat,
)
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QGraphicsOpacityEffect,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from textli import codeblocks as md_codeblocks
from textli import comments as md_comments
from textli import links as md_links
from textli import openfile
from textli import positions as md_positions
from textli import search as md_search
from textli import settings as md_settings
from textli import status as md_status
from textli.open_overlay import OpenFileOverlay
from textli.search_overlay import SearchOverlay
from textli.constants import (
    COMMENT_FONT_FAMILY,
    FONT_FAMILY,
    READING_FONT_FAMILY,
    ZEN_MD_COMMENT_INK,
    ZEN_MD_COMMENT_MAX_HEIGHT,
    ZEN_MD_COMMENT_MIN_HEIGHT,
    ZEN_MD_COMMENT_NOTE_BG,
    ZEN_MD_COMMENT_SIZE_BOOST,
    ZEN_MD_COMMENT_WIDTH,
    ZEN_CODE_COMMENT,
    ZEN_CODE_KEYWORD,
    ZEN_CODE_NUMBER,
    ZEN_CODE_STRING,
    ZEN_HINT_COLOR,
    ZEN_MD_BG,
    ZEN_MD_CODE_BLOCK_BG,
    ZEN_MD_CODE_PAD_H,
    ZEN_MD_CANVAS_DIM_COLOR,
    ZEN_MD_COMMENT_HL,
    ZEN_MD_SUGGEST_ADD,
    ZEN_MD_CARD_H_RATIO,
    ZEN_MD_CARD_INNER_PAD_H,
    ZEN_MD_CARD_INNER_PAD_V,
    ZEN_MD_CARD_RADIUS,
    ZEN_MD_DIM_COLOR,
    ZEN_MD_FONT_SIZE,
    ZEN_MD_FONT_SIZE_MAX,
    ZEN_MD_FONT_SIZE_MIN,
    ZEN_MD_HEADING_SIZES,
    ZEN_MD_READING_LINE_HEIGHT,
    ZEN_MD_SYNTAX_COLOR,
    ZEN_MD_CARET,
    ZEN_MD_FOCUS_CORE_LINES,
    ZEN_MD_FOCUS_DIM_MAX,
    ZEN_MD_FOCUS_FALLOFF_LINES,
    ZEN_MD_LINK_COLOR,
    ZEN_MD_TABLE_BORDER,
    ZEN_MD_TABLE_HEADER_BG,
    ZEN_MD_TABLE_PAD,
    ZEN_MD_MAX_WIDTH,
    ZEN_MD_MAX_WIDTH_MAX,
    ZEN_MD_MAX_WIDTH_MIN,
    ZEN_MD_WIDTH_STEP,
    ZEN_SEARCH_CURRENT,
    ZEN_SEARCH_HIT,
    ZEN_TEXT_COLOR,
    _CTRL_MOD,
)
from textli.fonts import register_bundled_fonts
from textli.highlight import MarkdownHighlighter, compute_focus_range
from textli.jump import WordJumpOverlay
from textli.suggest import SuggestionAnimator
from textli.vim import VimKeyHandler, VimMode

# Custom char-format property tagging a rendered span with its comment index,
# so the reveal/navigate loop can map a highlighted span back to its source
# comment even when inline formatting splits the span into fragments.
_COMMENT_IDX_PROP = QTextFormat.Property.UserProperty + 7
# Same idea for a suggestion: both spans of a substitution carry the same index,
# so its rendered range (struck-old through red-new) recovers as one unit.
_SUGGEST_IDX_PROP = QTextFormat.Property.UserProperty + 8
# Role of a suggestion fragment (0 = removed/struck, 1 = added), so the animator
# can fade the part that leaves and settle the part that stays.
_SUGGEST_ROLE_PROP = QTextFormat.Property.UserProperty + 9
_ROLE_REMOVED, _ROLE_ADDED = 0, 1

# A rendered suggestion: its overall [start, end) range, the source ``Mark``, and
# the rendered sub-ranges of its removed (struck) and added text — either may be
# None (an insertion has no removed; a deletion no added).
RSuggestion = namedtuple("RSuggestion", "start end mark removed added")

# Markdown feature set for the read view: GitHub dialect (tables, task lists)
# but with raw HTML off — a bare tag-looking token (`<variant>`) would
# otherwise open an HTML element that never closes and silently swallow every
# following paragraph. With NoHTML it renders as the literal text that was
# typed; CriticMarkup, not HTML, is textli's markup story.
_MD_FEATURES = (
    QTextDocument.MarkdownFeature.MarkdownDialectGitHub
    | QTextDocument.MarkdownFeature.MarkdownNoHTML
)


class _ReadingView(QTextBrowser):
    """The rendered read view. Paints a *thick* strike line over removed-text
    ranges itself — Qt derives the built-in strikeout's thickness from the font
    metrics (too thin, and it would only get heavier by bolding the glyphs), so a
    strong, calm line is drawn on top of regular-weight text instead. Each strike
    carries its own alpha so the accept/reject animation can fade it."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._strikes: list[list] = []          # [start, end, alpha]
        self._strike_color = QColor(ZEN_TEXT_COLOR)
        # Block positions of h1/h2 headings — each gets a thin muted rule
        # painted under it (GitHub-style; block formats have no borders).
        self._heading_rules: list[int] = []
        self._rule_color = QColor(ZEN_MD_SYNTAX_COLOR)
        self._rule_color.setAlpha(150)
        # Code bands, one (first_block_pos, last_block_pos) per fence run.
        # Painted here rather than via block backgrounds: Qt shifts a
        # block's background along with its margins, so an in-band text
        # inset is impossible that way — the view paints the band across
        # the full column and the margins inset only the code.
        self._code_bands: list[tuple[int, int]] = []
        # Blockquote bars, same (first_pos, last_pos) shape per quote run.
        self._quote_bars: list[tuple[int, int]] = []
        self._quote_bar_color = QColor(ZEN_MD_SYNTAX_COLOR)
        self._quote_bar_color.setAlpha(180)
        # Section focus: everything outside (start_pos, end_pos) is dimmed
        # under a translucent paper wash — nothing in the document mutates,
        # so comments, search hits and marks stay intact beneath it.
        self._focus_span: tuple[int, int] | None = None
        self._focus_wash = QColor(ZEN_MD_BG)
        self._focus_wash.setAlpha(175)
        # Focus reading mode (`f`): a spotlight centred on the caret line — a
        # bright band fading to a paper wash by distance, so brightness never
        # snaps at paragraph boundaries. Distinct from the section wash above;
        # only one is ever on.
        self._focus_reading = False
        self._focus_dim = QColor(ZEN_MD_BG)
        self._focus_dim.setAlpha(ZEN_MD_FOCUS_DIM_MAX)
        # Caret: hide Qt's near-invisible 1px line and paint a soft block over
        # the current glyph instead (vim-style), so it's findable on the warm
        # page while placing comments. Repaint as it moves or focus shifts.
        self.setCursorWidth(0)
        self._caret_color = QColor(ZEN_MD_CARET)
        self.cursorPositionChanged.connect(self.viewport().update)
        self.selectionChanged.connect(self.viewport().update)

    def set_heading_rules(self, positions: list[int]):
        """Replace the set of block positions to underline; repaint."""
        self._heading_rules = list(positions)
        self.viewport().update()

    def set_code_bands(self, bands: list[tuple[int, int]]):
        """Replace the set of code-band block ranges; repaint."""
        self._code_bands = list(bands)
        self.viewport().update()

    def set_quote_bars(self, bars: list[tuple[int, int]]):
        """Replace the set of blockquote bar ranges; repaint."""
        self._quote_bars = list(bars)
        self.viewport().update()

    def set_focus_span(self, span: tuple[int, int] | None):
        """Dim everything outside ``span`` (doc positions); None lifts it."""
        if span != self._focus_span:
            self._focus_span = span
            self.viewport().update()

    def set_focus_reading(self, on: bool):
        """Focus reading mode on/off — a caret-centred spotlight vignette."""
        if on != self._focus_reading:
            self._focus_reading = on
            self.viewport().update()

    def set_strikes(self, ranges):
        """Replace the strike set with ``ranges`` (each a rendered ``(start, end)``
        removed sub-range), all fully opaque; repaint."""
        self._strikes = [[s, e, 1.0] for (s, e) in ranges]
        self.viewport().update()

    def set_strike_alpha(self, rng, frac: float):
        """Fade the strike over ``rng`` (a ``(start, end)`` tuple) to ``frac`` of
        its ink — used by the animation as a removal leaves / un-strikes."""
        for st in self._strikes:
            if st[0] == rng[0] and st[1] == rng[1]:
                st[2] = max(0.0, min(1.0, frac))
        self.viewport().update()

    def _strike_width(self) -> float:
        """Line thickness scaled to the current font — strong but not heavy."""
        return max(2.0, self.font().pointSizeF() * 0.16)

    def _paint_code_bands(self, doc, layout, off):
        """The deeper-paper band behind each fence run, spanning the full
        text column. Painted *before* the text so glyphs sit on top."""
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(ZEN_MD_CODE_BLOCK_BG)
        margin = doc.documentMargin()
        x1 = margin + off.x()
        x2 = self.viewport().width() - margin + off.x()
        for first, last in self._code_bands:
            b0, b1 = doc.findBlock(first), doc.findBlock(last)
            if not (b0.isValid() and b1.isValid()):
                continue
            top = layout.blockBoundingRect(b0).top() + off.y()
            bottom = layout.blockBoundingRect(b1).bottom() + off.y()
            if bottom < 0 or top > self.viewport().height():
                continue
            painter.drawRoundedRect(QRectF(x1, top, x2 - x1, bottom - top),
                                    6.0, 6.0)
        painter.end()

    def paintEvent(self, event):
        doc = self.document()
        layout = doc.documentLayout()
        off = QPointF(-self.horizontalScrollBar().value(),
                      -self.verticalScrollBar().value())
        if self._code_bands:
            self._paint_code_bands(doc, layout, off)
        super().paintEvent(event)
        if (self._strikes or self._heading_rules or self._quote_bars
                or self._focus_span or self._focus_reading):
            self._paint_overlays(doc, layout, off)
        # The caret sits on top of every wash — it's always in the bright band,
        # but painting it last guarantees it's never dimmed.
        self._paint_caret(off)

    def _paint_overlays(self, doc, layout, off):
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._quote_bars:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(self._quote_bar_color)
            bar_x = doc.documentMargin() + 10 + off.x()
            for first, last in self._quote_bars:
                b0, b1 = doc.findBlock(first), doc.findBlock(last)
                if not (b0.isValid() and b1.isValid()):
                    continue
                top = layout.blockBoundingRect(b0).top() + off.y()
                bottom = layout.blockBoundingRect(b1).bottom() + off.y()
                painter.drawRoundedRect(
                    QRectF(bar_x, top + 2, 3.5, bottom - top - 4), 1.75, 1.75)
        if self._heading_rules:
            pen = QPen(self._rule_color)
            pen.setWidthF(1.2)
            painter.setPen(pen)
            for pos in self._heading_rules:
                block = doc.findBlock(pos)
                if not block.isValid():
                    continue
                r = layout.blockBoundingRect(block)
                # The bounding rect includes the block margins; sit the rule
                # just under the heading text, inside its bottom margin.
                y = r.bottom() - block.blockFormat().bottomMargin() + 4 + off.y()
                painter.drawLine(QPointF(r.left() + off.x(), y),
                                 QPointF(r.right() + off.x(), y))
        width = self._strike_width()
        for start, end, alpha in self._strikes:
            if alpha <= 0 or end <= start:
                continue
            color = QColor(self._strike_color)
            color.setAlphaF(color.alphaF() * alpha)
            pen = QPen(color)
            pen.setWidthF(width)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            self._paint_strike_range(painter, doc, layout, start, end, off)
        if self._focus_span is not None:
            # Painted last: the wash dims text, marks, bands and bars alike.
            start, end = self._focus_span
            b0, b1 = doc.findBlock(start), doc.findBlock(end)
            if b0.isValid() and b1.isValid():
                vp = self.viewport()
                top = layout.blockBoundingRect(b0).top() + off.y()
                bottom = layout.blockBoundingRect(b1).bottom() + off.y()
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(self._focus_wash)
                if top > 0:
                    painter.drawRect(QRectF(0, 0, vp.width(), top))
                if bottom < vp.height():
                    painter.drawRect(
                        QRectF(0, bottom, vp.width(), vp.height() - bottom))
        if self._focus_reading:
            self._paint_focus_reading(painter)
        painter.end()

    def _paint_focus_reading(self, painter):
        """Focus reading mode: a spotlight centred on the caret line. A bright
        band (``CORE_LINES`` half-height each side) fades to a paper wash over
        ``FALLOFF_LINES`` more line-heights, then holds. Because the fade keys
        off the caret's *position* — not paragraph edges — brightness slides
        smoothly as the text scrolls and never snaps between blocks."""
        vp = self.viewport()
        line_h = QFontMetricsF(self.font()).height()
        cy = self.cursorRect().center().y()
        core = line_h * ZEN_MD_FOCUS_CORE_LINES
        falloff = max(1.0, line_h * ZEN_MD_FOCUS_FALLOFF_LINES)
        clear = QColor(self._focus_dim)
        clear.setAlpha(0)
        painter.setPen(Qt.PenStyle.NoPen)
        top = cy - core
        if top > 0:                            # wash above the reading band
            g = QLinearGradient(0.0, top, 0.0, top - falloff)
            g.setSpread(QGradient.Spread.PadSpread)
            g.setColorAt(0.0, clear)
            g.setColorAt(1.0, self._focus_dim)
            painter.setBrush(QBrush(g))
            painter.drawRect(QRectF(0, 0, vp.width(), top))
        bottom = cy + core
        if bottom < vp.height():               # and below it
            g = QLinearGradient(0.0, bottom, 0.0, bottom + falloff)
            g.setSpread(QGradient.Spread.PadSpread)
            g.setColorAt(0.0, clear)
            g.setColorAt(1.0, self._focus_dim)
            painter.setBrush(QBrush(g))
            painter.drawRect(QRectF(0, bottom, vp.width(),
                                    vp.height() - bottom))

    def _paint_strike_range(self, painter, doc, layout, start, end, off):
        """Draw the strike across ``[start, end)`` line by line (a range can wrap),
        each segment a horizontal line through the text's vertical midline."""
        block = doc.findBlock(start)
        while block.isValid() and block.position() < end:
            bl = block.layout()
            bpos = block.position()
            btop = layout.blockBoundingRect(block).top()
            for i in range(bl.lineCount()):
                line = bl.lineAt(i)
                ls = bpos + line.textStart()
                le = ls + line.textLength()
                s, e = max(start, ls), min(end, le)
                if s >= e:
                    continue
                x1 = line.cursorToX(s - bpos)[0]
                x2 = line.cursorToX(e - bpos)[0]
                rect = line.naturalTextRect()
                y = btop + rect.top() + rect.height() * 0.58
                painter.drawLine(QPointF(x1 + off.x(), y + off.y()),
                                 QPointF(x2 + off.x(), y + off.y()))
            block = block.next()

    def _caret_cell(self, off):
        """The glyph-cell rectangle under the caret (viewport coords), or None
        if it can't be laid out — the soft block is painted here. Width is the
        advance to the next glyph; at a line end it falls back to a space."""
        pos = self.textCursor().position()
        doc = self.document()
        block = doc.findBlock(pos)
        if not block.isValid():
            return None
        bl = block.layout()
        rel = pos - block.position()
        line = bl.lineForTextPosition(rel)
        if not line.isValid():
            return None
        x1 = line.cursorToX(rel)[0]
        if rel < block.length() - 1:
            w = max(line.cursorToX(rel + 1)[0] - x1, 4.0)
        else:
            w = QFontMetricsF(self.font()).horizontalAdvance(" ")
        r = line.naturalTextRect()
        top = doc.documentLayout().blockBoundingRect(block).top() + r.top()
        return QRectF(x1 + off.x(), top + off.y(), w, r.height())

    def _paint_caret(self, off):
        """The soft block caret over the current glyph, only while the view has
        focus (an open card takes focus, so the caret rests then)."""
        if not self.hasFocus():
            return
        cell = self._caret_cell(off)
        if cell is None:
            return
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._caret_color)
        painter.drawRoundedRect(cell, 2.0, 2.0)
        painter.end()

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self.viewport().update()

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self.viewport().update()


def editor_help_html() -> str:
    """The editor's own help (F1). Owned here so it's identical whether the editor
    is embedded in a host app (e.g. grafli) or run standalone via ``textli`` —
    a self-contained contribution the host never has to know the contents of."""
    accent = ZEN_MD_SUGGEST_ADD.name()
    ink = ZEN_TEXT_COLOR.name()
    hdr = f"color:{accent};font-weight:bold;padding-top:14px;padding-bottom:2px"
    keyc = "font-family:monospace;white-space:nowrap;padding:3px 14px 3px 0;vertical-align:top"
    cell = "padding:3px 0;vertical-align:top"

    def rows(pairs):
        return "".join(
            f"<tr><td style='{keyc}'>{k}</td><td style='{cell}'>{d}</td></tr>"
            for k, d in pairs)

    return f"""
    <div style='color:{ink}'>
    <p style='color:{accent};font-weight:bold;font-size:15px'>textli — the zen Markdown editor</p>
    <p>A focused, distraction-free editor. It opens ready to type (vim NORMAL
    mode); <b>⌘R</b> flips to a rendered <b>reading view</b> for proof-reading,
    commenting, and suggesting changes. <b>F1</b> shows this help.</p>
    <p>The faint line in the card's corner is the <b>whisper status</b>: while
    writing it shows the vim mode, word count, and this session's delta; while
    reading, the section you're in (or where a link goes when the caret is on
    one), how far you are, roughly how many minutes remain, and what still
    awaits review. It hides whenever a card (search, open, overview) is up.</p>

    <p style='{hdr}'>Views &amp; session</p>
    <table>{rows([
        ("⌘R", "Toggle the source editor ↔ rendered reading view"),
        ("Esc", "Save &amp; close (⇧Esc cancels / discards pending changes)"),
        ("⌘↵", "Toggle full-window width"),
        ("⌘.", "Section focus — dim all but the current paragraph (writing) / section (reading)"),
        ("⌘T", "Typewriter scrolling — hold the caret line steady while writing (persists)"),
        ("⌘+ / ⌘- / ⌘0", "Font size bigger / smaller / reset (persists)"),
        ("⌘⇧→ / ⌘⇧← / ⌘⇧↓", "Content column wider / narrower / reset (persists)"),
        ("⌘J", "Word-jump overlay (Easymotion-style two-key jump)"),
        ("⌘P", "Print"),
        ("F1", "This help"),
    ])}</table>

    <p style='{hdr}'>Writing (vim — source editor)</p>
    <table>{rows([
        ("h j k l", "Move left / down / up / right"),
        ("w / b / e", "Next word / previous word / word end"),
        ("0 / $ · gg / G", "Line start / end · document start / end"),
        ("i a · I A · o O", "Enter INSERT: before/after · line start/end · new line below/above"),
        ("Esc", "Back to NORMAL mode"),
        ("x · dd · dw", "Delete char · line · to next word (into the register)"),
        ("u · ⌃r", "Undo · redo the last change"),
        ("v", "VISUAL — extend a selection with the motions, then d / y / c"),
        ("yy · yw · p / P", "Yank line / word · paste after / before"),
        ("2j · 3dd", "A leading count repeats the next motion or edit"),
        ("↵", "Follow the link under the caret — web/mail in the browser, <span style='font-family:monospace'>#heading</span> jumps there (NORMAL mode)"),
        ("go", "Open another file — history is fuzzy-matched, paths complete per segment"),
        ("gh", "Headings overview — an outline of the source (j/k preview, Enter keeps, Esc restores)"),
    ])}</table>

    <p style='{hdr}'>Search (/) — both views</p>
    <table>{rows([
        ("/", "Search the document — matching lines ranked best-first (exact above fuzzy)"),
        ("(type)", "Live hit list; the view scrolls to preview the selected hit"),
        ("⌃n / ⌃p · ↓ / ↑", "Move the selection"),
        ("Enter · Esc", "Jump to the hit · cancel back to where you were"),
        ("n / N", "Next / previous hit (wraps; the query survives ⌘R)"),
        ("⇥ (write view)", "Reveal replace — ↵ replaces this match & advances, ⌃↵ replaces all (literal matches)"),
    ])}</table>

    <p style='{hdr}'>Open-file dialog (go)</p>
    <table>{rows([
        ("(type)", "Fuzzy-match your history (files &amp; their folders); a path (with <span style='font-family:monospace'>/</span> or <span style='font-family:monospace'>~</span>) also completes the filesystem, segment by segment"),
        ("⌃n / ⌃p · ↓ / ↑", "Move the selection"),
        ("Tab", "Complete — extend to the common prefix, else adopt the selected row"),
        ("Enter", "Open the selected file (a directory descends into it); with no match, open the typed path as a new file"),
        ("Esc", "Cancel, back to the editor"),
    ])}</table>

    <p style='{hdr}'>Reading view — navigate</p>
    <table>{rows([
        ("h j k l · w b e · 0 $", "Move a caret through the rendered text"),
        ("gg / G", "Document start / end"),
        ("⌃d / ⌃u · ⌃f / ⌃b / Space", "Half-page · full-page scroll"),
        ("f", "Focus reading mode — caret-lock at centre + a spotlight on the reading line, fading text by distance (persists)"),
        ("gh", "Headings overview — j/k preview live, Enter keeps, Esc restores your spot"),
        ("gl", "Links overview — same jump-list; Enter follows the picked link"),
        ("↵", "Follow the link under the caret — a <span style='font-family:monospace'>.md</span> opens in place, web/mail in the browser, <span style='font-family:monospace'>#heading</span> jumps there"),
        ("gb / ⌫", "Back to the document the last link was followed from"),
        ("go", "Open another file (stays in the reading view)"),
    ])}</table>

    <p style='{hdr}'>Reading view — comments</p>
    <table>{rows([
        ("v", "Visual mode — extend a selection with the motions above"),
        ("c", "Comment the selection (or reveal/edit the comment under the caret)"),
        ("]c / [c", "Step to the next / previous comment"),
        ("Enter · ⇧D", "Reveal-edit · delete the active comment"),
    ])}</table>

    <p style='{hdr}'>Reading view — suggestions (track changes)</p>
    <table>{rows([
        ("s", "Suggest a change — replace the selection (empty = delete), or insert at the caret"),
        ("]s / [s", "Step to the next / previous suggestion"),
        ("a / x", "Accept / reject the suggestion under the caret and advance to the next"),
        ("⇧A / ⇧X", "Accept / reject all suggestions at once"),
        ("gc", "Changes overview — every change &amp; comment, same live preview as gh"),
        ("p", "Clean preview — the prose with every suggestion accepted (source untouched)"),
    ])}</table>

    <p style='color:{ink}'>Comments and suggestions live inline in the Markdown as
    <a href='http://criticmarkup.com/' style='color:{accent}'>CriticMarkup</a>
    (<span style='font-family:monospace'>{{==…==}}{{&gt;&gt;…&lt;&lt;}}</span>,
    <span style='font-family:monospace'>{{++…++}}</span>,
    <span style='font-family:monospace'>{{--…--}}</span>,
    <span style='font-family:monospace'>{{~~old~&gt;new~~}}</span>), so they travel
    with the file and diff in git — no sidecar.</p>
    </div>
    """


class ZenMarkdownEditor(QWidget):
    """Full-window zen editor for annotations and markdown files."""

    finished = Signal(str)
    cancelled = Signal()
    file_saved = Signal(Path)
    file_opened = Signal(Path)   # `go` switched to (or created) this file

    def __init__(
        self,
        parent: QWidget,
        text: str,
        title: str = "",
        file_path: Path | None = None,
        anchor: str = "",
        start_in_read: bool = False,
        canvas: QWidget | None = None,
    ):
        super().__init__(parent)
        # Bundled faces (JetBrains Mono, Caveat) — register on construction so
        # an embedding host renders identically to the standalone app without
        # extra wiring; idempotent, so the standalone call stays harmless (#25).
        register_bundled_fonts()
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        # Translucent so the dim wash painted in paintEvent composites over
        # the parent's content (e.g. a host canvas) instead of obscuring it.
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAutoFillBackground(False)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._file_path = file_path
        self._original_text = text
        # Live-reload: the content we last know is on disk — set on load and
        # after every autosave. On a file change, ``fileChanged`` compares the
        # disk against this to tell an external edit from our own write, and
        # the buffer against it to tell a clean reload from a conflict.
        self._disk_snapshot = text
        self._reloading = False       # guard: our own reload isn't a local edit
        self._reload_timer = None     # coalesces a burst of fileChanged events
        # The editor always opens editable; reading is the ⌘R rendered view.
        self._read_only = False
        # Section-focus dim (everything but the current paragraph) — off by
        # default, toggled with ⌘.
        self._focus_enabled = False
        self._watcher = None
        self._autosave_timer: QTimer | None = None
        # The host's canvas widget — the dim wash skips over this rect so
        # the canvas itself stays fully saturated while UI chrome dims.
        self._canvas = canvas

        # Load persisted font size preference
        settings = md_settings.app_settings()
        self._font_size = settings.value(
            "zen_md/font_size", ZEN_MD_FONT_SIZE, type=int
        )
        self._font_size = max(
            ZEN_MD_FONT_SIZE_MIN, min(ZEN_MD_FONT_SIZE_MAX, self._font_size)
        )

        # Typewriter scrolling (⌘T): keep the caret line at a fixed height
        # while writing, so the eyes never chase the text down the page.
        self._typewriter = settings.value(
            "zen_md/typewriter", False, type=bool
        )
        # Focus reading mode (`f`, read view): caret-lock at screen centre plus
        # a gradient spotlight on the current paragraph. Persists like ⌘T.
        self._read_focus = settings.value(
            "zen_md/read_focus", False, type=bool
        )

        # Load persisted content-column width preference (adjustable like font).
        self._content_width = settings.value(
            "zen_md/content_width", ZEN_MD_MAX_WIDTH, type=int
        )
        self._content_width = max(
            ZEN_MD_MAX_WIDTH_MIN, min(ZEN_MD_MAX_WIDTH_MAX, self._content_width)
        )

        # Opacity effect for fade in/out.
        self._opacity = QGraphicsOpacityEffect(self)
        self._opacity.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity)
        self._closing = False

        self.resize(parent.size())
        self._build_ui(title, text)
        self._setup_file_watcher()
        self._enable_autosave()
        # Every file-backed open feeds the `go` dialog's history — including
        # this one, so it's findable from the next session's first `go`.
        if file_path is not None:
            self._record_open_history(file_path)
            # Closing normally saves the position on hide; quitting the whole
            # app (⌘Q) tears the window down without one, so catch that too.
            # PySide drops the connection with the receiver, so a closed
            # editor never gets a stale call.
            QApplication.instance().aboutToQuit.connect(self._save_position)
        self.show()
        self._start_fade_in()
        # Open at a location / in a mode (used by textli's open-at-anchor). The
        # read-view toggle and centerCursor both need a laid-out viewport, so do
        # this after show(). Explicit requests win over memory: `-r` forces the
        # read view, an anchor overrides the remembered offsets.
        if start_in_read:
            self._toggle_rendered()
        if file_path is not None:
            self._restore_position(restore_mode=not start_in_read,
                                   restore_offsets=not anchor)
        if anchor:
            self._jump_to_anchor(anchor)

    # ── UI construction ──

    def _build_ui(self, title: str, text: str):
        self._full_width = False      # ⌘↵ expands the card to the window
        self._rendered_mode = False   # ⌘R shows a read-only rendered view
        # Read-view comment interaction state — initialized before any child
        # widget is built, since installing event filters can fire eventFilter
        # (which references these) during construction. _rendered_comments maps
        # each highlighted span to its source Comment; _active_comment is the
        # one ]c / [c stepped onto; _comment_field is the inline reveal editor.
        self._rendered_comments: list = []
        self._rendered_suggestions: list = []
        # Play the accept/reject animation (tests turn this off for determinism).
        self._suggest_animate = True
        self._active_comment = -1
        self._comment_field: QPlainTextEdit | None = None
        self._rendered_pending_bracket = ""
        # Authoring: vim visual mode in the read view selects the span to comment.
        self._visual = False
        self._authoring_span: tuple | None = None
        # True while the inline field is authoring a suggestion (vs a comment).
        self._authoring_suggestion = False
        # Transient READ/WRITE flash shown when toggling the rendered view.
        self._mode_flash: QLabel | None = None
        # `p` clean preview: render the fully-accepted prose (no markup) on/off.
        self._preview = False
        # Jump-list overlay shared by `gc` (changes) and `gh` (headings). Rows are
        # ``(start, end, html)`` rebuilt fresh on each open, so the list reflects
        # any document change (e.g. an accepted suggestion) since last time.
        self._overview_overlay: QLabel | None = None
        self._overview_rows = []
        self._overview_sel = 0
        self._overview_title = ""
        self._overview_scroll_top = False
        # The view the open overview drives — the rendered reader (`gc`/`gh`/`gl`)
        # or the source editor (`gh` in the write view). Set on each open.
        self._overview_view = None
        # `gl` follows the picked row (a link); `gc`/`gh` just land on it.
        self._overview_targets = None
        # In-session back-stack of (path, caret, scroll) for link navigation —
        # `gb`/Backspace walks it. Not persisted (position memory owns resume).
        self._nav_stack = []
        # Transient toast for link targets / grafli notice / nav landings.
        self._notice_flash: QLabel | None = None
        self._last_notice = ""            # test seam for the toast text
        # F1 help dialog (the editor owns its own help).
        self._help_dialog: QDialog | None = None
        layout = QVBoxLayout(self)
        self._apply_card_margins(layout)
        layout.setSpacing(0)

        # Pure text — no title, no hint bar, no badges. Discoverability
        # lives in F1 help; the card is just the writing surface.
        self._editor = QPlainTextEdit(text)
        self._editor.setFont(QFont(FONT_FAMILY, self._font_size))
        self._editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self._editor.setReadOnly(self._read_only)
        self._editor.setStyleSheet(
            f"QPlainTextEdit {{"
            f" background: {ZEN_MD_BG.name()}; color: {ZEN_TEXT_COLOR.name()};"
            f" border: none; padding: 0px;"
            f" selection-background-color: #B8D4E8;"
            f"}}"
        )
        self._editor.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        # Typewriter mode holds the caret line steady, which needs scrolling
        # past the document end (see _toggle_typewriter).
        self._editor.setCenterOnScroll(self._typewriter)
        layout.addWidget(self._editor, stretch=1)

        # Read-only rendered Markdown view (⌘R toggles editor <-> this).
        self._rendered = _ReadingView()
        self._rendered.setOpenExternalLinks(True)
        self._rendered.setFont(QFont(READING_FONT_FAMILY, self._font_size))
        self._rendered.setStyleSheet(
            f"QTextBrowser {{"
            f" background: {ZEN_MD_BG.name()}; color: {ZEN_TEXT_COLOR.name()};"
            f" border: none; padding: 0px;"
            f" selection-background-color: #B8D4E8;"
            f"}}"
        )
        # Keyboard-selectable so the read view has a movable caret for vim
        # motions and visual-mode span selection (it stays read-only).
        self._rendered.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
            | Qt.TextInteractionFlag.LinksAccessibleByMouse
        )
        self._rendered.setVisible(False)
        self._rendered.installEventFilter(self)
        # Section focus and the whisper breadcrumb follow the read-view caret
        # (a caret move that doesn't scroll won't fire the scrollbar signal).
        self._rendered.cursorPositionChanged.connect(
            self._update_rendered_focus)
        self._rendered.cursorPositionChanged.connect(self._update_read_focus)
        self._rendered.cursorPositionChanged.connect(self._refresh_status)
        layout.addWidget(self._rendered, stretch=1)

        # Animates accept/reject on the read view (fade what leaves, settle what
        # stays) before the source edit lands.
        self._suggest_animator = SuggestionAnimator(
            self._rendered,
            body_color=ZEN_TEXT_COLOR,
            body_family=FONT_FAMILY,
            del_color=ZEN_TEXT_COLOR,   # removals are body-ink now (just struck)
            add_color=ZEN_MD_SUGGEST_ADD,
        )

        # Markdown highlighter + paragraph focus (off by default; ⌘. toggles)
        self._highlighter = MarkdownHighlighter(self._editor.document())
        self._highlighter.set_base_size(self._font_size)
        self._editor.cursorPositionChanged.connect(self._update_focus)
        self._editor.cursorPositionChanged.connect(self._typewriter_recenter)
        self._highlighter.set_focus_enabled(self._focus_enabled)

        # Heading gutter — `#` markers hang to the left of body text.
        self._applying_layout = False
        self._apply_heading_layout()
        self._editor.textChanged.connect(self._on_text_changed_layout)

        # Vim key handler
        self._vim = VimKeyHandler(
            editor=self._editor,
            mode_changed=self._on_mode_changed,
            close_save=self._close_save,
            close_cancel=self._close_cancel,
            open_file=self._open_file_dialog,
            open_headings=self._open_headings_overview,
        )
        # `go` open-file overlay (created on demand, one at a time).
        self._open_overlay: OpenFileOverlay | None = None
        # `/` in-document search: overlay, last query (n/N re-run it against
        # the active view), and the position to restore on Esc.
        self._search_overlay: SearchOverlay | None = None
        self._search_query = ""
        self._search_saved: tuple[int, int] | None = None
        self._editor.setOverwriteMode(True)  # block cursor in normal mode
        self._editor.setAttribute(Qt.WidgetAttribute.WA_InputMethodEnabled, False)
        self._editor.installEventFilter(self)  # intercept keys before editor

        # Word jump overlay
        self._jump: WordJumpOverlay | None = None

        # Whisper status — one faint line in the card's corner (content built
        # in textli.status). Word counts are debounced off textChanged; the
        # read view updates as it scrolls. Never interactive, never boxed.
        self._status_label = QLabel(self)
        self._status_label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._status_label.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._status_label.setStyleSheet(
            f"color: rgba({ZEN_HINT_COLOR.red()}, {ZEN_HINT_COLOR.green()},"
            f" {ZEN_HINT_COLOR.blue()}, 175); background: transparent;")
        self._session_start_words = md_status.word_count(text)
        self._status_timer = QTimer(self)
        self._status_timer.setSingleShot(True)
        self._status_timer.setInterval(300)
        self._status_timer.timeout.connect(self._refresh_status)
        self._editor.textChanged.connect(self._status_timer.start)
        self._rendered.verticalScrollBar().valueChanged.connect(
            lambda _v: self._refresh_status())

        # Focus and cursor
        self._editor.setFocus()
        cursor = self._editor.textCursor()
        cursor.movePosition(cursor.MoveOperation.Start)
        self._editor.setTextCursor(cursor)
        self._update_focus()
        self._refresh_status()

    def _on_mode_changed(self, mode: VimMode):
        # Disable macOS input method in normal mode to prevent IMK
        # interference with auto-repeat key events.
        self._editor.setAttribute(
            Qt.WidgetAttribute.WA_InputMethodEnabled,
            mode == VimMode.INSERT,
        )
        self._refresh_status()

    # ── Whisper status line ──

    def _refresh_status(self):
        """Recompute and re-place the whisper status line. Hidden while any
        overlay card is up — the whisper never competes for attention."""
        lbl = getattr(self, "_status_label", None)
        if lbl is None:
            return
        if (self._search_overlay is not None
                or self._open_overlay is not None
                or self._overview_overlay is not None):
            lbl.hide()
            return
        src = self._editor.toPlainText()
        words = md_status.word_count(src)
        if self._rendered_mode:
            sb = self._rendered.verticalScrollBar()
            span = sb.maximum() + sb.pageStep()
            progress = (sb.value() + sb.pageStep()) / span if span else 1.0
            href = self._rendered_anchor_at_caret()
            text = md_status.read_status(
                progress, words,
                changes=len(self._rendered_suggestions),
                comment_count=len(self._rendered_comments),
                section=self._current_rendered_section(),
                link=self._link_hint(href) if href else "")
            if self._visual:
                text = f"VISUAL{md_status.SEP}{text}"
        else:
            text = md_status.write_status(
                self._vim.mode.value, words,
                words - self._session_start_words)
        lbl.setFont(QFont(
            FONT_FAMILY, max(ZEN_MD_FONT_SIZE_MIN, self._font_size - 4)))
        lbl.setText(text)
        lbl.adjustSize()
        card = self._card_rect()
        lbl.move(int(card.right()) - lbl.width() - ZEN_MD_CARD_INNER_PAD_H,
                 int(card.bottom()) - lbl.height() - 10)
        lbl.show()
        lbl.raise_()

    def _start_fade_in(self):
        anim = QPropertyAnimation(self._opacity, b"opacity", self)
        anim.setDuration(320)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
        self._fade_in_anim = anim  # hold ref so it doesn't get GC'd mid-run

    def _close_save(self):
        if self._file_path:
            self._autosave()   # flush any pending edit before closing
            self._fade_out_and_close(self._emit_cancelled)
        else:
            captured = self._editor.toPlainText()
            self._fade_out_and_close(lambda: self._emit_finished(captured))

    def _close_cancel(self):
        self._fade_out_and_close(self._emit_cancelled)

    def _emit_cancelled(self):
        self.cancelled.emit()
        self.close()

    def _emit_finished(self, text: str):
        self.finished.emit(text)
        self.close()

    def _fade_out_and_close(self, callback):
        if self._closing:
            return
        self._closing = True
        anim = QPropertyAnimation(self._opacity, b"opacity", self)
        anim.setDuration(240)
        anim.setStartValue(self._opacity.opacity())
        anim.setEndValue(0.0)
        anim.setEasingCurve(QEasingCurve.Type.InCubic)
        anim.finished.connect(callback)
        anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
        self._fade_out_anim = anim

    def _update_focus(self):
        if not self._focus_enabled:
            return
        start, end = compute_focus_range(self._editor)
        self._highlighter.set_focus_range(start, end)

    @staticmethod
    def _slugify(text: str) -> str:
        """Convert heading text to a markdown anchor slug."""
        s = text.lower().strip()
        s = re.sub(r"[^\w\s-]", "", s)
        return re.sub(r"[\s]+", "-", s).strip("-")

    def _jump_to_anchor(self, anchor: str):
        """Scroll to the heading matching the given anchor slug, in whichever
        view is active. In the source editor a heading carries its `#` markers;
        in the rendered read view they're gone, so identify headings by their
        block heading-level (set by Markdown rendering) and match the bare text."""
        rendered = self._rendered_mode
        view = self._rendered if rendered else self._editor
        doc = view.document()
        block = doc.begin()
        while block.isValid():
            if rendered:
                is_heading = block.blockFormat().headingLevel() > 0
                heading = block.text() if is_heading else None
            else:
                m = re.match(r"^#{1,6}\s+(.*)", block.text())
                heading = m.group(1) if m else None
            if heading is not None and self._slugify(heading) == anchor:
                cursor = view.textCursor()
                cursor.setPosition(block.position())
                view.setTextCursor(cursor)
                if rendered:
                    # QTextBrowser has no centerCursor — scroll the heading to
                    # the top of the viewport (natural for an anchor landing).
                    y = int(doc.documentLayout().blockBoundingRect(block).y())
                    view.verticalScrollBar().setValue(y)
                else:
                    view.centerCursor()
                return
            block = block.next()

    # ── Heading-gutter layout ──

    _RE_HEADING_PREFIX = re.compile(r"^(#{1,3})\s+")

    def _gutter_metrics(self) -> tuple[float, float]:
        """Return (char_width, gutter_width). Gutter fits the longest
        heading marker (`### ` = 4 chars).
        """
        char_w = QFontMetricsF(self._editor.font()).horizontalAdvance(" ")
        return char_w, char_w * 4

    def _apply_block_layout(self, block) -> None:
        """Set the block's leftMargin/textIndent so heading `#`s hang in
        the gutter and heading text aligns with body text.
        """
        char_w, gutter = self._gutter_metrics()
        m = self._RE_HEADING_PREFIX.match(block.text())
        fmt = QTextBlockFormat()
        fmt.setLeftMargin(gutter)
        if m:
            level = len(m.group(1))
            fmt.setTextIndent(-char_w * (level + 1))
        else:
            fmt.setTextIndent(0)
        current = block.blockFormat()
        if (current.leftMargin() == fmt.leftMargin()
                and current.textIndent() == fmt.textIndent()):
            return
        cursor = QTextCursor(block)
        self._applying_layout = True
        try:
            cursor.setBlockFormat(fmt)
        finally:
            self._applying_layout = False

    def _apply_heading_layout(self) -> None:
        """Apply heading-gutter layout to every block in the document."""
        doc = self._editor.document()
        block = doc.firstBlock()
        while block.isValid():
            self._apply_block_layout(block)
            block = block.next()

    def _on_text_changed_layout(self) -> None:
        """Re-apply layout to the block under the cursor on every edit."""
        if self._applying_layout:
            return
        self._apply_block_layout(self._editor.textCursor().block())

    # ── File watching & autosave ──

    def _setup_file_watcher(self):
        if not self._file_path or not self._file_path.exists():
            return
        self._watcher = QFileSystemWatcher([str(self._file_path)], self)
        self._watcher.fileChanged.connect(self._on_file_changed)

    def _on_file_changed(self, path: str):
        """Something wrote the open file. Re-arm the watch — a replace-by-rename
        drops it on many platforms — and debounce: editors and agents often
        write in a burst (temp file, rename), firing several events. The
        settled decision happens in :meth:`_reload_if_changed`."""
        if self._watcher and path not in self._watcher.files():
            self._watcher.addPath(path)
        if self._reload_timer is None:
            self._reload_timer = QTimer(self)
            self._reload_timer.setSingleShot(True)
            self._reload_timer.timeout.connect(self._reload_if_changed)
        self._reload_timer.start(150)

    def _reload_if_changed(self):
        """Reflect an external edit in place. Read the file and compare: in sync
        or our own last write → ignore; changed with a clean buffer → reload,
        keeping the view, caret and scroll; changed while the buffer has unsaved
        local edits → a conflict, so warn and keep the buffer (it wins on the
        next autosave), leaving reconciliation to #24."""
        if getattr(self, "_editor", None) is None:
            return                       # mid-teardown; child refs may be gone
        if not self._file_path or not self._file_path.exists():
            return
        if self._watcher and str(self._file_path) not in self._watcher.files():
            self._watcher.addPath(str(self._file_path))
        try:
            disk = self._file_path.read_text(encoding="utf-8")
        except OSError:
            return                       # mid-write; a later event settles it
        if disk == self._editor.toPlainText() or disk == self._disk_snapshot:
            self._disk_snapshot = disk   # our own write, or already in sync
            return
        if self._editor.toPlainText() == self._disk_snapshot:
            self._reload_from_disk(disk)     # no unsaved edits → clean reload
            self._flash_notice("↻ reloaded — file changed on disk")
        else:
            self._flash_notice("⚠ file changed on disk — kept your edits")

    def _reload_from_disk(self, text: str):
        """Replace the buffer with ``text`` from disk, restoring the active
        view's caret and scroll and re-rendering the read view so comments and
        suggestions come back. Guarded so the replacement isn't taken for a
        local edit (which would re-save and echo back through the watcher)."""
        self._reloading = True
        try:
            if self._rendered_mode:
                sb = self._rendered.verticalScrollBar()
                scroll, caret = sb.value(), self._rendered.textCursor().position()
                self._editor.setPlainText(text)
                self._apply_heading_layout()
                self._render_markdown(text)
                rendered = self._rendered.document().toPlainText()
                cur = self._rendered.textCursor()
                cur.setPosition(min(caret, len(rendered)))
                self._rendered.setTextCursor(cur)
                if not self._read_focus:     # focus mode re-locks the caret itself
                    sb.setValue(min(scroll, sb.maximum()))
            else:
                sb = self._editor.verticalScrollBar()
                scroll, caret = sb.value(), self._editor.textCursor().position()
                self._editor.setPlainText(text)
                self._apply_heading_layout()
                cur = self._editor.textCursor()
                cur.setPosition(min(caret, len(text)))
                self._editor.setTextCursor(cur)
                sb.setValue(min(scroll, sb.maximum()))
            self._disk_snapshot = text
        finally:
            self._reloading = False
        self._refresh_status()

    def _enable_autosave(self):
        """Doc-backed notes open editable, so wire up autosave from the start
        (debounced). The file watcher stays live alongside it: an external edit
        reloads in place rather than being overwritten blind (see
        :meth:`_on_file_changed`)."""
        if not self._file_path:
            return
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setSingleShot(True)
        self._autosave_timer.setInterval(500)
        self._autosave_timer.timeout.connect(self._autosave)
        self._editor.textChanged.connect(self._schedule_autosave)

    def _toggle_typewriter(self):
        """⌘T — typewriter scrolling on/off (persists). On, the caret line is
        held at a fixed height in the write view while the text moves — the
        page scrolls under a stationary carriage, like the machine it's named
        after."""
        self._typewriter = not self._typewriter
        md_settings.app_settings().setValue(
            "zen_md/typewriter", self._typewriter)
        # centerOnScroll lets the view scroll past the last line — without it
        # the caret can't be held at typewriter height near the document end.
        self._editor.setCenterOnScroll(self._typewriter)
        if self._typewriter:
            self._typewriter_recenter()
        self._flash_mode(
            "TYPEWRITER" if self._typewriter else "TYPEWRITER OFF")

    def _typewriter_recenter(self):
        """Keep the caret line at the typewriter height (~40% down the
        viewport). QPlainTextEdit's vertical scrollbar works in line steps, so
        the pixel offset converts via the line height."""
        if not getattr(self, "_typewriter", False) or self._rendered_mode:
            return
        ed = self._editor
        target = int(ed.viewport().height() * 0.42)
        line_h = ed.fontMetrics().lineSpacing() or 1
        delta = round((ed.cursorRect().center().y() - target) / line_h)
        if delta:
            sb = ed.verticalScrollBar()
            sb.setValue(sb.value() + delta)

    def _toggle_focus(self):
        """⌘. — toggle the section-focus dim (everything but the current
        paragraph). Off by default."""
        self._focus_enabled = not self._focus_enabled
        self._highlighter.set_focus_enabled(self._focus_enabled)
        if self._focus_enabled and self._read_focus:
            # Only one focus at a time: ⌘. turns off `f` reading mode.
            self._read_focus = False
            md_settings.app_settings().setValue("zen_md/read_focus", False)
            self._update_read_focus()
        if self._focus_enabled:
            self._update_focus()
        self._update_rendered_focus()
        self.update()

    def _schedule_autosave(self):
        if self._reloading:      # a disk reload isn't a local edit to save back
            return
        if self._autosave_timer:
            self._autosave_timer.start()

    def _autosave(self):
        if not self._file_path or self._read_only:
            return
        text = self._editor.toPlainText()
        self._file_path.write_text(text, encoding="utf-8")
        # Record what we put on disk so the watcher can tell this write from an
        # external one, and re-arm the watch (a truncating write can drop it).
        self._disk_snapshot = text
        if self._watcher and str(self._file_path) not in self._watcher.files():
            self._watcher.addPath(str(self._file_path))
        self.file_saved.emit(self._file_path)

    # ── Per-file position memory ──

    @staticmethod
    def _load_positions() -> list[str]:
        """Persisted per-file positions (see :mod:`textli.positions`).
        QSettings hands a lone entry back as a plain string."""
        val = md_settings.app_settings().value("open/positions", [])
        if isinstance(val, str):
            return [val]
        return list(val or [])

    @staticmethod
    def _store_positions(entries: list[str]):
        md_settings.app_settings().setValue("open/positions", entries)

    def _save_position(self):
        """Remember where this file is being left: the view mode, the write
        caret, and (in the read view) the rendered position at the top of the
        viewport — so reopening resumes exactly here."""
        if not self._file_path or getattr(self, "_editor", None) is None:
            return
        top = 0
        if self._rendered_mode:
            top = self._rendered.cursorForPosition(QPoint(0, 0)).position()
        self._store_positions(md_positions.remember(
            self._load_positions(), str(self._file_path),
            "read" if self._rendered_mode else "write",
            self._editor.textCursor().position(), top))

    def _restore_position(self, *, restore_mode: bool, restore_offsets: bool):
        """Resume the stored spot for the current file. ``restore_mode`` also
        re-enters the read view when the file was left there (skipped when the
        caller forced a view); ``restore_offsets`` puts caret and scroll back
        (skipped when an anchor names an explicit target)."""
        stored = (md_positions.lookup(self._load_positions(),
                                      str(self._file_path))
                  if self._file_path else None)
        if stored is None:
            return
        mode, caret, top = stored
        if restore_mode and mode == "read" and not self._rendered_mode:
            self._toggle_rendered()
        if not restore_offsets:
            return
        cur = self._editor.textCursor()
        cur.setPosition(min(caret, len(self._editor.toPlainText())))
        self._editor.setTextCursor(cur)
        self._editor.centerCursor()
        if self._rendered_mode and mode == "read":
            doc = self._rendered.document()
            pos = min(top, max(0, doc.characterCount() - 1))
            block = doc.findBlock(pos)
            y = doc.documentLayout().blockBoundingRect(block).y()
            # Line-level, not block-level: a long wrapped paragraph is one
            # block, and its top can be pages above the remembered spot.
            line = block.layout().lineForTextPosition(pos - block.position())
            if line.isValid():
                y += line.y()
            self._rendered.verticalScrollBar().setValue(int(y))
            rcur = self._rendered.textCursor()
            rcur.setPosition(pos)
            self._rendered.setTextCursor(rcur)

    # ── `go` open-file dialog ──

    @staticmethod
    def _load_open_history() -> list[str]:
        """Persisted open-history (most recent first). QSettings hands a lone
        entry back as a plain string — normalize to a list of str."""
        val = md_settings.app_settings().value("open/history", [])
        if isinstance(val, str):
            val = [val]
        return [str(v) for v in (val or [])]

    def _record_open_history(self, path: Path):
        """LRU-promote ``path`` in the persisted history (see openfile)."""
        hist = openfile.push_history(self._load_open_history(), str(path))
        md_settings.app_settings().setValue("open/history", hist)

    def _open_file_dialog(self):
        """go — the keyboard-only open-file overlay: history matched fuzzily,
        the filesystem completed per segment. Only for file-backed editing —
        an embedded, text-only editor has nowhere to switch to."""
        if self._open_overlay is not None or not self._file_path:
            return
        overlay = OpenFileOverlay(
            self, self._load_open_history(), self._font_size)
        overlay.chosen.connect(self._on_open_chosen)
        overlay.cancelled.connect(self._close_open_dialog)
        self._open_overlay = overlay
        overlay.open()
        self._refresh_status()

    def _close_open_dialog(self):
        if self._open_overlay is not None:
            self._open_overlay.hide()
            self._open_overlay.deleteLater()
            self._open_overlay = None
        # Back to whichever view the dialog was opened from.
        (self._rendered if self._rendered_mode else self._editor).setFocus()
        self._refresh_status()

    def _on_open_chosen(self, path: str):
        self._close_open_dialog()
        self._switch_file(Path(path))

    def _switch_file(self, path: Path):
        """Jump the editor to ``path``: flush the current file (autosave owns
        it, so there is nothing to ask), swap the buffer, and re-anchor. A path
        that doesn't exist yet opens empty — created on first save, like the
        CLI. The undo stack starts fresh (undo never crosses files)."""
        if path == self._file_path:
            return
        self._save_position()   # remember the file being left
        if self._autosave_timer is not None and self._autosave_timer.isActive():
            self._autosave_timer.stop()
            self._autosave()
        if self._watcher is not None and self._file_path:
            self._watcher.removePath(str(self._file_path))
        self._file_path = path
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        self._disk_snapshot = text       # new file's on-disk baseline
        if self._watcher is None:        # started on a not-yet-existing file
            self._setup_file_watcher()
        elif path.exists():
            self._watcher.addPath(str(path))
        self._editor.setPlainText(text)
        # setPlainText scheduled an autosave; a mere open must not touch the
        # disk (a new file would materialize empty before any typing).
        if self._autosave_timer is not None:
            self._autosave_timer.stop()
        self._apply_heading_layout()
        cur = self._editor.textCursor()
        cur.movePosition(QTextCursor.MoveOperation.Start)
        self._editor.setTextCursor(cur)
        self._update_focus()
        if self._rendered_mode:
            # Opened from the reading view — stay there, on the new file.
            self._preview = False
            self._render_markdown(text)
            rcur = self._rendered.textCursor()
            rcur.movePosition(QTextCursor.MoveOperation.Start)
            self._rendered.setTextCursor(rcur)
            self._rendered.verticalScrollBar().setValue(0)
        # Resume where this file was left (offsets only — `go` stays in the
        # view it was invoked from, as read-mode `go` promised).
        self._restore_position(restore_mode=False, restore_offsets=True)
        # A fresh file starts a fresh session baseline for the status delta.
        self._session_start_words = md_status.word_count(text)
        self._refresh_status()
        self._record_open_history(path)
        self.file_opened.emit(path)

    # ── `/` in-document search ──

    def _active_view(self):
        """The view the reader is in — search always works on its text."""
        return self._rendered if self._rendered_mode else self._editor

    def _open_search(self):
        """/ — the in-document search card: per-line fuzzy hits in document
        order, live preview of the selected hit, Esc restores the position."""
        if self._search_overlay is not None:
            return
        view = self._active_view()
        self._search_saved = (view.verticalScrollBar().value(),
                              view.textCursor().position())
        overlay = SearchOverlay(self, view.toPlainText, self._font_size,
                                allow_replace=not self._rendered_mode)
        overlay.selection_changed.connect(self._search_preview)
        overlay.accepted.connect(self._search_accept)
        overlay.cancelled.connect(self._search_cancel)
        overlay.cleared.connect(
            lambda: self._active_view().setExtraSelections([]))
        overlay.replace_opened.connect(self._replace_opened)
        overlay.replace_one.connect(self._replace_one)
        overlay.replace_all.connect(self._replace_all)
        self._search_overlay = overlay
        overlay.open()
        self._refresh_status()

    def _close_search_overlay(self):
        if self._search_overlay is not None:
            self._search_overlay.hide()
            self._search_overlay.deleteLater()
            self._search_overlay = None
        self._active_view().setFocus()
        self._refresh_status()

    def _search_preview(self, start: int, _end: int):
        """Live preview while the selection moves through the hit list: scroll
        the view to the hit and refresh the highlights."""
        ov = self._search_overlay
        if ov is None:
            return
        view = self._active_view()
        self._apply_search_highlights(view, ov.hits, start, ov.query)
        self._center_view_on(
            view, self._search_caret_pos(ov.hits, start, ov.query))
        self._ensure_hit_visible(view, ov)

    def _ensure_hit_visible(self, view, ov):
        """The preview must never hide behind the search card: nudge the scroll
        until the caret clears the card — and when it can't (a hit near the
        document edge, nothing left to scroll), flip the card to the other
        edge, where the hit is visible by construction."""
        vp_top = view.viewport().mapTo(self, QPoint(0, 0)).y()
        margin = 12
        sb = view.verticalScrollBar()

        def caret_top():
            return view.cursorRect().top() + vp_top

        def caret_bottom():
            return view.cursorRect().bottom() + vp_top

        card = ov.geometry()
        if (caret_bottom() < card.top() - margin
                or caret_top() > card.bottom() + margin):
            return                                   # already in the clear
        if ov.region == "top":
            # Push the content down until the caret drops below the card.
            for _ in range(200):
                if caret_top() > card.bottom() + margin:
                    return
                v = sb.value()
                sb.setValue(v - max(1, sb.singleStep()))
                if sb.value() == v:
                    break                            # top of the document
            ov.place_region("bottom")
        else:
            # Pull the content up until the caret rises above the card.
            for _ in range(200):
                if caret_bottom() < card.top() - margin:
                    return
                v = sb.value()
                sb.setValue(v + max(1, sb.singleStep()))
                if sb.value() == v:
                    break                            # end of the document
            ov.place_region("top")

    def _search_accept(self, start: int, _end: int):
        """Enter — jump to the hit and keep the query for n/N."""
        ov = self._search_overlay
        self._search_query = ov.query if ov else self._search_query
        hits = list(ov.hits) if ov else []
        self._close_search_overlay()
        view = self._active_view()
        self._apply_search_highlights(view, hits, start, self._search_query)
        self._center_view_on(
            view, self._search_caret_pos(hits, start, self._search_query))

    def _search_cancel(self):
        """Esc — back to where the reader was, highlights gone, previous
        query kept (like vim's aborted search)."""
        self._close_search_overlay()
        view = self._active_view()
        view.setExtraSelections([])
        if self._search_saved is not None:
            scroll, caret = self._search_saved
            self._search_saved = None
            cur = view.textCursor()
            cur.setPosition(min(caret, len(view.toPlainText())))
            view.setTextCursor(cur)
            view.verticalScrollBar().setValue(scroll)

    def _search_step(self, direction: int):
        """n / N — the nearest hit after/before the caret, wrapping around the
        document. Re-runs the last query against the active view's current
        text, so it survives edits, accept/reject, and the ⌘R view switch."""
        if not self._search_query:
            return
        view = self._active_view()
        hits = md_search.find_hits(view.toPlainText(), self._search_query)
        # Compare against the caret's *line start*: the caret sits on the match
        # (mid-line), and stepping back must not re-land on the same hit.
        pos = view.document().findBlock(
            view.textCursor().position()).position()
        h = md_search.next_hit(hits, pos, direction)
        if h is None:
            return
        self._apply_search_highlights(view, hits, h.start, self._search_query)
        self._center_view_on(
            view, self._search_caret_pos(hits, h.start, self._search_query))

    @staticmethod
    def _search_caret_pos(hits, line_start: int, query: str) -> int:
        """Where the caret lands on a hit: on its first match span (vim lands
        on the match, not the line), else the line start."""
        h = next((x for x in hits if x.start == line_start), None)
        if h is not None and h.spans:
            return h.start + h.spans[0][0]
        return line_start

    def _apply_search_highlights(self, view, hits, current_start: int,
                                 query: str):
        """Every match span (the phrase, or each matched word) gets the soft
        wash; the current hit's spans the stronger one — ExtraSelections only,
        the document itself is never touched."""
        sels = []
        for h in hits:
            color = (ZEN_SEARCH_CURRENT if h.start == current_start
                     else ZEN_SEARCH_HIT)
            for a, b in (h.spans or ((0, h.end - h.start),)):
                sel = QTextBrowser.ExtraSelection()
                cur = QTextCursor(view.document())
                cur.setPosition(h.start + a)
                cur.setPosition(h.start + b, QTextCursor.MoveMode.KeepAnchor)
                sel.cursor = cur
                sel.format.setBackground(QBrush(color))
                sels.append(sel)
        view.setExtraSelections(sels)

    def _center_view_on(self, view, pos: int):
        """Park the caret at ``pos`` and scroll it comfortably into view."""
        cur = view.textCursor()
        cur.setPosition(pos)
        view.setTextCursor(cur)
        if view is self._editor:
            view.centerCursor()
        else:
            doc = view.document()
            y = doc.documentLayout().blockBoundingRect(doc.findBlock(pos)).y()
            sb = view.verticalScrollBar()
            sb.setValue(max(0, int(y - view.viewport().height() * 0.35)))

    # ── Replace (write view only; targets literal matches) ──

    def _highlight_literal(self, view, query: str, current: int | None = None):
        """Wash every literal match of ``query``; the one starting at ``current``
        gets the stronger wash — ExtraSelections only, never touching the text."""
        sels = []
        for s, e in md_search.find_literal(view.toPlainText(), query):
            sel = QTextBrowser.ExtraSelection()
            cur = QTextCursor(view.document())
            cur.setPosition(s)
            cur.setPosition(e, QTextCursor.MoveMode.KeepAnchor)
            sel.cursor = cur
            sel.format.setBackground(QBrush(
                ZEN_SEARCH_CURRENT if s == current else ZEN_SEARCH_HIT))
            sels.append(sel)
        view.setExtraSelections(sels)

    def _goto_literal(self, view, query: str, from_pos: int):
        """Land on the first literal match at/after ``from_pos`` (wrapping),
        scroll it clear of the search card, and highlight it as current. Returns
        the match ``(start, end)`` or ``None`` when there are none."""
        matches = md_search.find_literal(view.toPlainText(), query)
        if not matches:
            view.setExtraSelections([])
            return None
        m = next(((s, e) for s, e in matches if s >= from_pos), matches[0])
        self._center_view_on(view, m[0])
        self._highlight_literal(view, query, current=m[0])
        if self._search_overlay is not None:
            self._ensure_hit_visible(view, self._search_overlay)
        return m

    def _replace_opened(self):
        """Tab revealed the replace field — switch the preview from the fuzzy
        hits to the literal matches replace acts on, landing on the first at or
        after the caret."""
        ov = self._search_overlay
        if ov is None:
            return
        self._goto_literal(self._active_view(), ov.query,
                           self._active_view().textCursor().position())

    def _replace_one(self, query: str, replacement: str):
        """↵ in the replace field — replace the current literal match (the one at
        the caret, else the next), one undoable step, then advance to the next."""
        if not query:
            return
        view = self._active_view()
        matches = md_search.find_literal(view.toPlainText(), query)
        if not matches:
            return
        caret = view.textCursor().position()
        s, e = next(((s, e) for s, e in matches if s >= caret), matches[0])
        cur = view.textCursor()
        cur.setPosition(s)
        cur.setPosition(e, QTextCursor.MoveMode.KeepAnchor)
        cur.insertText(replacement)                 # undoable
        self._search_query = query
        self._search_saved = None                   # a replace happened — Esc stays put
        self._goto_literal(view, query, s + len(replacement))
        if self._search_overlay is not None:
            self._search_overlay.refresh_hits()

    def _replace_all(self, query: str, replacement: str):
        """⌃↵ — replace every literal match in one undoable step (right-to-left,
        so earlier offsets stay valid as the text shifts)."""
        if not query:
            return
        view = self._active_view()
        matches = md_search.find_literal(view.toPlainText(), query)
        if not matches:
            return
        cur = view.textCursor()
        cur.beginEditBlock()
        for s, e in reversed(matches):
            cur.setPosition(s)
            cur.setPosition(e, QTextCursor.MoveMode.KeepAnchor)
            cur.insertText(replacement)
        cur.endEditBlock()
        self._search_query = query
        self._search_saved = None
        view.setExtraSelections([])                 # nothing left to mark
        if self._search_overlay is not None:
            self._search_overlay.refresh_hits()

    def _print(self):
        """⌘P — native print dialog. In the reading view it prints the typeset
        page (not the raw source), with the code band baked in as a real block
        background since the on-screen band is view-painting. In the write view
        it prints the source with section-focus dimming off."""
        write_mode = not self._rendered_mode
        if write_mode:
            self._highlighter.set_focus_enabled(False)
        printer = QPrinter()
        dialog = QPrintDialog(printer, self)
        if dialog.exec() == QPrintDialog.DialogCode.Accepted:
            if write_mode:
                self._editor.print_(printer)
            else:
                self._print_rendered(printer)
        if write_mode:
            self._highlighter.set_focus_enabled(self._focus_enabled)

    def _print_rendered(self, printer):
        """Print the read view's typeset page — via a clone whose code band is
        re-expressed as a real block background, since the on-screen band is
        view-painting. The live document is untouched."""
        self._baked_print_doc().print_(printer)

    def _baked_print_doc(self):
        """A clone of the rendered document with the code band baked in as a
        real block background — the one view-painted overlay that carries
        meaning on paper. Heading rules and the quote bar stay screen-only
        (no document-format equivalent). Cloning keeps the live view intact."""
        doc = self._rendered.document().clone()
        band = QTextBlockFormat()
        band.setBackground(ZEN_MD_CODE_BLOCK_BG)
        block = doc.begin()
        while block.isValid():
            if block.blockFormat().hasProperty(
                    QTextFormat.Property.BlockCodeFence):
                cur = QTextCursor(doc)
                cur.setPosition(block.position())
                cur.mergeBlockFormat(band)
            block = block.next()
        return doc

    def _show_help(self):
        """F1 — the editor's own help dialog (modeless, so it never blocks the
        writing surface). Built from :func:`editor_help_html`, which the editor
        owns so embedded and standalone use show the exact same content."""
        dlg = QDialog(self)
        dlg.setWindowTitle("textli — help")
        dlg.setModal(True)
        dlg.resize(560, 720)
        browser = QTextBrowser(dlg)
        browser.setOpenExternalLinks(True)
        browser.setFont(QFont(
            FONT_FAMILY, max(ZEN_MD_FONT_SIZE_MIN, self._font_size - 4)))
        browser.setStyleSheet(
            f"QTextBrowser {{ background: {ZEN_MD_BG.name()};"
            f" color: {ZEN_TEXT_COLOR.name()}; border: none; padding: 14px; }}")
        browser.setHtml(editor_help_html())
        btn = QPushButton("Close", dlg)
        btn.clicked.connect(dlg.accept)
        lay = QVBoxLayout(dlg)
        lay.addWidget(browser, 1)
        lay.addWidget(btn)
        self._help_dialog = dlg
        dlg.show()

    def _toggle_full_width(self):
        """⌘↵: expand the card to fill the window (and back to the column)."""
        self._full_width = not self._full_width
        layout = self.layout()
        if layout:
            self._apply_card_margins(layout)
        self._apply_heading_layout()
        self.update()
        self._refresh_status()

    def _toggle_rendered(self):
        """⌘R: switch between the source editor and a read-only rendered
        Markdown view — a quick read perspective <-> edit perspective."""
        self._close_overview()
        # Search highlights address one view's offsets — stale in the other.
        # The query itself survives: n/N re-runs it against the new view.
        self._editor.setExtraSelections([])
        self._rendered.setExtraSelections([])
        self._rendered_mode = not self._rendered_mode
        if self._rendered_mode:
            self._active_comment = -1
            self._rendered_pending_bracket = ""
            self._visual = False
            self._authoring_span = None
            self._authoring_suggestion = False
            self._preview = False
            src = self._editor.toPlainText()
            src_caret = self._editor.textCursor().position()
            self._rendered.setFont(QFont(READING_FONT_FAMILY, self._font_size))
            # Show the view *before* rendering: a hidden widget has no layout
            # geometry yet (first ⌘R), and the render settles the document
            # layout against the viewport width — which must be the real one.
            self._editor.setVisible(False)
            self._rendered.setVisible(True)
            self._rendered.setFocus()
            self._render_markdown(src)
            # Keep the reader's place: map the source caret to the rendered text.
            rendered = self._rendered.document().toPlainText()
            r_pos = md_comments.map_position(src, rendered, src_caret)
            cur = self._rendered.textCursor()
            cur.setPosition(min(r_pos, len(rendered)))
            self._rendered.setTextCursor(cur)
            self._rendered.ensureCursorVisible()
        else:
            if self._preview:   # leave the clean preview before mapping the caret
                self._preview = False
                self._render_markdown(self._editor.toPlainText())
            # Keep the reader's place: map the rendered caret back to the source.
            rendered = self._rendered.document().toPlainText()
            r_caret = self._rendered.textCursor().position()
            src = self._editor.toPlainText()
            s_pos = md_comments.map_position(rendered, src, r_caret)
            self._hide_comment_field()
            self._rendered.setVisible(False)
            self._editor.setVisible(True)
            self._editor.setFocus()
            cur = self._editor.textCursor()
            cur.setPosition(min(s_pos, len(src)))
            self._editor.setTextCursor(cur)
            self._editor.ensureCursorVisible()
        self._update_rendered_focus()   # entering write mode lifts the wash
        self._update_read_focus()       # ...and the focus-reading gradient
        self.update()
        self._refresh_status()
        # Flash last, after the view swap + repaint, so it sits clearly on top.
        self._flash_mode("READ" if self._rendered_mode else "WRITE")

    def _settle_rendered_layout(self):
        """Force the rendered document's layout to finish before we navigate it.

        Two Qt lazy-layout traps meet here. First, the scroll range is only an
        estimate until the deferred relayout runs, so jumping (``G``) or
        restoring the scrollbar too early stops short of the real document
        end. Second — worse — *any* mutation after ``setMarkdown`` (our
        comment formats and sentinel deletions) can corrupt the incremental
        layout's checkpoints: it then permanently believes layout is finished
        while most blocks have no line layouts at all, and the view paints
        blank past the stuck point no matter how it is scrolled. Marking the
        whole document dirty forces a synchronous top-to-bottom relayout that
        resets that state; the event drain (excluding user input so it can't
        re-enter this handler) then lets the view adopt the corrected scroll
        range."""
        doc = self._rendered.document()
        if doc.characterCount() > 1:
            # Reset the (possibly corrupt) incremental state, then force the
            # relayout to complete: documentSize() ensures a *pending* layout
            # finishes synchronously, but without the dirty-marking it is a
            # no-op on the stuck state (which claims to be finished already).
            doc.markContentsDirty(0, doc.characterCount() - 1)
            doc.documentLayout().documentSize()
        QApplication.processEvents(
            QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents
        )

    def _flash_mode(self, text: str):
        """Briefly flash a big, blocky word ('READ' / 'WRITE') in the centre to
        anchor a mode change, then fade it out — so the current state needn't be
        shown permanently (it's also legible from the styling)."""
        if self._mode_flash is None:
            lbl = QLabel(self)
            # Non-interactive: never takes focus or swallows mouse/keyboard, so
            # you can read/type while it fades.
            lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            lbl.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            font = QFont(FONT_FAMILY, 96, QFont.Weight.Bold)
            font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 10)
            lbl.setFont(font)
            lbl.setStyleSheet(
                f"color: rgba({ZEN_TEXT_COLOR.red()}, {ZEN_TEXT_COLOR.green()},"
                f" {ZEN_TEXT_COLOR.blue()}, 200); background: transparent;"
            )
            self._mode_flash = lbl
            self._mode_flash_effect = QGraphicsOpacityEffect(lbl)
            lbl.setGraphicsEffect(self._mode_flash_effect)
        lbl = self._mode_flash
        lbl.setText(text)
        lbl.setGeometry(self.rect())
        self._mode_flash_effect.setOpacity(1.0)
        lbl.show()
        lbl.raise_()
        # Appear instantly, hold at full briefly, then ease out — so it reads as
        # a calm flash rather than a blink. Linear timing keeps the hold exact;
        # the extra key points give the fade a soft tail.
        anim = QPropertyAnimation(self._mode_flash_effect, b"opacity", self)
        anim.setDuration(2000)
        anim.setKeyValueAt(0.0, 1.0)
        anim.setKeyValueAt(0.22, 1.0)    # hold at full briefly
        anim.setKeyValueAt(0.60, 0.5)    # then a long, soft fade
        anim.setKeyValueAt(1.0, 0.0)
        anim.finished.connect(lbl.hide)
        anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
        self._mode_flash_anim = anim   # hold a ref so it isn't GC'd mid-run

    def _apply_doc_base_url(self, doc):
        """Resolve relative resources (images today, links later) against the
        document's own folder instead of the process working directory — so
        ``![](diagram.png)`` renders wherever textli was launched from. A
        no-op for unsaved buffers, which have no folder to resolve against."""
        if self._file_path is not None:
            doc.setBaseUrl(
                QUrl.fromLocalFile(str(self._file_path.parent) + "/"))

    def _render_markdown(self, source: str):
        """Render ``source`` into the read view: comment spans are highlighted
        (bodies hidden, revealed on demand), and suggestion marks are styled as
        track-changes — removed text struck, added text in zen red. The raw
        CriticMarkup never shows.

        Settles the layout before returning, so every caller — mode toggle,
        comment/suggestion commit, preview flip — can restore the scrollbar or
        park the caret against a *correct* scroll range, never the lazy-layout
        estimate (which would clamp the restore and leave the view unable to
        scroll to the real document end)."""
        md, spans = md_comments.to_rendered(source)
        doc = self._rendered.document()
        doc.setMarkdown(md, _MD_FEATURES)
        self._apply_doc_base_url(doc)
        self._style_links(doc)
        # Pad lines are *insertions* — they must land before the mark pass
        # records comment/suggestion offsets. The band/token pass below only
        # applies formats, which shift nothing.
        self._pad_code_blocks(doc)
        self._apply_mark_formats(doc, spans)
        self._style_code_blocks(doc)
        self._style_headings(doc)
        self._style_inline_code(doc)
        self._apply_code_font(doc)
        self._style_reading_rhythm(doc)
        self._style_quotes(doc)
        self._style_tables(doc)
        self._settle_rendered_layout()
        self._update_rendered_focus()
        self._update_read_focus()
        self._refresh_status()   # review counts / progress just changed

    # ── `p` clean preview: the fully-accepted prose, no markup ──

    def _toggle_preview(self):
        """Flip the read view between track-changes and a clean preview of the
        prose with every suggestion accepted and comments unwrapped — a calm
        proof-read of the result, without mutating the source."""
        if not self._rendered_mode:
            return
        self._preview = not self._preview
        sb = self._rendered.verticalScrollBar()
        pos = sb.value()
        src = self._editor.toPlainText()
        if self._preview:
            self._render_preview(src)
        else:
            self._render_markdown(src)
        sb.setValue(pos)
        self._flash_mode("PREVIEW" if self._preview else "READ")

    def _render_preview(self, source: str):
        """Render the accepted 'final' text — no marks, no strikes, no styling.
        Settled like :meth:`_render_markdown`, for the same scroll-restore
        correctness."""
        doc = self._rendered.document()
        doc.setMarkdown(md_comments.accepted(source), _MD_FEATURES)
        self._apply_doc_base_url(doc)
        self._style_links(doc)
        self._pad_code_blocks(doc)
        self._style_code_blocks(doc)
        self._style_headings(doc)
        self._style_inline_code(doc)
        self._apply_code_font(doc)
        self._style_reading_rhythm(doc)
        self._style_quotes(doc)
        self._style_tables(doc)
        self._rendered.set_strikes([])
        self._rendered_comments = []
        self._rendered_suggestions = []
        self._active_comment = -1
        self._settle_rendered_layout()
        self._update_read_focus()
        self._refresh_status()

    # ── Links: zen-styled in the read view, Enter follows in either view ──

    @staticmethod
    def _style_links(doc):
        """Restyle rendered anchors from Qt's palette blue to the zen link
        color. Ranges are collected before formatting — mergeCharFormat
        invalidates the fragment iterator being walked."""
        ranges = []
        block = doc.begin()
        while block.isValid():
            it = block.begin()
            while not it.atEnd():
                frag = it.fragment()
                if frag.charFormat().anchorHref():
                    ranges.append((frag.position(), frag.length()))
                it += 1
            block = block.next()
        fmt = QTextCharFormat()
        fmt.setForeground(ZEN_MD_LINK_COLOR)
        fmt.setFontUnderline(True)
        for pos, length in ranges:
            cur = QTextCursor(doc)
            cur.setPosition(pos)
            cur.setPosition(pos + length, QTextCursor.MoveMode.KeepAnchor)
            cur.mergeCharFormat(fmt)

    def _pad_code_blocks(self, doc):
        """Vertical breathing room inside the code band. Block margins paint
        as paper, not band, so each fence gets a real — but thin, sub-height
        — empty code line at its top and bottom; they inherit the fence
        block format and thus join the band. Runs are processed bottom-up
        because every insert shifts all positions after it; callers must
        invoke this before any pass that records document offsets."""
        runs = []                     # [first_pos, last_pos, last_len]
        prev_fenced = False
        block = doc.begin()
        while block.isValid():
            fenced = block.blockFormat().hasProperty(
                QTextFormat.Property.BlockCodeFence)
            if fenced and not prev_fenced:
                runs.append([block.position(), block.position(),
                             len(block.text())])
            elif fenced:
                runs[-1][1] = block.position()
                runs[-1][2] = len(block.text())
            prev_fenced = fenced
            block = block.next()
        pad = QTextCharFormat()
        pad.setFontPointSize(max(4.0, self._font_size * 0.45))
        for first, last, last_len in reversed(runs):
            cur = QTextCursor(doc)
            cur.setPosition(last + last_len)
            cur.insertBlock()             # empty block below, format kept
            cur.setBlockCharFormat(pad)
            cur = QTextCursor(doc)
            cur.setPosition(first)
            cur.insertBlock()             # splits: the empty half stays above
            cur.movePosition(QTextCursor.MoveOperation.PreviousBlock)
            cur.setBlockCharFormat(pad)

    def _style_code_blocks(self, doc):
        """Make code blocks land as code: every fenced block sits on a
        full-width band in the deeper paper shade (Qt paints no background
        for them at all), and blocks with a language tag get the calm zen
        token scheme via Pygments. Rendered blocks are one QTextBlock per
        code *line*; consecutive lines of one fence are lexed as a single
        unit so multi-line strings and comments hold together."""
        runs = []            # (language, [(doc_pos, line_text), ...])
        current_lang = None
        block = doc.begin()
        while block.isValid():
            bf = block.blockFormat()
            if bf.hasProperty(QTextFormat.Property.BlockCodeFence):
                lang = bf.stringProperty(
                    QTextFormat.Property.BlockCodeLanguage)
                if current_lang is None or lang != current_lang:
                    runs.append((lang, []))
                current_lang = lang
                runs[-1][1].append((block.position(), block.text()))
            else:
                current_lang = None
            block = block.next()
        if not runs:
            self._rendered.set_code_bands([])
            return

        token_fmts = {}
        for cls, color, italic in (
            ("keyword", ZEN_CODE_KEYWORD, False),
            ("string", ZEN_CODE_STRING, False),
            ("comment", ZEN_CODE_COMMENT, True),
            ("number", ZEN_CODE_NUMBER, False),
        ):
            f = QTextCharFormat()
            f.setForeground(color)
            f.setFontItalic(italic)
            token_fmts[cls] = f
        # In-band inset for the code: margins shift a block's *background*
        # along with its text, so the band itself is painted by the view
        # across the full column (set_code_bands below) and the margins
        # here only push the code inward. Em-scaled with a floor: a fixed
        # pixel inset visually shrinks away as the font grows.
        inset = QTextBlockFormat()
        pad_h = max(ZEN_MD_CODE_PAD_H, round(self._font_size * 1.75))
        inset.setLeftMargin(pad_h)
        inset.setRightMargin(pad_h)

        for lang, lines in runs:
            for pos, _text in lines:
                cur = QTextCursor(doc)
                cur.setPosition(pos)
                cur.mergeBlockFormat(inset)
            # Map spans in the joined code back through per-line offsets
            # (a span can cross lines — split it at each boundary).
            joined = "\n".join(text for _pos, text in lines)
            offsets = []                       # (join_start, join_end, doc_pos)
            at = 0
            for pos, text in lines:
                offsets.append((at, at + len(text), pos))
                at += len(text) + 1            # the joining "\n"
            for s, e, cls in md_codeblocks.highlight_spans(joined, lang):
                for js, je, dpos in offsets:
                    lo, hi = max(s, js), min(e, je)
                    if lo >= hi:
                        continue
                    cur = QTextCursor(doc)
                    cur.setPosition(dpos + (lo - js))
                    cur.setPosition(dpos + (hi - js),
                                    QTextCursor.MoveMode.KeepAnchor)
                    cur.mergeCharFormat(token_fmts[cls])
        self._rendered.set_code_bands(
            [(lines[0][0], lines[-1][0]) for _lang, lines in runs])

    def _style_inline_code(self, doc):
        """Chip wash for inline code in prose: Qt marks it fixed-pitch but
        paints no background, so `identifiers` dissolve into body text.
        Fenced blocks are skipped — they have the band."""
        ranges = []
        block = doc.begin()
        while block.isValid():
            if not block.blockFormat().hasProperty(
                    QTextFormat.Property.BlockCodeFence):
                it = block.begin()
                while not it.atEnd():
                    frag = it.fragment()
                    if frag.charFormat().fontFixedPitch():
                        ranges.append((frag.position(), frag.length()))
                    it += 1
            block = block.next()
        fmt = QTextCharFormat()
        fmt.setBackground(ZEN_MD_CODE_BLOCK_BG)
        for pos, length in ranges:
            cur = QTextCursor(doc)
            cur.setPosition(pos)
            cur.setPosition(pos + length, QTextCursor.MoveMode.KeepAnchor)
            cur.mergeCharFormat(fmt)

    def _style_reading_rhythm(self, doc):
        """Long-form breathing room (#33): a proportional line height on prose
        (not code, which reads better tight) and a gap between top-level
        paragraphs, so sustained reading in the proportional face doesn't run
        together. Scales with the font zoom; read view only. Format-only."""
        para_gap = round(self._font_size * 0.6)
        prop = QTextBlockFormat.LineHeightTypes.ProportionalHeight.value
        block = doc.begin()
        while block.isValid():
            bf = block.blockFormat()
            if not bf.hasProperty(QTextFormat.Property.BlockCodeFence):
                fmt = QTextBlockFormat()
                fmt.setLineHeight(ZEN_MD_READING_LINE_HEIGHT, prop)
                cur = QTextCursor(doc)
                cur.setPosition(block.position())
                nxt = block.next()
                # Space plain top-level paragraphs — not headings (they carry
                # their own rhythm), list items, quotes, or table cells, and
                # not right before a heading (its top margin already separates).
                plain = (bf.headingLevel() == 0 and bf.indent() == 0
                         and block.textList() is None
                         and cur.currentTable() is None
                         and bool(block.text().strip()))
                next_heading = (nxt.isValid()
                                and nxt.blockFormat().headingLevel() > 0)
                if plain and not next_heading:
                    fmt.setBottomMargin(para_gap)
                cur.mergeBlockFormat(fmt)
            block = block.next()

    def _apply_code_font(self, doc):
        """Pin code back to the monospace face. Qt flags code fixed-pitch but
        leaves its family at the document default — now the proportional
        reading face (#31) — so inline code and fenced blocks would otherwise
        render in the reading serif. Format-only: shifts no offsets."""
        mono = QTextCharFormat()
        mono.setFontFamilies([FONT_FAMILY])
        block = doc.begin()
        while block.isValid():
            is_fence = block.blockFormat().hasProperty(
                QTextFormat.Property.BlockCodeFence)
            it = block.begin()
            while not it.atEnd():
                frag = it.fragment()
                if is_fence or frag.charFormat().fontFixedPitch():
                    cur = QTextCursor(doc)
                    cur.setPosition(frag.position())
                    cur.setPosition(frag.position() + frag.length(),
                                    QTextCursor.MoveMode.KeepAnchor)
                    cur.mergeCharFormat(mono)
                it += 1
            block = block.next()

    def _style_quotes(self, doc):
        """Blockquotes read as a different voice: hint-gray ink, plus a thin
        vertical bar at the left painted by the view (Qt only indents
        them). Consecutive quote blocks share one bar."""
        ink = QTextCharFormat()
        ink.setForeground(ZEN_HINT_COLOR)
        bars = []
        prev_quoted = False
        block = doc.begin()
        while block.isValid():
            quoted = block.blockFormat().intProperty(
                QTextFormat.Property.BlockQuoteLevel) > 0
            if quoted:
                if not prev_quoted:
                    bars.append([block.position(), block.position()])
                bars[-1][1] = block.position()
                cur = QTextCursor(doc)
                cur.setPosition(block.position())
                cur.setPosition(block.position() + max(0, block.length() - 1),
                                QTextCursor.MoveMode.KeepAnchor)
                cur.mergeCharFormat(ink)
            prev_quoted = quoted
            block = block.next()
        self._rendered.set_quote_bars([tuple(b) for b in bars])

    def _style_tables(self, doc):
        """Give Markdown tables the paper palette: thin collapsed gridlines in
        a warm gray, cell padding for air, and a header row in the code-band
        shade, bold. These are real ``QTextTable`` formats (not view-painting),
        so they survive ``⌘P`` print."""
        for frame in doc.rootFrame().childFrames():
            if not isinstance(frame, QTextTable):
                continue
            tf = frame.format()
            tf.setBorder(1)
            tf.setBorderStyle(
                QTextFrameFormat.BorderStyle.BorderStyle_Solid)
            tf.setBorderBrush(ZEN_MD_TABLE_BORDER)
            tf.setBorderCollapse(True)
            tf.setCellPadding(ZEN_MD_TABLE_PAD)
            tf.setCellSpacing(0)
            # Don't stretch to the column — let the table size to its content.
            tf.setWidth(QTextLength(QTextLength.Type.VariableLength, 0))
            frame.setFormat(tf)
            header = QTextCharFormat()
            header.setFontWeight(QFont.Weight.Bold)
            for col in range(frame.columns()):
                cell = frame.cellAt(0, col)
                cf = cell.format()
                cf.setBackground(ZEN_MD_TABLE_HEADER_BG)
                cell.setFormat(cf)
                cur = cell.firstCursorPosition()
                cur.setPosition(cell.lastCursorPosition().position(),
                                QTextCursor.MoveMode.KeepAnchor)
                cur.mergeCharFormat(header)

    def _update_rendered_focus(self):
        """Keep the read view's focus wash on the section under the caret —
        previous heading through the block before the next one. Sections
        are the reading unit (the write view focuses paragraphs)."""
        if not (self._rendered_mode and self._focus_enabled):
            self._rendered.set_focus_span(None)
            return
        doc = self._rendered.document()
        caret = self._rendered.textCursor().block()
        b = caret
        while b.isValid() and b.blockFormat().headingLevel() == 0:
            b = b.previous()
        start_block = b if b.isValid() else doc.begin()
        e = caret.next()
        while e.isValid() and e.blockFormat().headingLevel() == 0:
            e = e.next()
        end_pos = (e.position() - 1 if e.isValid()
                   else doc.characterCount() - 1)
        self._rendered.set_focus_span((start_block.position(), end_pos))

    # ── `f` focus reading mode: caret-lock + gradient spotlight ──

    def _toggle_read_focus(self):
        """f — focus reading mode (read view, persists). The caret line holds
        at screen centre with the page scrolling under it, and a gradient
        spotlight keeps the current paragraph bright while the rest recedes.
        Supersedes the ⌘. section wash while it's on."""
        self._read_focus = not self._read_focus
        md_settings.app_settings().setValue(
            "zen_md/read_focus", self._read_focus)
        if self._read_focus and self._focus_enabled:
            # Only one focus at a time: f wins, lift the section wash.
            self._focus_enabled = False
            self._highlighter.set_focus_enabled(False)
            self._update_rendered_focus()
        self._update_read_focus()
        self._flash_mode("FOCUS" if self._read_focus else "READ")

    def _update_read_focus(self):
        """Enable the caret-centred spotlight and re-centre the reading line.
        A no-op (lifts the vignette) when the mode or read view is off."""
        on = self._read_focus and self._rendered_mode
        self._rendered.set_focus_reading(on)
        if on:
            self._read_focus_recenter()
            self._rendered.viewport().update()

    def _read_focus_recenter(self):
        """Hold the caret line at the vertical centre of the read view; the
        scrollbar clamps naturally at the document's ends, so the caret travels
        to the top/bottom there instead of centring past the edge."""
        if not (self._read_focus and self._rendered_mode):
            return
        v = self._rendered
        target = int(v.viewport().height() * 0.5)
        delta = v.cursorRect().center().y() - target
        if delta:
            sb = v.verticalScrollBar()
            sb.setValue(sb.value() + delta)

    def _current_rendered_section(self) -> str:
        """The heading of the section under the read-view caret — the whisper
        breadcrumb. Empty before the first heading (the document's preamble
        has no section to name)."""
        b = self._rendered.textCursor().block()
        while b.isValid() and b.blockFormat().headingLevel() == 0:
            b = b.previous()
        return b.text().strip() if b.isValid() else ""

    def _style_headings(self, doc):
        """GitHub-flavored heading rhythm. A heading closes the previous
        section more than it opens its own, so the margin above is clearly
        larger than the one below — per level, scaled with the font zoom.
        h1/h2 additionally get a thin rule, painted by the view."""
        scale = self._font_size / ZEN_MD_FONT_SIZE
        rules = []
        block = doc.begin()
        while block.isValid():
            level = block.blockFormat().headingLevel()
            if level > 0:
                hsize = ZEN_MD_HEADING_SIZES.get(
                    level, ZEN_MD_FONT_SIZE) * scale
                fmt = QTextBlockFormat()
                fmt.setTopMargin(round(hsize * 1.5))
                fmt.setBottomMargin(round(hsize * 0.4))
                cur = QTextCursor(doc)
                cur.setPosition(block.position())
                cur.mergeBlockFormat(fmt)
                if level <= 2:
                    rules.append(block.position())
            block = block.next()
        self._rendered.set_heading_rules(rules)

    def _rendered_anchor_at_caret(self) -> str:
        """The anchor target under the read-view caret ('' if none). The
        caret's charFormat is the *preceding* char's, so the char to the
        right is probed too — a block caret sits on that one."""
        cur = self._rendered.textCursor()
        href = cur.charFormat().anchorHref()
        if not href:
            probe = QTextCursor(cur)
            if probe.movePosition(QTextCursor.MoveOperation.Right):
                href = probe.charFormat().anchorHref()
        return href

    def _follow_link(self, target: str) -> bool:
        """Follow ``target``: a ``#heading-slug`` jumps within the document
        (same slugs the CLI accepts), web/mail targets open externally.
        Returns False for anything else so Enter keeps its other meanings."""
        if target.startswith("#"):
            self._jump_to_anchor(target[1:])
            return True
        if target.split(":", 1)[0].lower() in ("http", "https", "mailto"):
            self._open_external(QUrl(target))
            return True
        return False

    def _open_external(self, url: QUrl):
        """Seam for tests; the real thing hands the URL to the OS."""
        QDesktopServices.openUrl(url)

    # ── Read-view link following: files open in place, the rest is routed ──

    def _follow_rendered_link(self, href: str) -> bool:
        """Read-view Enter on a link. In-document ``#slug`` jumps and web/mail
        targets behave as in the write view; a file target is resolved against
        the current document's folder and routed by type — ``.md`` opens in
        textli (with back-nav), ``.grafli`` shows a stay-tuned notice, anything
        else opens with the system handler."""
        if href.startswith("#"):
            self._jump_to_anchor(href[1:])
            return True
        scheme = QUrl(href).scheme().lower()
        if scheme in ("http", "https", "mailto"):
            self._open_external(QUrl(href))
            return True
        if scheme and scheme != "file":       # ftp, custom schemes → the OS
            self._open_external(QUrl(href))
            return True
        return self._open_local_target(href)

    def _resolve_target(self, href: str) -> tuple[Path | None, str]:
        """Resolve a file href to an absolute path and its ``#fragment`` (both
        may be empty). Relative paths resolve against the current document's
        folder — like image resources — so a folder of docs links naturally."""
        path_part, _, frag = href.partition("#")
        if not path_part or self._file_path is None:
            return None, frag
        url = QUrl(path_part)
        target = Path(url.toLocalFile()) if url.scheme() == "file" \
            else Path(path_part)
        if not target.is_absolute():
            target = self._file_path.parent / target
        return Path(os.path.normpath(str(target))), frag

    def _open_local_target(self, href: str) -> bool:
        """Route a resolved file target by type. Returns True when handled
        (Enter is consumed); False only when there is nothing to resolve."""
        target, frag = self._resolve_target(href)
        if target is None:
            return False
        suffix = target.suffix.lower()
        if suffix == ".grafli":
            self._flash_notice("Opening grafli files is not yet supported "
                               "but will be soon, stay tuned")
            return True
        if suffix in (".md", ".markdown"):
            if not target.exists():
                self._flash_notice(f"not found: {target.name}")
                return True
            self._navigate_to_md(target, frag)
            return True
        # any other resource — hand the local file to the system handler
        if target.exists():
            self._open_external(QUrl.fromLocalFile(str(target)))
        else:
            self._flash_notice(f"not found: {target.name}")
        return True

    def _nav_location(self) -> tuple:
        """Where the reader is now — pushed on the back-stack before a link
        navigates away, so ``gb`` can restore caret and scroll exactly."""
        return (self._file_path,
                self._rendered.textCursor().position(),
                self._rendered.verticalScrollBar().value())

    def _navigate_to_md(self, target: Path, fragment: str = ""):
        """Open another Markdown file in the reading view, remembering where we
        were so ``gb`` walks back. A same-file link with a fragment just jumps;
        a ``#fragment`` on another file lands on that heading."""
        if target == self._file_path:
            if fragment:
                self._jump_to_anchor(fragment)
            return
        self._nav_stack.append(self._nav_location())
        self._switch_file(target)
        if fragment:
            self._jump_to_anchor(fragment)
        self._flash_notice(f"→ {target.name}")

    def _navigate_back(self):
        """gb / Backspace — return to the document a link was followed from,
        exactly where it was left. A no-op (with a whisper) at the root."""
        if not self._nav_stack:
            self._flash_notice("no page to go back to")
            return
        path, pos, scroll = self._nav_stack.pop()
        if path is not None and path != self._file_path:
            self._switch_file(path)
        cur = self._rendered.textCursor()
        cur.setPosition(min(pos, self._rendered.document().characterCount() - 1))
        self._rendered.setTextCursor(cur)
        self._rendered.verticalScrollBar().setValue(scroll)
        if path is not None:
            self._flash_notice(f"← {path.name}")

    def _link_hint(self, href: str) -> str:
        """A short 'where Enter goes' for the whisper: a filename for a file
        link, the host for a web link, the raw ``#slug`` for an in-doc jump."""
        if href.startswith("#"):
            return href
        url = QUrl(href)
        scheme = url.scheme().lower()
        if scheme in ("http", "https"):
            return url.host() or href
        if scheme == "mailto":
            return url.path() or href
        return Path(href.partition("#")[0]).name or href

    def _flash_notice(self, text: str):
        """A brief, quiet toast near the card's bottom — link targets, the
        grafli notice, and back/forward landings. Calmer and smaller than the
        big READ/WRITE mode flash."""
        self._last_notice = text
        if self._notice_flash is None:
            lbl = QLabel(self)
            lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            lbl.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setTextFormat(Qt.TextFormat.PlainText)
            self._notice_flash = lbl
            self._notice_flash_effect = QGraphicsOpacityEffect(lbl)
            lbl.setGraphicsEffect(self._notice_flash_effect)
        lbl = self._notice_flash
        lbl.setFont(QFont(
            FONT_FAMILY, max(ZEN_MD_FONT_SIZE_MIN, self._font_size - 2)))
        lbl.setStyleSheet(
            f"QLabel {{ color: {ZEN_TEXT_COLOR.name()};"
            f" background: #FBF7EC; border: 1px solid #C9A227;"
            f" border-radius: 8px; padding: 6px 14px; }}")
        lbl.setText(text)
        lbl.adjustSize()
        card = self._card_rect()
        lbl.move(int(card.center().x()) - lbl.width() // 2,
                 int(card.bottom()) - lbl.height() - 48)
        lbl.show()
        lbl.raise_()
        self._notice_flash_effect.setOpacity(1.0)
        anim = QPropertyAnimation(self._notice_flash_effect, b"opacity", self)
        anim.setDuration(2200)
        anim.setKeyValueAt(0.0, 1.0)
        anim.setKeyValueAt(0.35, 1.0)     # hold, then fade
        anim.setKeyValueAt(1.0, 0.0)
        anim.finished.connect(lbl.hide)
        anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
        self._notice_flash_anim = anim    # hold a ref so it isn't GC'd mid-run

    # ── `gc` / `gh` jump-list overviews (changes / headings) ──

    @staticmethod
    def _esc_html(t: str) -> str:
        t = t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return t if len(t) <= 42 else t[:41] + "…"

    def _build_changes_list(self):
        """Every mark in document order as ``(start, end, kind, label)`` — comments
        and suggestions, keyed by their current rendered position."""
        rows = []
        for start, end, comment in self._rendered_comments:
            rows.append((start, end, "comment", comment.span or comment.body or ""))
        for s in self._rendered_suggestions:
            m = s.mark
            if m.kind == md_comments.MarkKind.SUBSTITUTE:
                label = f"{m.removed} → {m.added}"
            elif m.kind == md_comments.MarkKind.INSERT:
                label = f"+ {m.added}"
            elif m.kind == md_comments.MarkKind.DELETE:
                label = f"− {m.removed}"
            else:
                label = m.span
            rows.append((s.start, s.end, m.kind, label))
        rows.sort(key=lambda r: r[0])
        return rows

    def _build_headings_list(self):
        """Every heading as ``(start, end, level, text)``, read fresh from the live
        rendered document — so it stays correct after an accepted change shifts or
        rewrites a heading. Ordered as they appear in the document."""
        doc = self._rendered.document()
        rows = []
        block = doc.begin()
        while block.isValid():
            level = block.blockFormat().headingLevel()
            text = block.text().strip()
            if level > 0 and text:
                start = block.position()
                rows.append((start, start + len(block.text()), level, text))
            block = block.next()
        return rows

    def _build_source_headings_list(self):
        """Every ATX heading (``# …``) in the *source* as ``(start, end, level,
        text)``, skipping fenced code blocks — the write-view outline. Positions
        are into the source document so preview/jump land on the ``#`` line."""
        doc = self._editor.document()
        rows = []
        in_fence = False
        block = doc.begin()
        while block.isValid():
            text = block.text()
            stripped = text.lstrip()
            if stripped.startswith("```") or stripped.startswith("~~~"):
                in_fence = not in_fence
            elif not in_fence:
                m = re.match(r"(#{1,6})\s+(.*)", stripped)
                if m and m.group(2).strip():
                    start = block.position()
                    rows.append((start, start + len(text),
                                 len(m.group(1)), m.group(2).strip()))
            block = block.next()
        return rows

    def _build_links_list(self):
        """Every link as ``(start, end, href, text)`` in document order —
        contiguous fragments of one anchor merged into a single row."""
        doc = self._rendered.document()
        rows = []
        block = doc.begin()
        while block.isValid():
            it = block.begin()
            while not it.atEnd():
                frag = it.fragment()
                href = frag.charFormat().anchorHref()
                if href:
                    s = frag.position()
                    e = s + frag.length()
                    if rows and rows[-1][2] == href and rows[-1][1] == s:
                        prev = rows[-1]
                        rows[-1] = (prev[0], e, href, prev[3] + frag.text())
                    else:
                        rows.append((s, e, href, frag.text()))
                it += 1
            block = block.next()
        return rows

    def _open_changes_overview(self):
        """gc — jump-list of every change and comment in the document."""
        marker = {"substitute": "±", "insert": "+", "delete": "−", "comment": "✎"}
        rows = [
            (s, e, f"<span style='color:{ZEN_MD_SUGGEST_ADD.name()}'>"
                   f"{marker.get(k, '?')}</span>&nbsp;{self._esc_html(label)}")
            for (s, e, k, label) in self._build_changes_list()
        ]
        self._open_overview(rows, f"Changes ({len(rows)})", scroll_top=False)

    def _open_headings_overview(self):
        """gh — jump-list of every heading (an outline). Works in both views:
        the reading view reads headings from the rendered document, the write
        view parses them from the source. Rebuilt on each invocation, so a
        heading added or moved since last time is reflected."""
        build = (self._build_headings_list if self._rendered_mode
                 else self._build_source_headings_list)
        rows = [
            (s, e, f"{'&nbsp;' * ((level - 1) * 3)}"
                   f"<span style='color:#A2937A'>{'#' * level}</span>"
                   f"&nbsp;{self._esc_html(text)}")
            for (s, e, level, text) in build()
        ]
        self._open_overview(rows, f"Headings ({len(rows)})", scroll_top=True)

    def _open_links_overview(self):
        """gl — jump-list of every link, to step between them; unlike gh/gc,
        Enter *follows* the picked link (files open in place, the rest routed).
        Rebuilt from the live document each time."""
        rows, targets = [], []
        for s, e, href, text in self._build_links_list():
            hint = self._link_hint(href)
            rows.append((s, e,
                f"<span style='color:{ZEN_MD_LINK_COLOR.name()}'>"
                f"{self._esc_html(text or hint)}</span>&nbsp;"
                f"<span style='color:{ZEN_HINT_COLOR.name()}'>"
                f"→ {self._esc_html(hint)}</span>"))
            targets.append(href)
        self._open_overview(rows, f"Links ({len(rows)})",
                            scroll_top=False, targets=targets)

    def _open_overview(self, rows, title: str, *, scroll_top: bool,
                       targets=None):
        """Show the jump-list overlay for ``rows`` (each ``(start, end, html)``),
        selecting the row nearest the caret. j/k moves *and previews* (the view
        follows the selection live), Enter keeps the spot, Esc returns to where
        the reader was, a digit jumps directly. A no-op for an empty list. When
        ``targets`` is given (one href per row), Enter follows the link instead
        of just landing on it — that's the `gl` links overview."""
        if not rows:
            return
        # The overview drives whichever view is live — the rendered reader or
        # the source editor (gh works in both).
        self._overview_view = (self._rendered if self._rendered_mode
                               else self._editor)
        view = self._overview_view
        self._overview_rows = rows
        self._overview_title = title
        self._overview_scroll_top = scroll_top
        self._overview_targets = targets
        # Where the reader came from — Esc promises to put this back exactly.
        self._overview_origin = (view.verticalScrollBar().value(),
                                 view.textCursor().position())
        pos = view.textCursor().position()
        # Select where the reader *is*: the row whose own span holds the caret,
        # else the row whose section the caret is in (the last row starting at
        # or before it) — so `gh` opens on the current heading, not the first.
        sel = next((i for i, (s, e, _h) in enumerate(rows) if s <= pos <= e),
                   None)
        if sel is None:
            sel = max((i for i, (s, _e, _h) in enumerate(rows) if s <= pos),
                      default=0)
        self._overview_sel = sel
        if self._overview_overlay is None:
            lbl = QLabel(self)
            lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            lbl.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            lbl.setTextFormat(Qt.TextFormat.RichText)
            self._overview_overlay = lbl
        self._render_overview()
        self._refresh_status()

    def _render_overview(self):
        """(Re)paint the overview overlay with the current selection highlighted."""
        lbl = self._overview_overlay
        if lbl is None:
            return
        lines = []
        for i, (_s, _e, inner) in enumerate(self._overview_rows):
            bg = (f"background:{ZEN_MD_COMMENT_HL.name()};"
                  if i == self._overview_sel else "")
            lines.append(f"<tr><td style='{bg}padding:2px 10px'>{i + 1}"
                         f"&nbsp;&nbsp;{inner}</td></tr>")
        header = (f"<div style='padding:2px 10px;color:{ZEN_TEXT_COLOR.name()};"
                  f"font-weight:bold'>{self._overview_title}</div>")
        html = (f"<div style='font-family:\"{FONT_FAMILY}\";"
                f"font-size:{max(ZEN_MD_FONT_SIZE_MIN, self._font_size - 3)}pt;"
                f"color:{ZEN_TEXT_COLOR.name()}'>{header}"
                f"<table cellspacing='0'>{''.join(lines)}</table></div>")
        lbl.setText(html)
        lbl.setStyleSheet(
            "QLabel {"
            " background: #FBF7EC; border: 1px solid #C9A227;"
            " border-radius: 8px; padding: 8px; }")
        lbl.adjustSize()
        vp = self._overview_view or self._rendered
        lbl.move(vp.x() + max(16, vp.width() - lbl.width() - 24), vp.y() + 24)
        lbl.show()
        lbl.raise_()

    def _handle_overview_key(self, event: QKeyEvent) -> bool:
        """Keys while an overview is open: j/k (or arrows) move the selection
        and preview it live in the view, Enter keeps the previewed spot, a
        digit jumps directly, Esc / q / g returns to the origin."""
        key = event.key()
        n = len(self._overview_rows)
        if key in (Qt.Key.Key_J, Qt.Key.Key_Down):
            self._overview_sel = min(n - 1, self._overview_sel + 1)
            self._render_overview()
            self._preview_overview_row(self._overview_sel)
            return True
        if key in (Qt.Key.Key_K, Qt.Key.Key_Up):
            self._overview_sel = max(0, self._overview_sel - 1)
            self._render_overview()
            self._preview_overview_row(self._overview_sel)
            return True
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._jump_to_overview_row(self._overview_sel)
            return True
        if Qt.Key.Key_1 <= key <= Qt.Key.Key_9:
            idx = key - Qt.Key.Key_1
            if idx < n:
                self._jump_to_overview_row(idx)
            return True
        if key in (Qt.Key.Key_Escape, Qt.Key.Key_Q, Qt.Key.Key_G):
            self._cancel_overview()
            return True
        return True   # swallow everything else while the overview is up

    def _preview_overview_row(self, idx: int):
        """Bring row ``idx``'s span into the active view without closing the
        overview — the live preview behind j/k. Headings scroll to the top of
        the view (outline jump); changes just scroll into view, leaving the
        caret on the mark so a/x/Enter act on it."""
        if not (0 <= idx < len(self._overview_rows)):
            return
        start, end, _inner = self._overview_rows[idx]
        view = self._overview_view or self._rendered
        cur = view.textCursor()
        cur.setPosition(start)
        cur.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
        view.setTextCursor(cur)
        if self._overview_scroll_top and view is self._rendered:
            doc = view.document()
            y = doc.documentLayout().blockBoundingRect(doc.findBlock(start)).y()
            view.verticalScrollBar().setValue(int(y))
        elif self._overview_scroll_top:
            # The write view (a QPlainTextEdit) scrolls in line units, not
            # pixels — bring the heading into view, then nudge its line to the
            # top so it reads like an outline jump.
            view.ensureCursorVisible()
            line_h = max(1, view.fontMetrics().lineSpacing())
            sb = view.verticalScrollBar()
            sb.setValue(sb.value() + view.cursorRect().top() // line_h)
        else:
            view.ensureCursorVisible()

    def _jump_to_overview_row(self, idx: int):
        """Commit row ``idx``: preview it (caret on the span, scrolled per the
        list's style) and close the overview there. For the `gl` links overview
        (``_overview_targets`` set) the picked link is then followed."""
        targets = self._overview_targets
        if 0 <= idx < len(self._overview_rows):
            self._preview_overview_row(idx)
        self._close_overview()
        if targets and 0 <= idx < len(targets):
            self._follow_rendered_link(targets[idx])

    def _cancel_overview(self):
        """Esc — put the reader back exactly where the overview found them
        (caret and scroll), then close."""
        scroll, pos = getattr(self, "_overview_origin",
                              (None, None))
        view = self._overview_view or self._rendered
        if pos is not None:
            cur = view.textCursor()
            cur.setPosition(pos)
            view.setTextCursor(cur)
            view.verticalScrollBar().setValue(scroll)
        self._close_overview()

    def _close_overview(self):
        """Hide the jump-list overlay (idempotent)."""
        if getattr(self, "_overview_overlay", None) is not None:
            self._overview_overlay.hide()
            self._overview_overlay = None
        view = self._overview_view or getattr(self, "_rendered", None)
        if view is not None:
            view.setFocus()
        self._refresh_status()

    def _format_for_span(self, span, comment_idx: int,
                         suggest_idx: int) -> QTextCharFormat:
        """The char format for one rendered span by its role. Comments wear the
        highlight (tagged with their comment index); a removed span keeps the body
        ink and regular weight — the strong strike line is painted over it by
        :class:`_ReadingView`; an added span is body text in a subtle zen red,
        which stands out on its own and works equally for inline edits and block
        rewrites. Suggestion spans are tagged with their suggestion index."""
        fmt = QTextCharFormat()
        if span.role == "comment":
            fmt.setBackground(QBrush(ZEN_MD_COMMENT_HL))
            fmt.setProperty(_COMMENT_IDX_PROP, comment_idx)
            return fmt
        fmt.setProperty(_SUGGEST_IDX_PROP, suggest_idx)
        if span.role == "removed":
            fmt.setProperty(_SUGGEST_ROLE_PROP, _ROLE_REMOVED)   # painted strike
        elif span.role == "added":
            fmt.setProperty(_SUGGEST_ROLE_PROP, _ROLE_ADDED)
            fmt.setForeground(QBrush(ZEN_MD_SUGGEST_ADD))
        return fmt

    def _apply_mark_formats(self, doc, spans):
        """Find each sentinel-wrapped span in the rendered document, paint its
        role's format over it, tag comment spans with their comment index, and
        delete the sentinel markers. Builds ``self._rendered_comments`` (the
        rendered-range → source-``Comment`` map the reveal/navigate loop uses).

        Located via ``QTextDocument.find`` (not raw string indexing) so the
        positions stay correct even when the render inserts position-bearing
        objects (images, rules) ahead of a span.
        """
        self._rendered_comments = []
        self._rendered_suggestions = []
        if not spans:
            return
        # Collect each span's sentinel bounds, in document order.
        bounds = []
        pos = 0
        for _ in spans:
            start = doc.find(md_comments.SENTINEL_START, pos)
            if start.isNull():
                break
            end = doc.find(md_comments.SENTINEL_END, start.selectionEnd())
            if end.isNull():
                break
            bounds.append((start.selectionStart(), start.selectionEnd(),
                           end.selectionStart(), end.selectionEnd()))
            pos = end.selectionEnd()
        # Comment spans index into a comment-only list (kept as Comment objects
        # so the reveal/edit code stays typed against Comment). Suggestion spans
        # index into a suggestion-only list of source Marks; a substitution's two
        # spans share one index so they recover as a single reviewable unit.
        comments = []
        comment_idx = []
        sugg_marks = []
        sugg_ord = {}            # mark.full_start -> suggestion index
        suggest_idx = []
        for span in spans:
            if span.role == "comment":
                comment_idx.append(len(comments))
                comments.append(md_comments.as_comment(span.mark))
                suggest_idx.append(-1)
            else:
                fs = span.mark.full_start
                if fs not in sugg_ord:
                    sugg_ord[fs] = len(sugg_marks)
                    sugg_marks.append(span.mark)
                comment_idx.append(-1)
                suggest_idx.append(sugg_ord[fs])
        # Apply last-to-first so deletions don't shift not-yet-processed offsets.
        edit = QTextCursor(doc)
        edit.beginEditBlock()
        for i in range(len(bounds) - 1, -1, -1):
            s0, s1, e0, e1 = bounds[i]
            fmt = self._format_for_span(spans[i], comment_idx[i], suggest_idx[i])
            edit.setPosition(s1)
            edit.setPosition(e0, QTextCursor.MoveMode.KeepAnchor)
            edit.mergeCharFormat(fmt)               # style the span text
            edit.setPosition(e0)
            edit.setPosition(e1, QTextCursor.MoveMode.KeepAnchor)
            edit.removeSelectedText()               # drop END sentinel
            edit.setPosition(s0)
            edit.setPosition(s1, QTextCursor.MoveMode.KeepAnchor)
            edit.removeSelectedText()               # drop START sentinel
        edit.endEditBlock()
        self._rendered_comments = self._collect_rendered_comments(doc, comments)
        self._rendered_suggestions = self._collect_rendered_suggestions(
            doc, sugg_marks)
        self._rendered.set_strikes(
            [s.removed for s in self._rendered_suggestions if s.removed])

    def _collect_rendered_suggestions(self, doc, marks):
        """Recover each suggestion as an :class:`RSuggestion` — its overall range
        plus the separate removed/added sub-ranges — from the tagged fragments. A
        substitution's struck-old and red-new fragments share the same
        index (folded into one unit) but carry distinct roles (kept apart so the
        animator can fade one and settle the other)."""
        overall: dict[int, tuple[int, int]] = {}
        by_role: dict[tuple[int, int], tuple[int, int]] = {}
        block = doc.begin()
        while block.isValid():
            it = block.begin()
            while not it.atEnd():
                frag = it.fragment()
                cf = frag.charFormat()
                if cf.hasProperty(_SUGGEST_IDX_PROP):
                    idx = cf.intProperty(_SUGGEST_IDX_PROP)
                    role = cf.intProperty(_SUGGEST_ROLE_PROP)
                    a = frag.position()
                    b = a + frag.length()
                    lo, hi = overall.get(idx, (a, b))
                    overall[idx] = (min(lo, a), max(hi, b))
                    rlo, rhi = by_role.get((idx, role), (a, b))
                    by_role[(idx, role)] = (min(rlo, a), max(rhi, b))
                it += 1
            block = block.next()
        return [
            RSuggestion(overall[i][0], overall[i][1], marks[i],
                        by_role.get((i, _ROLE_REMOVED)),
                        by_role.get((i, _ROLE_ADDED)))
            for i in sorted(overall)
        ]

    def _collect_rendered_comments(self, doc, comments):
        """Walk the rendered document's fragments and, for each comment index
        tagged on a span, recover its [start, end) range — robust to the span
        being split into several fragments by inline formatting."""
        bounds: dict[int, tuple[int, int]] = {}
        block = doc.begin()
        while block.isValid():
            it = block.begin()
            while not it.atEnd():
                frag = it.fragment()
                cf = frag.charFormat()
                if cf.hasProperty(_COMMENT_IDX_PROP):
                    idx = cf.intProperty(_COMMENT_IDX_PROP)
                    a = frag.position()
                    b = a + frag.length()
                    lo, hi = bounds.get(idx, (a, b))
                    bounds[idx] = (min(lo, a), max(hi, b))
                it += 1
            block = block.next()
        return [(bounds[i][0], bounds[i][1], comments[i])
                for i in sorted(bounds)]

    # ── Modal card geometry ──

    def _card_rect(self) -> QRectF:
        """Card width hugs the text column (the adjustable content width +
        padding); height takes most of the window. Centered. In full-width mode
        (⌘↵) the card grows to nearly fill the window.
        """
        max_w = max(self.width() - 80, 320)
        if getattr(self, "_full_width", False):
            w = max_w
            h = max(self.height() - 40, 320)
        else:
            content_w = getattr(self, "_content_width", ZEN_MD_MAX_WIDTH)
            desired_w = content_w + 2 * ZEN_MD_CARD_INNER_PAD_H
            w = min(desired_w, max_w)
            h = min(self.height() * ZEN_MD_CARD_H_RATIO, self.height() - 60)
        x = (self.width() - w) / 2
        y = (self.height() - h) / 2
        return QRectF(x, y, w, h)

    def _apply_card_margins(self, layout):
        """Anchor layout margins inside the card with comfortable padding."""
        card = self._card_rect()
        h_outside = (self.width() - card.width()) / 2
        v_outside = (self.height() - card.height()) / 2
        layout.setContentsMargins(
            int(h_outside + ZEN_MD_CARD_INNER_PAD_H),
            int(v_outside + ZEN_MD_CARD_INNER_PAD_V),
            int(h_outside + ZEN_MD_CARD_INNER_PAD_H),
            int(v_outside + ZEN_MD_CARD_INNER_PAD_V),
        )

    def _canvas_rect_in_self(self) -> QRect | None:
        """Return the canvas widget's geometry in this widget's coord space,
        or None if no canvas was supplied / it isn't visible.
        """
        if not self._canvas or not self._canvas.isVisible():
            return None
        top_left = self.mapFromGlobal(self._canvas.mapToGlobal(QPoint(0, 0)))
        return QRect(top_left, self._canvas.size())

    # ── Paint ──

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Dim wash — chrome gets the full wash; canvas gets a gentler dim
        # so the canvas stays readable but visibly steps back. Both fade
        # together with the widget's opacity effect.
        canvas = self._canvas_rect_in_self()
        full = self.rect()
        if canvas is None or not full.intersects(canvas):
            p.fillRect(full, ZEN_MD_DIM_COLOR)
        else:
            clipped = canvas.intersected(full)
            # Four chrome strips — full dim.
            if clipped.top() > full.top():
                p.fillRect(
                    QRect(full.left(), full.top(),
                          full.width(), clipped.top() - full.top()),
                    ZEN_MD_DIM_COLOR,
                )
            if clipped.bottom() < full.bottom():
                p.fillRect(
                    QRect(full.left(), clipped.bottom() + 1,
                          full.width(), full.bottom() - clipped.bottom()),
                    ZEN_MD_DIM_COLOR,
                )
            if clipped.left() > full.left():
                p.fillRect(
                    QRect(full.left(), clipped.top(),
                          clipped.left() - full.left(), clipped.height()),
                    ZEN_MD_DIM_COLOR,
                )
            if clipped.right() < full.right():
                p.fillRect(
                    QRect(clipped.right() + 1, clipped.top(),
                          full.right() - clipped.right(), clipped.height()),
                    ZEN_MD_DIM_COLOR,
                )
            # Canvas — gentler dim, animates with the editor's opacity.
            p.fillRect(clipped, ZEN_MD_CANVAS_DIM_COLOR)

        # Drop shadow, then the solid writing card on top.
        card = self._card_rect()
        self._paint_card_shadow(p, card)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(ZEN_MD_BG))
        p.drawRoundedRect(card, ZEN_MD_CARD_RADIUS, ZEN_MD_CARD_RADIUS)

        p.end()

    def _paint_card_shadow(self, painter: QPainter, card: QRectF):
        """Soft drop shadow around the card. Painted before the card; the
        opaque card covers the inside, so only the spillover at the edges
        shows. Layers stack outward with decreasing alpha, biased downward
        for gravity.
        """
        drop = 6  # downward bias
        painter.setPen(Qt.PenStyle.NoPen)
        for i in range(1, 14):
            alpha = 20 - i * 2
            if alpha <= 0:
                break
            painter.setBrush(QBrush(QColor(0, 0, 0, alpha)))
            shadow = QRectF(
                card.left() - i,
                card.top() - i + drop // 2,
                card.width() + 2 * i,
                card.height() + 2 * i + drop // 2,
            )
            painter.drawRoundedRect(
                shadow, ZEN_MD_CARD_RADIUS + i, ZEN_MD_CARD_RADIUS + i,
            )


    # ── Resize tracking ──

    def resizeEvent(self, event):
        super().resizeEvent(event)
        layout = self.layout()
        if layout:
            self._apply_card_margins(layout)
        self._refresh_status()   # the card corner moved with the window

    def _parent_resized(self):
        parent = self.parentWidget()
        if parent:
            self.resize(parent.size())

    def showEvent(self, event):
        super().showEvent(event)
        parent = self.parentWidget()
        if parent:
            parent.installEventFilter(self)
            self.resize(parent.size())

    def hideEvent(self, event):
        parent = self.parentWidget()
        if parent:
            parent.removeEventFilter(self)
        # The editor only hides on its way out — the moment to remember where
        # the reader left the file.
        self._save_position()
        super().hideEvent(event)

    def eventFilter(self, obj, event):
        # Bail if we're mid-construction or mid-teardown — pumping the event
        # loop (e.g. the read-view layout settle) can deliver events while
        # these child refs aren't established or have been cleared.
        if getattr(self, "_editor", None) is None:
            return False
        if obj == self.parentWidget() and event.type() == QEvent.Type.Resize:
            self.resize(obj.size())
            return False
        if (getattr(self, "_comment_field", None) is not None
                and obj is self._comment_field
                and event.type() == QEvent.Type.KeyPress):
            return self._handle_comment_field_key(event)
        if (obj in (self._editor, self._rendered)
                and event.type() == QEvent.Type.KeyPress):
            return self._handle_key(event)
        return False

    def _handle_comment_field_key(self, event: QKeyEvent) -> bool:
        """Keys while the inline comment editor is open: Enter saves and returns
        to undisturbed reading; ⇧Enter inserts a line break; Esc cancels."""
        key = event.key()
        shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if shift:
                self._comment_field.insertPlainText("\n")   # ⇧↵ — line break
            else:
                self._commit_comment_field()                # ↵ — save & back
            return True
        if key == Qt.Key.Key_Escape:
            self._cancel_comment_field()                    # Esc — discard
            return True
        return False

    def _cancel_comment_field(self):
        """Discard the open comment editor without writing changes (abandons a
        new comment; leaves an edited one untouched)."""
        self._authoring_span = None
        self._authoring_suggestion = False
        self._hide_comment_field()

    # ── Key handling ──

    def _handle_key(self, event: QKeyEvent) -> bool:
        """Central key router. Returns True if event is consumed."""
        # Jump overlay consumes all keys while active
        if self._jump and self._jump.is_active():
            self._jump.keyPressEvent(event)
            return True

        # F1 — the editor's own help (works in either view). The editor owns and
        # shows this, so it's the same whether embedded in a host app or run
        # standalone via `textli`.
        if event.key() == Qt.Key.Key_F1:
            self._show_help()
            return True

        # Ctrl+R — toggle rendered read-only view <-> source editor
        if (event.key() == Qt.Key.Key_R
                and event.modifiers() & _CTRL_MOD):
            self._toggle_rendered()
            return True

        # Ctrl+Enter — toggle full-window width (works in either view)
        if (event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
                and event.modifiers() & _CTRL_MOD):
            self._toggle_full_width()
            return True

        # Ctrl+Shift+→/←/↓ — widen / narrow / reset the content column.
        # Arrow keys (not +/-) so the binding is layout-independent and doesn't
        # collide with the Ctrl +/-/0 font zoom below. Works in either view.
        if ((event.modifiers() & _CTRL_MOD)
                and (event.modifiers() & Qt.KeyboardModifier.ShiftModifier)):
            if event.key() == Qt.Key.Key_Right:
                self._change_width(+1)
                return True
            if event.key() == Qt.Key.Key_Left:
                self._change_width(-1)
                return True
            if event.key() == Qt.Key.Key_Down:
                self._change_width(0)
                return True

        # Ctrl+. — toggle section-focus dim (works in either view)
        if (event.key() == Qt.Key.Key_Period
                and event.modifiers() & _CTRL_MOD):
            self._toggle_focus()
            return True

        # Ctrl+T — toggle typewriter scrolling (a write-view behaviour, but
        # togglable from either view; the preference persists)
        if (event.key() == Qt.Key.Key_T
                and event.modifiers() & _CTRL_MOD):
            self._toggle_typewriter()
            return True

        # Ctrl+P — print (works in either view)
        if (event.key() == Qt.Key.Key_P
                and event.modifiers() & _CTRL_MOD):
            self._print()
            return True

        # Ctrl +/-/0 — font size zoom (works in either view; the read view
        # re-renders inside _change_font_size)
        if event.modifiers() & _CTRL_MOD:
            if event.key() in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
                self._change_font_size(+1)
                return True
            if event.key() == Qt.Key.Key_Minus:
                self._change_font_size(-1)
                return True
            if event.key() == Qt.Key.Key_0:
                self._change_font_size(0)
                return True

        # Rendered view: vim-style navigation; Esc saves & closes.
        if self._rendered_mode:
            return self._handle_rendered_key(event)

        # A jump-list overview (gh) can be open over the write view too — it
        # captures every key while up, same as in the reading view.
        if self._overview_overlay is not None:
            return self._handle_overview_key(event)

        # Ctrl+J — activate word jump
        if (event.key() == Qt.Key.Key_J
                and event.modifiers() & _CTRL_MOD):
            self._activate_jump()
            return True

        # `/` — in-document search; n/N — step hits. NORMAL mode only (INSERT
        # must type these), and never mid-sequence (g…, d…) so vim's pending
        # keys keep their meaning.
        if (self._vim.mode == VimMode.NORMAL and not self._vim.has_pending
                and not (event.modifiers() & _CTRL_MOD)):
            if event.text() == "/":
                self._open_search()
                return True
            if event.text() == "n":
                self._search_step(+1)
                return True
            if event.text() == "N":
                self._search_step(-1)
                return True

        # Enter (NORMAL) — follow the link under the caret: [text](url),
        # <autolink> or a bare URL. INSERT keeps Enter as a newline, and with
        # no link under the caret vim consumes it as before (a no-op).
        if (event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
                and self._vim.mode == VimMode.NORMAL
                and not self._vim.has_pending):
            cur = self._editor.textCursor()
            target = md_links.link_at(cur.block().text(), cur.positionInBlock())
            if target and self._follow_link(target):
                return True

        # Route through vim handler
        return self._vim.handle_key(event)

    def _handle_rendered_key(self, event: QKeyEvent) -> bool:
        """Vim-style read view. Motions move a caret (h/l/j/k, w/b/e, 0/$, gg/G,
        Ctrl-d/u half-page, Ctrl-f/b/Space page). `v` enters visual mode so the
        same motions extend a selection; `c` comments the selection, `s` suggests
        an alternative for it (empty = delete; no selection = insert at the caret).
        `]c`/`[c` step between comments, `]s`/`[s` between suggestions; on a
        suggestion `a`/`x` accept/reject and advance (⇧A/⇧X = all). Enter reveals/edits a
        comment, ⇧D deletes it. Esc leaves visual mode, or — when not selecting —
        saves & closes (⇧Esc cancels)."""
        key = event.key()
        mods = event.modifiers()
        shift = bool(mods & Qt.KeyboardModifier.ShiftModifier)
        ctrl = bool(mods & _CTRL_MOD)
        MO = QTextCursor.MoveOperation

        # While a jump-list overview is open it captures every key.
        if self._overview_overlay is not None:
            return self._handle_overview_key(event)

        # p — toggle the clean preview (fully-accepted prose, no markup).
        if key == Qt.Key.Key_P and not ctrl:
            self._toggle_preview()
            return True

        # f — toggle focus reading mode (caret-lock + gradient spotlight).
        if key == Qt.Key.Key_F and not ctrl and not shift:
            self._toggle_read_focus()
            return True

        # ]c / [c — step to the next / previous comment (two-key, vim diff-style).
        if self._rendered_pending_bracket:
            pending = self._rendered_pending_bracket
            self._rendered_pending_bracket = ""
            if key == Qt.Key.Key_C:
                self._goto_comment(1 if pending == "]" else -1)
                return True
            if key == Qt.Key.Key_S:
                self._goto_suggestion(1 if pending == "]" else -1)
                return True
        if key == Qt.Key.Key_BracketRight and not shift:
            self._rendered_pending_bracket = "]"
            return True
        if key == Qt.Key.Key_BracketLeft and not shift:
            self._rendered_pending_bracket = "["
            return True

        # `gg` — top; `gc` — changes overview; `gh` — headings; `go` — open file.
        if key == Qt.Key.Key_G and not shift:
            if getattr(self, "_rendered_pending_g", False):
                self._rendered_pending_g = False
                self._caret_move(MO.Start)
            else:
                self._rendered_pending_g = True
            return True
        if (getattr(self, "_rendered_pending_g", False)
                and not ctrl and not shift
                and key in (Qt.Key.Key_C, Qt.Key.Key_H, Qt.Key.Key_O,
                            Qt.Key.Key_L, Qt.Key.Key_B)):
            self._rendered_pending_g = False
            if key == Qt.Key.Key_C:
                self._open_changes_overview()
            elif key == Qt.Key.Key_H:
                self._open_headings_overview()
            elif key == Qt.Key.Key_L:
                self._open_links_overview()
            elif key == Qt.Key.Key_B:
                self._navigate_back()
            else:
                self._open_file_dialog()
            return True
        self._rendered_pending_g = False

        # Backspace — browser-style back through followed .md links.
        if key == Qt.Key.Key_Backspace and not ctrl:
            self._navigate_back()
            return True

        # `/` — in-document search; n/N — step through hits.
        if event.text() == "/":
            self._open_search()
            return True
        if key == Qt.Key.Key_N and not ctrl:
            self._search_step(-1 if shift else +1)
            return True

        # v — toggle visual (selection) mode. c — comment the selection.
        if key == Qt.Key.Key_V and not ctrl:
            self._set_visual(not self._visual)
            return True
        # Authoring is disabled in the clean preview (the rendered text is the
        # accepted prose — mapping a span back to the marked-up source is unsafe).
        if key == Qt.Key.Key_C and not ctrl and not shift and not self._preview:
            self._comment_selection()
            return True
        # s — suggest an alternative for the selection (type it; empty = delete);
        # with no selection, propose an insertion at the caret.
        if key == Qt.Key.Key_S and not ctrl and not shift and not self._preview:
            self._suggest_selection()
            return True

        # a / x — accept / reject the suggestion under the caret and advance to the
        # next decision (scrolling to it). ⇧A / ⇧X — accept / reject all at once.
        if key == Qt.Key.Key_A and not ctrl:
            self._review_suggestion(accept=True, every=shift)
            return True
        if key == Qt.Key.Key_X and not ctrl:
            self._review_suggestion(accept=False, every=shift)
            return True

        # Enter — follow the link under the caret; with none there, reveal/
        # edit the active comment inline. ⇧D — delete it.
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not ctrl:
            href = self._rendered_anchor_at_caret()
            if href and self._follow_rendered_link(href):
                return True
            self._reveal_active_comment()
            return True
        if key == Qt.Key.Key_D and shift:
            self._delete_active_comment()
            return True

        # Esc — leave visual mode if selecting; otherwise save & close.
        if key == Qt.Key.Key_Escape:
            if self._visual:
                self._set_visual(False)
            else:
                self._close_cancel() if shift else self._close_save()
            return True

        # Caret motions — extend the selection when in visual mode.
        if key == Qt.Key.Key_G and shift:                 # G — bottom
            self._caret_move(MO.End)
            return True
        if key in (Qt.Key.Key_H, Qt.Key.Key_Left):
            self._caret_move(MO.Left)
            return True
        if key in (Qt.Key.Key_L, Qt.Key.Key_Right):
            self._caret_move(MO.Right)
            return True
        if key in (Qt.Key.Key_J, Qt.Key.Key_Down):
            self._caret_move(MO.Down)
            return True
        if key in (Qt.Key.Key_K, Qt.Key.Key_Up):
            self._caret_move(MO.Up)
            return True
        if key == Qt.Key.Key_W and not ctrl:
            self._caret_move(MO.NextWord)
            return True
        if key == Qt.Key.Key_B and not ctrl:
            self._caret_move(MO.PreviousWord)
            return True
        if key == Qt.Key.Key_E and not ctrl:
            self._caret_move(MO.EndOfWord)
            return True
        if key == Qt.Key.Key_0 and not ctrl:
            self._caret_move(MO.StartOfLine)
            return True
        if key == Qt.Key.Key_Dollar:
            self._caret_move(MO.EndOfLine)
            return True
        if ctrl and key == Qt.Key.Key_D:
            self._caret_move(MO.Down, self._page_lines(0.5))
            return True
        if ctrl and key == Qt.Key.Key_U:
            self._caret_move(MO.Up, self._page_lines(0.5))
            return True
        if key in (Qt.Key.Key_Space, Qt.Key.Key_PageDown) or (
                ctrl and key == Qt.Key.Key_F):
            self._caret_move(MO.Down, self._page_lines(1.0))
            return True
        if key == Qt.Key.Key_PageUp or (ctrl and key == Qt.Key.Key_B):
            self._caret_move(MO.Up, self._page_lines(1.0))
            return True
        return False

    def _caret_move(self, op, count: int = 1):
        """Move the read-view caret by ``op`` × ``count``; in visual mode keep
        the anchor so the selection extends."""
        mode = (QTextCursor.MoveMode.KeepAnchor if self._visual
                else QTextCursor.MoveMode.MoveAnchor)
        cur = self._rendered.textCursor()
        cur.movePosition(op, mode, count)
        self._rendered.setTextCursor(cur)
        self._rendered.ensureCursorVisible()

    def _page_lines(self, frac: float) -> int:
        """Number of text lines in ``frac`` of the viewport (for page motions)."""
        line_h = max(1, int(QFontMetricsF(self._rendered.font()).height()))
        return max(1, int(self._rendered.viewport().height() * frac / line_h))

    def _set_visual(self, on: bool):
        """Enter/leave visual mode. Entering anchors the selection at the caret;
        leaving collapses any selection back to undisturbed reading."""
        self._visual = on
        cur = self._rendered.textCursor()
        if on:
            cur.setPosition(cur.position())   # collapse → anchor at caret
        else:
            cur.clearSelection()
        self._rendered.setTextCursor(cur)
        self._refresh_status()

    def _comment_selection(self):
        """c — comment the visual selection; or, with no selection, reveal/edit
        the comment the caret is sitting on (so you can jump straight to editing
        an existing comment without `]c` or visual mode)."""
        cur = self._rendered.textCursor()
        if cur.hasSelection():
            if not cur.selectedText().strip():
                self._set_visual(False)     # nothing but whitespace — ignore
                return
            r0, r1 = cur.selectionStart(), cur.selectionEnd()
            self._set_visual(False)
            self._begin_comment_for_span(r0, r1)
            return
        self._reveal_active_comment()   # no selection → reveal comment under caret

    def _comment_at_position(self, pos: int) -> int:
        """Index of the rendered comment whose span contains ``pos``, else -1."""
        for i, (start, end, _c) in enumerate(self._rendered_comments):
            if start <= pos <= end:
                return i
        return -1

    # ── Read-view comment interaction ──

    def _goto_comment(self, direction: int):
        """Step the active comment forward (+1) or back (-1), wrapping, and
        scroll it into view. From no active comment, land on the first / last."""
        comments = self._rendered_comments
        if not comments:
            return
        n = len(comments)
        if self._active_comment < 0:
            idx = 0 if direction > 0 else n - 1
        else:
            idx = (self._active_comment + direction) % n
        self._set_active_comment(idx)

    def _set_active_comment(self, idx: int):
        """Mark comment ``idx`` active: select its span (the native selection
        marks it atop the amber highlight) and scroll it into view."""
        self._active_comment = idx
        start, end, _comment = self._rendered_comments[idx]
        cur = self._rendered.textCursor()
        cur.setPosition(start)
        cur.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
        self._rendered.setTextCursor(cur)
        self._rendered.ensureCursorVisible()

    def _reveal_active_comment(self):
        """Show the inline editable field for the comment **under the caret**
        (Enter). If the caret isn't on a comment, do nothing — never open an
        unrelated comment that merely happens to be on the same screen."""
        idx = self._comment_at_position(self._rendered.textCursor().position())
        if idx < 0:
            return
        self._active_comment = idx
        _start, end, comment = self._rendered_comments[idx]
        self._show_comment_field(end, comment.body)

    def _show_comment_field(self, end_pos: int, body: str):
        """Place the inline comment editor just below the active span. It reads
        as a handwritten margin note — Caveat in dark red ink on the same tint
        a commented span wears in the text — and starts small, growing with the
        text up to a max (then scrolling), so an empty note isn't a big box."""
        field = self._comment_field
        if field is None:
            field = QPlainTextEdit(self._rendered.viewport())
            field.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
            field.setVerticalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            field.setHorizontalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            field.installEventFilter(self)
            field.textChanged.connect(self._autosize_comment_field)
            self._comment_field = field
        # Font restyled each open so a font zoom since last time is reflected.
        field.setFont(QFont(
            COMMENT_FONT_FAMILY, self._font_size + ZEN_MD_COMMENT_SIZE_BOOST))
        field.setStyleSheet(
            f"QPlainTextEdit {{"
            f" background: {ZEN_MD_COMMENT_NOTE_BG.name()};"
            f" color: {ZEN_MD_COMMENT_INK.name()};"
            f" border: 1px solid {ZEN_MD_COMMENT_INK.name()};"
            f" border-radius: 6px;"
            f" padding: 6px 10px;"
            f" selection-background-color: #E7C6A0;"
            f"}}"
        )
        self._comment_anchor_pos = end_pos
        field.setFixedWidth(min(ZEN_MD_COMMENT_WIDTH,
                               self._rendered.viewport().width() - 24))
        field.setPlainText(body)
        field.show()
        self._autosize_comment_field()   # sets height + places the field
        field.setFocus()
        field.moveCursor(QTextCursor.MoveOperation.End)

    def _autosize_comment_field(self):
        """Grow the note to fit its text — from a small start up to a max, then
        let it scroll — and keep it anchored below the span, on screen.

        QPlainTextEdit reports its document height in *lines*, not pixels, so
        the wrapped pixel height is measured with a throwaway QTextDocument at
        the same font and wrap width (deterministic, no dependence on the
        widget's lazy layout)."""
        field = self._comment_field
        if field is None:
            return
        vw = field.viewport().width()
        if vw <= 0:                       # not laid out yet — estimate from width
            vw = field.width() - 28
        probe = QTextDocument()
        probe.setDefaultFont(field.font())
        probe.setDocumentMargin(field.document().documentMargin())
        probe.setTextWidth(vw)
        probe.setPlainText(field.toPlainText())
        chrome = 18   # 6px padding top+bottom, 1px border, a little slack
        wanted = probe.size().height() + chrome
        h = int(min(ZEN_MD_COMMENT_MAX_HEIGHT,
                    max(ZEN_MD_COMMENT_MIN_HEIGHT, wanted)))
        field.setFixedHeight(h)
        vp = self._rendered.viewport()
        cur = self._rendered.textCursor()
        cur.setPosition(min(self._comment_anchor_pos,
                            self._rendered.document().characterCount() - 1))
        rect = self._rendered.cursorRect(cur)
        w = field.width()
        x = max(8, min(rect.left(), vp.width() - w - 8))
        y = min(rect.bottom() + 4, vp.height() - h - 8)
        field.move(x, max(8, y))

    def _hide_comment_field(self):
        if self._comment_field is not None:
            self._comment_field.hide()
        self._rendered.setFocus()

    def _commit_comment_field(self):
        """Commit the field. For a new comment (authoring), wrap the picked span;
        for an existing one, write the edited body back. An emptied body abandons
        a new comment / deletes an edited one. Then re-render, back to reading."""
        if self._comment_field is None:
            return
        raw = self._comment_field.toPlainText()
        body = raw.strip()
        if self._authoring_span is not None:
            if self._authoring_suggestion:
                self._commit_new_suggestion(raw)   # keep spaces — they're content
            else:
                self._commit_new_comment(body)
            return
        if self._active_comment < 0:
            return
        _s, _e, comment = self._rendered_comments[self._active_comment]
        src = self._editor.toPlainText()
        if body:
            src = md_comments.set_body(src, comment, body)
        else:
            src = md_comments.remove(src, comment)   # emptied → delete
        idx = self._active_comment
        self._hide_comment_field()
        self._apply_source_change(
            src,
            lambda: (min(idx, len(self._rendered_comments) - 1)
                     if self._rendered_comments else None),
        )

    # ── Authoring: comment the visual selection ──

    def _begin_comment_for_span(self, r0: int, r1: int):
        """Map the rendered span back to source; if it maps, open an empty field
        to type the comment. An unmappable selection (e.g. no words) is a quiet
        no-op — it never yanks you out of the reading view."""
        rendered = self._rendered.document().toPlainText()
        src = self._editor.toPlainText()
        mapped = md_comments.map_rendered_span(rendered, src, r0, r1)
        if mapped is None:
            return
        s0, s1 = mapped
        # Keep the {== / ==} markers out of code: if a boundary maps inside an
        # inline `code` span (e.g. a word that was in backticks), snap it to the
        # code edge so the comment stays parseable.
        s0, s1 = md_comments.snap_out_of_code(src, s0, s1)
        # The span still can't include CriticMarkup delimiters (e.g. it crossed a
        # code example like `{== ==}`) — wrapping would nest markers and render as
        # literal text. Refuse quietly.
        if md_comments.contains_markup(src[s0:s1]):
            return
        # Overlap-aware (no nesting): inside an existing comment → edit it;
        # straddling one → refuse quietly rather than corrupt the markup.
        overlap = md_comments.classify_overlap(src, s0, s1)
        if overlap is not None:
            kind, idx = overlap
            if kind == "inside" and idx < len(self._rendered_comments):
                self._set_active_comment(idx)
                self._reveal_active_comment()
            return
        self._authoring_span = (s0, s1, rendered[r0:r1])
        cur = self._rendered.textCursor()
        cur.setPosition(r0)
        cur.setPosition(r1, QTextCursor.MoveMode.KeepAnchor)
        self._rendered.setTextCursor(cur)        # show what will be commented
        self._show_comment_field(r1, "")

    def _commit_new_comment(self, body: str):
        """Wrap the authored span in CriticMarkup and re-render, staying in the
        reading view with the new comment active. An empty body abandons it."""
        s0, _s1, _sel = self._authoring_span
        self._authoring_span = None
        self._hide_comment_field()
        if not body:
            return                               # abandoned — no comment created
        new_src = md_comments.wrap(self._editor.toPlainText(), s0, _s1, body)
        self._apply_source_change(
            new_src, lambda: self._rendered_index_for_source_start(s0)
        )

    def _rendered_index_for_source_start(self, full_start: int):
        """Index of the rendered comment whose source construct begins at
        ``full_start`` — i.e. the one just wrapped at that offset."""
        for i, (_s, _e, comment) in enumerate(self._rendered_comments):
            if comment.full_start == full_start:
                return i
        return None

    # ── Authoring: suggest an alternative for the selection ──

    def _suggest_selection(self):
        """s — propose a change. With a visual selection, open the inline field to
        type its replacement (an empty field commits a deletion); with no
        selection, propose an insertion at the caret."""
        cur = self._rendered.textCursor()
        if cur.hasSelection():
            if not cur.selectedText().strip():
                self._set_visual(False)     # whitespace-only — ignore
                return
            r0, r1 = cur.selectionStart(), cur.selectionEnd()
            self._set_visual(False)
            self._begin_suggestion_for_span(r0, r1)
            return
        pos = cur.position()
        self._begin_suggestion_for_span(pos, pos)   # insertion at the caret

    def _begin_suggestion_for_span(self, r0: int, r1: int):
        """Map the rendered span back to source and open an empty field for the
        replacement text. A zero-width span authors an insertion; a real span a
        substitution (or a deletion if the field is left empty). Unmappable spans,
        spans crossing existing markup, or spans overlapping another mark are quiet
        no-ops — they never yank you out of the reading view."""
        rendered = self._rendered.document().toPlainText()
        src = self._editor.toPlainText()
        if r0 == r1:
            s0 = s1 = md_comments.map_position(rendered, src, r0)
        else:
            mapped = md_comments.map_rendered_span(rendered, src, r0, r1)
            if mapped is None:
                return
            s0, s1 = md_comments.snap_out_of_code(src, *mapped)
            if md_comments.contains_markup(src[s0:s1]):
                return
        if md_comments.overlaps_mark(src, s0, s1):
            return
        self._authoring_span = (s0, s1, rendered[r0:r1])
        self._authoring_suggestion = True
        cur = self._rendered.textCursor()
        cur.setPosition(r0)
        cur.setPosition(r1, QTextCursor.MoveMode.KeepAnchor)
        self._rendered.setTextCursor(cur)        # show what will be changed
        self._show_comment_field(r1, "")

    def _commit_new_suggestion(self, body: str):
        """Wrap the authored span as a CriticMarkup suggestion and re-render,
        staying in the reading view with the new suggestion under the caret. The
        gesture branches on the span and the (unstripped) body: a caret authors an
        insertion (empty body abandons it, surrounding spaces are kept); a real
        selection substitutes — or, when the body is blank, deletes it."""
        s0, s1, _sel = self._authoring_span
        self._authoring_span = None
        self._authoring_suggestion = False
        self._hide_comment_field()
        if s0 == s1:
            if not body.strip():
                return                           # insert-nothing — abandoned
            replacement = body                   # keep leading/trailing spaces
        else:
            replacement = "" if not body.strip() else body   # blank → deletion
        new_src = md_comments.wrap_suggestion(
            self._editor.toPlainText(), s0, s1, replacement)
        self._apply_source_change_pos(
            new_src, lambda: self._rendered_suggestion_pos_for_source(s0)
        )

    def _rendered_suggestion_pos_for_source(self, full_start: int):
        """Rendered start position of the suggestion whose source mark begins at
        ``full_start`` — i.e. the one just wrapped there."""
        for s in self._rendered_suggestions:
            if s.mark.full_start == full_start:
                return s.start
        return None

    def _delete_active_comment(self):
        """⇧D — unwrap the active comment (highlight + body gone), re-render."""
        if not (0 <= self._active_comment < len(self._rendered_comments)):
            return
        _s, _e, comment = self._rendered_comments[self._active_comment]
        idx = self._active_comment
        src = md_comments.remove(self._editor.toPlainText(), comment)
        self._hide_comment_field()
        self._apply_source_change(
            src,
            lambda: (min(idx, len(self._rendered_comments) - 1)
                     if self._rendered_comments else None),
        )

    def _set_source_text(self, src: str):
        """Replace the source buffer (fires heading layout + autosave). Done
        through a cursor edit (not ``setPlainText``) so it lands on the editor's
        undo stack as a single step — accept/reject and comment edits are then
        revertible with ⌘Z in the write view."""
        cur = self._editor.textCursor()
        cur.beginEditBlock()
        cur.select(QTextCursor.SelectionType.Document)
        cur.insertText(src)
        cur.endEditBlock()

    def _apply_source_change(self, src: str, resolve_idx=None):
        """Update the source + re-render the read view **keeping the reader's
        scroll position**, then activate the comment ``resolve_idx()`` returns
        (resolved after the re-render). Adding/editing/deleting a comment barely
        changes the rendered text, so the view stays put instead of snapping to
        the top — ``ensureCursorVisible`` isn't reliable right after
        ``setMarkdown`` (layout isn't ready), so we restore the scrollbar."""
        sb = self._rendered.verticalScrollBar()
        pos = sb.value()
        self._set_source_text(src)
        self._render_markdown(src)
        sb.setValue(pos)   # restore scroll first, so visibility is computed right
        idx = resolve_idx() if resolve_idx is not None else None
        caret = self._rendered.textCursor()
        if idx is not None and 0 <= idx < len(self._rendered_comments):
            # Park the caret on the comment just touched (it's already in view, so
            # no scroll jump) — j/k then continue from there, not the page top.
            self._active_comment = idx
            caret.setPosition(self._rendered_comments[idx][0])
        else:
            # No comment to anchor to (e.g. the last one was deleted) — fall back
            # to the top of the visible area rather than the document end.
            self._active_comment = -1
            caret = self._rendered.cursorForPosition(QPoint(0, 0))
        self._rendered.setTextCursor(caret)
        sb.setValue(pos)   # setTextCursor may nudge scroll; reassert the position

    def _apply_source_change_pos(self, src: str, pos_resolver=None,
                                 *, scroll_to_caret: bool = False):
        """Like :meth:`_apply_source_change` but parks the caret at an absolute
        rendered position (``pos_resolver()``), used by suggestion review. When
        ``scroll_to_caret`` the view scrolls to reveal the caret (used when review
        advances to the next decision); otherwise the reader's scroll is kept
        (used when review stays at the current spot)."""
        sb = self._rendered.verticalScrollBar()
        pos = sb.value()
        self._set_source_text(src)
        self._render_markdown(src)
        sb.setValue(pos)
        target = pos_resolver() if pos_resolver is not None else None
        caret = self._rendered.textCursor()
        if target is not None:
            n = len(self._rendered.document().toPlainText())
            caret.setPosition(max(0, min(target, n)))
        else:
            caret = self._rendered.cursorForPosition(QPoint(0, 0))
        self._rendered.setTextCursor(caret)
        if scroll_to_caret:
            self._rendered.ensureCursorVisible()
        else:
            sb.setValue(pos)

    # ── Read-view suggestion review (track-changes) ──

    def _suggestion_at_position(self, pos: int) -> int:
        """Index of the rendered suggestion whose range contains ``pos``, else -1."""
        for i, s in enumerate(self._rendered_suggestions):
            if s.start <= pos <= s.end:
                return i
        return -1

    def _goto_suggestion(self, direction: int):
        """]s / [s — step to the next / previous suggestion and select it. From a
        caret that isn't on one, land on the nearest in the given direction."""
        sugg = self._rendered_suggestions
        if not sugg:
            return
        n = len(sugg)
        pos = self._rendered.textCursor().position()
        here = self._suggestion_at_position(pos)
        if here >= 0:
            idx = (here + direction) % n
        elif direction > 0:
            idx = next((i for i, s in enumerate(sugg) if s.start > pos), 0)
        else:
            idx = next((i for i in range(n - 1, -1, -1) if sugg[i].start < pos), n - 1)
        s = sugg[idx]
        cur = self._rendered.textCursor()
        cur.setPosition(s.start)
        cur.setPosition(s.end, QTextCursor.MoveMode.KeepAnchor)
        self._rendered.setTextCursor(cur)
        self._rendered.ensureCursorVisible()

    def _review_suggestion(self, accept: bool, every: bool = False):
        """a / x (and ⇧A / ⇧X). Accept or reject the suggestion under the caret —
        the accepted/rejected text is applied to the source, the view re-renders,
        and the caret advances onto the next suggestion (scrolling to reveal it) so
        review is a rhythm. A single accept/reject plays the zen animation first
        (fade what leaves, settle what stays); ⇧ variants resolve every suggestion
        at once, instantly."""
        # Settle any in-flight animation so we compute against a stable document.
        self._suggest_animator.finish()
        src = self._editor.toPlainText()
        if every:
            new_src = (md_comments.accept_all(src) if accept
                       else md_comments.reject_all(src))
            self._apply_source_change_pos(new_src, lambda: 0)
            return
        idx = self._suggestion_at_position(self._rendered.textCursor().position())
        if idx < 0:
            return
        s = self._rendered_suggestions[idx]
        new_src = (md_comments.accept(src, s.mark) if accept
                   else md_comments.reject(src, s.mark))

        # After re-render the resolved mark is gone, so the suggestion that was
        # next has slid into ``idx`` — park there (and scroll to it) to advance.
        def resolve_pos():
            if not self._rendered_suggestions:
                return None
            return self._rendered_suggestions[
                min(idx, len(self._rendered_suggestions) - 1)].start

        def apply():
            self._apply_source_change_pos(
                new_src, resolve_pos, scroll_to_caret=True)

        if self._suggest_animate:
            self._suggest_animator.run(
                accept=accept, removed=s.removed, added=s.added, on_finish=apply)
        else:
            apply()

    def _change_font_size(self, delta: int):
        """Change font size. delta=0 resets to default. Applies to whichever
        view is active: the read view must re-render, not just change font —
        heading sizes are baked into char formats at setMarkdown time."""
        if delta == 0:
            new_size = ZEN_MD_FONT_SIZE
        else:
            new_size = max(
                ZEN_MD_FONT_SIZE_MIN,
                min(ZEN_MD_FONT_SIZE_MAX, self._font_size + delta),
            )
        if new_size == self._font_size:
            return
        self._font_size = new_size
        self._editor.setFont(QFont(FONT_FAMILY, self._font_size))
        self._highlighter.set_base_size(self._font_size)
        # Gutter width is char-based; re-apply after font change.
        self._apply_heading_layout()
        if self._rendered_mode:
            self._rendered.setFont(QFont(READING_FONT_FAMILY, self._font_size))
            pos = self._rendered.textCursor().position()
            src = self._editor.toPlainText()
            if self._preview:
                self._render_preview(src)
            else:
                self._render_markdown(src)
            # Same text, new metrics — the position is still valid; keep the
            # reader anchored on it rather than snapping to the top.
            cur = self._rendered.textCursor()
            cur.setPosition(
                min(pos, self._rendered.document().characterCount() - 1))
            self._rendered.setTextCursor(cur)
            self._rendered.ensureCursorVisible()
        self._refresh_status()
        md_settings.app_settings().setValue(
            "zen_md/font_size", self._font_size
        )

    def _change_width(self, delta: int):
        """Step the editor's content-column width. delta=0 resets to default;
        +1/-1 widen/narrow by one step. Stepping exits full-width mode so the
        change is visible, and the preference persists across sessions."""
        if delta == 0:
            new_w = ZEN_MD_MAX_WIDTH
        else:
            new_w = max(
                ZEN_MD_MAX_WIDTH_MIN,
                min(ZEN_MD_MAX_WIDTH_MAX,
                    self._content_width + delta * ZEN_MD_WIDTH_STEP),
            )
        if new_w == self._content_width and not self._full_width:
            return
        self._content_width = new_w
        self._full_width = False
        layout = self.layout()
        if layout:
            self._apply_card_margins(layout)
        self._apply_heading_layout()
        self.update()
        self._refresh_status()
        md_settings.app_settings().setValue(
            "zen_md/content_width", self._content_width
        )

    def _activate_jump(self):
        if self._jump is None:
            self._jump = WordJumpOverlay(self._editor, self)
        self._jump.activate()

    # ── Public API ──

    def editor(self) -> QPlainTextEdit:
        return self._editor

    def set_hint(self, text: str):
        self._hint.setText(text)
