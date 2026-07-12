"""Keyboard-only in-document search overlay for the zen editor (``/``).

An input line over a live hit list — the same card language as the ``go``
open-file dialog, over the *current document*: every line the query
fuzzy-matches, in document order (see :mod:`textli.search`), the match region
emphasized when it's contiguous.

Keys: type to filter — ``C-n``/``C-p`` (or arrows) move the selection (the
host scrolls the view to preview it), ``Enter`` jumps to the selected hit,
``Esc`` cancels (the host restores the original position).

Self-contained: the host passes a text provider in and receives hit ranges
via signals; it never touches the document itself.
"""

from __future__ import annotations

import html
from typing import Callable

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QFont, QKeyEvent
from PySide6.QtWidgets import QLabel, QLineEdit, QVBoxLayout, QWidget

from textli import search
from textli.constants import (
    FONT_FAMILY,
    ZEN_HINT_COLOR,
    ZEN_MD_COMMENT_HL,
    ZEN_MD_FONT_SIZE_MIN,
    ZEN_MD_SUGGEST_ADD,
    ZEN_TEXT_COLOR,
    _CTRL_MOD,
)

_MAX_VISIBLE = 12       # hit rows shown at once (window slides)
_LINE_MAX = 72          # longer hit lines are tail-truncated for display


