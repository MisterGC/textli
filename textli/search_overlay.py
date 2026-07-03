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

    def __init__(self, parent: QWidget, text_provider: Callable[[], str],
                 font_size: int):
        super().__init__(parent)
        self._text_provider = text_provider
        self._anchor = 0
        self._hits: list[search.Hit] = []
        self._sel = 0
        self._font_size = max(ZEN_MD_FONT_SIZE_MIN, font_size - 3)

        self.setStyleSheet(
            "QWidget { background: #FBF7EC; border: 1px solid #C9A227;"
            " border-radius: 8px; }")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(4)

        title = QLabel("Search", self)
        title.setStyleSheet(
            f"QLabel {{ color: {ZEN_TEXT_COLOR.name()}; font-weight: bold;"
            f" border: none; }}")
        title.setFont(QFont(FONT_FAMILY, self._font_size))
        lay.addWidget(title)

        self._input = QLineEdit(self)
        self._input.setFont(QFont(FONT_FAMILY, self._font_size))
        self._input.setStyleSheet(
            f"QLineEdit {{ background: #FFFFFF; color: {ZEN_TEXT_COLOR.name()};"
            f" border: 1px solid {ZEN_HINT_COLOR.name()}; border-radius: 4px;"
            f" padding: 3px 6px; }}")
        self._input.textChanged.connect(self._refresh)
        self._input.installEventFilter(self)
        lay.addWidget(self._input)

        self._list = QLabel(self)
        self._list.setTextFormat(Qt.TextFormat.RichText)
        self._list.setFont(QFont(FONT_FAMILY, self._font_size))
        self._list.setStyleSheet("QLabel { border: none; }")
        lay.addWidget(self._list)

    # ── Host API ──

    @property
    def query(self) -> str:
        return self._input.text()

    @property
    def hits(self) -> list[search.Hit]:
        return self._hits

    def open(self, anchor_pos: int):
        """Show the card; the selection anchors to the first hit at or after
        ``anchor_pos`` (where the reader is) as the query is typed."""
        self._anchor = anchor_pos
        self._refresh("")
        self._place()
        self.show()
        self.raise_()
        self._input.setFocus()

    def _place(self):
        p = self.parentWidget()
        self.adjustSize()
        w = max(self.width(), min(640, int(p.width() * 0.7)))
        self.resize(w, self.height())
        self.move((p.width() - w) // 2, int(p.height() * 0.12))

    # ── Matching ──

    def _refresh(self, text: str):
        self._hits = search.find_hits(self._text_provider(), text)
        self._sel = search.initial_index(self._hits, self._anchor)
        self._render()
        self._emit_selection()

    def _emit_selection(self):
        if self._hits:
            h = self._hits[self._sel]
            self.selection_changed.emit(h.start, h.end)

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
                f"{self._hit_html(q, h.text)}</span></td></tr>")
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
    def _hit_html(query: str, line: str) -> str:
        """The hit line for the list: tail-truncated around the match, the
        contiguous match region emphasized (a scattered fuzzy hit shows the
        plain line)."""
        rng = search.match_range(query, line)
        if rng is None:
            return html.escape(line[:_LINE_MAX])
        a, b = rng
        # keep the match visible even on a long line
        lead = max(0, min(a - 20, len(line) - _LINE_MAX))
        vis = line[lead:lead + _LINE_MAX]
        a, b = a - lead, min(b - lead, len(vis))
        pre = ("…" if lead else "") + html.escape(vis[:a])
        mid = html.escape(vis[a:b])
        post = html.escape(vis[b:]) + ("…" if lead + _LINE_MAX < len(line) else "")
        return (f"{pre}<b><span style='color:{ZEN_MD_SUGGEST_ADD.name()}'>"
                f"{mid}</span></b>{post}")

    # ── Keys ──

    def eventFilter(self, obj, event):
        if obj is self._input and event.type() == QEvent.Type.KeyPress:
            if self._handle_key(event):
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
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self._hits:
                h = self._hits[self._sel]
                self.accepted.emit(h.start, h.end)
            else:
                self.cancelled.emit()
            return True
        return False

    def _move_sel(self, step: int):
        if self._hits:
            self._sel = max(0, min(len(self._hits) - 1, self._sel + step))
            self._render()
            self._emit_selection()