class SearchOverlay(QWidget):
    """The ``/`` search card. ``selection_changed(start, end)`` fires whenever
    the selected hit changes (live preview); ``accepted(start, end)`` on Enter;
    ``cancelled()`` on Esc. Offsets address the searched text."""

    selection_changed = Signal(int, int)
    accepted = Signal(int, int)
    cancelled = Signal()
    cleared = Signal()      # query emptied / no hits — host drops highlights
    replace_opened = Signal()        # replace field revealed — host previews literals
    replace_one = Signal(str, str)   # (query, replacement) — replace current, advance
    replace_all = Signal(str, str)   # (query, replacement) — replace every literal match

    def __init__(self, parent: QWidget, text_provider: Callable[[], str],
                 font_size: int, allow_replace: bool = False):
        super().__init__(parent)
        self._text_provider = text_provider
        self._hits: list[search.Hit] = []
        self._sel = 0
        self._font_size = max(ZEN_MD_FONT_SIZE_MIN, font_size - 3)
        # Replace is offered only where the text is editable — the write view.
        # The reading view is a read-only render, so `/` stays find-only there.
        self._allow_replace = allow_replace

        # One card: the container itself paints the background/border (a plain
        # QWidget needs WA_StyledBackground for that), and the rule is scoped
        # to the container by object name so it can't cascade onto the
        # children as their own bordered boxes.
        self.setObjectName("zenCard")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            "QWidget#zenCard { background: #FBF7EC;"
            " border: 1px solid #C9A227; border-radius: 8px; }")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(4)

        title = QLabel(self)
        title.setTextFormat(Qt.TextFormat.RichText)
        hint = (f"&nbsp;&nbsp;<span style='color:{ZEN_HINT_COLOR.name()};"
                f"font-weight:normal'>⇥ replace</span>" if allow_replace else "")
        title.setStyleSheet(
            f"QLabel {{ color: {ZEN_TEXT_COLOR.name()}; font-weight: bold; }}")
        title.setFont(QFont(FONT_FAMILY, self._font_size))
        title.setText(f"Search{hint}")
        lay.addWidget(title)

        _field_css = (
            f"QLineEdit {{ background: #FFFFFF; color: {ZEN_TEXT_COLOR.name()};"
            f" border: 1px solid {ZEN_HINT_COLOR.name()}; border-radius: 4px;"
            f" padding: 3px 6px; }}")

        self._input = QLineEdit(self)
        self._input.setFont(QFont(FONT_FAMILY, self._font_size))
        self._input.setStyleSheet(_field_css)
        self._input.textChanged.connect(self._refresh)
        self._input.installEventFilter(self)
        lay.addWidget(self._input)

        # Replace field + key hint — hidden until Tab reveals them (write view
        # only). A hidden widget takes no layout space, so plain search is
        # unchanged until you ask to replace.
        self._replace = QLineEdit(self)
        self._replace.setFont(QFont(FONT_FAMILY, self._font_size))
        self._replace.setPlaceholderText("replace with…")
        self._replace.setStyleSheet(_field_css)
        self._replace.installEventFilter(self)
        self._replace.hide()
        lay.addWidget(self._replace)

        self._replace_hint = QLabel(
            "↵ replace · ⌃↵ all · ⇥ back · Esc cancel", self)
        self._replace_hint.setStyleSheet(
            f"QLabel {{ color: {ZEN_HINT_COLOR.name()}; }}")
        self._replace_hint.setFont(QFont(
            FONT_FAMILY, max(ZEN_MD_FONT_SIZE_MIN, self._font_size - 1)))
        self._replace_hint.hide()
        lay.addWidget(self._replace_hint)

        self._list = QLabel(self)
        self._list.setTextFormat(Qt.TextFormat.RichText)
        self._list.setFont(QFont(FONT_FAMILY, self._font_size))
        lay.addWidget(self._list)

    # ── Host API ──

    @property
    def query(self) -> str:
        return self._input.text()

    @property
    def hits(self) -> list[search.Hit]:
        return self._hits

    @property
    def replacement(self) -> str:
        return self._replace.text()

    def refresh_hits(self):
        """Re-run the query against the (now edited) text so the list and count
        reflect what a replace left behind."""
        self._refresh(self._input.text())

    def open(self):
        """Show the card; the best-ranked hit is selected as the query is
        typed."""
        self._region = "top"
        self._refresh("")
        self._place()
        self.show()
        self.raise_()
        self._input.setFocus()

    @property
    def region(self) -> str:
        """Where the card sits: ``"top"`` (default) or ``"bottom"`` — the host
        flips it when it would cover the current hit (see
        ``_ensure_hit_visible``)."""
        return getattr(self, "_region", "top")

    def place_region(self, region: str):
        """Move the card to the top or bottom edge, keeping it there across
        re-renders."""
        self._region = region
        self._place()

    def _place(self):
        p = self.parentWidget()
        self.adjustSize()
        w = max(self.width(), min(640, int(p.width() * 0.7)))
        self.resize(w, self.height())
        y = (int(p.height() * 0.12) if self.region == "top"
             else max(24, p.height() - self.height() - 40))
        self.move((p.width() - w) // 2, y)

    # ── Matching ──

    def _refresh(self, text: str):
        # Ranked for the list (best first, exact above fuzzy) — n/N later
        # walk the document spatially, independent of this order.
        self._hits = search.rank(search.find_hits(self._text_provider(), text))
        self._sel = 0
        self._render()
        self._emit_selection()

    def _emit_selection(self):
        if self._hits:
            h = self._hits[self._sel]
            self.selection_changed.emit(h.start, h.end)
        else:
            # Empty query means *no search* — stale highlights must go.
            self.cleared.emit()

    def _render(self):
        hits = self._hits
        start = max(0, min(self._sel - _MAX_VISIBLE // 2,
                           len(hits) - _MAX_VISIBLE))
        window = hits[start:start + _MAX_VISIBLE]
        q = self._input.text()
        lines = []
        for i, h in enumerate(window, start=start):
            bg = (f"background:{ZEN_MD_COMMENT_HL.name()};"
                  if i == self._sel else "")
            lines.append(
                f"<tr><td style='{bg}padding:1px 8px;"
                f"color:{ZEN_HINT_COLOR.name()}'>{h.line_no + 1}"
                f"&nbsp;&nbsp;<span style='color:{ZEN_TEXT_COLOR.name()}'>"
                f"{self._hit_html(h)}</span></td></tr>")
        more = ""
        if len(hits) > start + _MAX_VISIBLE:
            more = (f"<div style='padding:1px 8px;"
                    f"color:{ZEN_HINT_COLOR.name()}'>…</div>")
        empty = ("" if hits or not q.strip() else
                 f"<div style='padding:1px 8px;color:{ZEN_HINT_COLOR.name()}'>"
                 f"no matches</div>")
        count = (f"<div style='padding:1px 8px;color:{ZEN_HINT_COLOR.name()}'>"
                 f"{len(hits)} hit{'s' if len(hits) != 1 else ''}</div>"
                 if hits else "")
        self._list.setText(
            f"<table cellspacing='0'>{''.join(lines)}</table>{more}{empty}{count}")
        self._place()

    @staticmethod
    def _hit_html(h: search.Hit) -> str:
        """The hit line for the list: truncated around the first match span,
        every span (the phrase, or each matched word) emphasized."""
        line = h.text
        first = h.spans[0][0] if h.spans else 0
        # keep the (first) match visible even on a long line
        lead = max(0, min(first - 20, len(line) - _LINE_MAX))
        vis = line[lead:lead + _LINE_MAX]
        out, last = [], 0
        for a, b in h.spans:
            a, b = a - lead, min(b - lead, len(vis))
            if b <= 0 or a >= len(vis) or a < last:
                continue
            a = max(a, 0)
            out.append(html.escape(vis[last:a]))
            out.append(f"<b><span style='color:{ZEN_MD_SUGGEST_ADD.name()}'>"
                       f"{html.escape(vis[a:b])}</span></b>")
            last = b
        out.append(html.escape(vis[last:]))
        pre = "…" if lead else ""
        post = "…" if lead + _LINE_MAX < len(line) else ""
        return f"{pre}{''.join(out)}{post}"

    # ── Keys ──

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.KeyPress:
            if obj is self._input and self._handle_key(event):
                return True
            if obj is self._replace and self._handle_replace_key(event):
                return True
        return super().eventFilter(obj, event)

    def _handle_key(self, event: QKeyEvent) -> bool:
        key = event.key()
        ctrl = bool(event.modifiers() & _CTRL_MOD)
        if key == Qt.Key.Key_Escape:
            self.cancelled.emit()
            return True
        if key == Qt.Key.Key_Down or (ctrl and key == Qt.Key.Key_N):
            self._move_sel(+1)
            return True
        if key == Qt.Key.Key_Up or (ctrl and key == Qt.Key.Key_P):
            self._move_sel(-1)
            return True
        if key in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab) and self._allow_replace:
            self._open_replace()
            return True
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self._hits:
                h = self._hits[self._sel]
                self.accepted.emit(h.start, h.end)
            else:
                self.cancelled.emit()
            return True
        return False

    def _open_replace(self):
        """Reveal the replace field and move there, keeping the query. The host
        previews the literal matches replace will act on."""
        self._replace.show()
        self._replace_hint.show()
        self._place()
        self._replace.setFocus()
        self.replace_opened.emit()

    def _handle_replace_key(self, event: QKeyEvent) -> bool:
        key = event.key()
        ctrl = bool(event.modifiers() & _CTRL_MOD)
        if key == Qt.Key.Key_Escape:
            self.cancelled.emit()
            return True
        if key in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
            self._input.setFocus()               # back to the search field
            return True
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if ctrl:
                self.replace_all.emit(self.query, self.replacement)
            else:
                self.replace_one.emit(self.query, self.replacement)
            return True
        return False

    def _move_sel(self, step: int):
        if self._hits:
            self._sel = max(0, min(len(self._hits) - 1, self._sel + step))
            self._render()
            self._emit_selection()
