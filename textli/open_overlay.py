"""Keyboard-only open-file overlay for the zen editor (``go``).

An input line over a ranked suggestion list, styled like the ``gc``/``gh``
jump-list cards. History entries match fuzzily over their full path; the
filesystem completes per segment (see :mod:`textli.openfile` for the split).

Keys: type to filter — ``C-n``/``C-p`` (or arrows) move the selection,
``Tab`` completes (common prefix, else the selected row), ``Enter`` descends
into a directory or picks a file, ``Esc`` cancels.

Self-contained: the host passes the history in and receives the picked path
via ``chosen`` (or a ``cancelled``); it never touches the file itself.
"""

from __future__ import annotations

import os

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QFont, QKeyEvent
from PySide6.QtWidgets import QLabel, QLineEdit, QVBoxLayout, QWidget

from textli import openfile
from textli.constants import (
    FONT_FAMILY,
    ZEN_HINT_COLOR,
    ZEN_MD_COMMENT_HL,
    ZEN_MD_FONT_SIZE_MIN,
    ZEN_TEXT_COLOR,
    ZEN_TITLE_COLOR,
    _CTRL_MOD,
)

_MAX_VISIBLE = 12       # suggestion rows shown at once (window slides)
_DISPLAY_MAX = 68       # longer paths are middle-truncated for display


class OpenFileOverlay(QWidget):
    """The `go` open-file card. Emits ``chosen(str)`` with an absolute file
    path (which may not exist yet — opening a new note is legitimate), or
    ``cancelled()``."""

    chosen = Signal(str)
    cancelled = Signal()

    def __init__(self, parent: QWidget, history: list[str], font_size: int):
        super().__init__(parent)
        self._history = history
        self._rows: list[openfile.Candidate] = []
        self._sel = 0
        self._font_size = max(ZEN_MD_FONT_SIZE_MIN, font_size - 3)

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

        title = QLabel("Open file", self)
        title.setStyleSheet(
            f"QLabel {{ color: {ZEN_TEXT_COLOR.name()}; font-weight: bold; }}")
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
        lay.addWidget(self._list)

        self._refresh("")

    # ── Host API ──

    def open(self):
        """Place the card over the parent (upper middle) and take focus."""
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
        """Recompute the ranked rows for the current query and repaint."""
        self._rows = openfile.suggestions(text, self._history)
        self._sel = 0
        self._render()

    def _render(self):
        rows = self._rows
        # Slide a window over the rows so the selection stays visible.
        start = max(0, min(self._sel - _MAX_VISIBLE // 2,
                           len(rows) - _MAX_VISIBLE))
        window = rows[start:start + _MAX_VISIBLE]
        lines = []
        for i, cand in enumerate(window, start=start):
            bg = (f"background:{ZEN_MD_COMMENT_HL.name()};"
                  if i == self._sel else "")
            marker = (f"<span style='color:{ZEN_TITLE_COLOR.name()}'>●</span>"
                      if cand.from_history else
                      f"<span style='color:{ZEN_HINT_COLOR.name()}'>○</span>")
            style = "font-weight:bold;" if cand.is_dir else ""
            lines.append(
                f"<tr><td style='{bg}padding:1px 8px'>{marker}&nbsp;"
                f"<span style='{style}color:{ZEN_TEXT_COLOR.name()}'>"
                f"{self._display(cand.path)}</span></td></tr>")
        more = ""
        if len(rows) > start + _MAX_VISIBLE:
            more = (f"<div style='padding:1px 8px;"
                    f"color:{ZEN_HINT_COLOR.name()}'>…</div>")
        empty = ("" if rows else
                 f"<div style='padding:1px 8px;color:{ZEN_HINT_COLOR.name()}'>"
                 f"no matches — Enter opens the typed path as a new file</div>")
        self._list.setText(
            f"<table cellspacing='0'>{''.join(lines)}</table>{more}{empty}")
        self._place()

    @staticmethod
    def _display(path: str) -> str:
        """Path as shown: home as ``~``, long paths middle-truncated."""
        home = os.path.expanduser("~")
        if path.startswith(home + "/") or path == home:
            path = "~" + path[len(home):]
        if len(path) > _DISPLAY_MAX:
            keep = _DISPLAY_MAX // 2 - 1
            path = path[:keep] + "…" + path[-keep:]
        return path

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
        if key in (Qt.Key.Key_Down,) or (ctrl and key == Qt.Key.Key_N):
            self._move_sel(+1)
            return True
        if key in (Qt.Key.Key_Up,) or (ctrl and key == Qt.Key.Key_P):
            self._move_sel(-1)
            return True
        if key == Qt.Key.Key_Tab:
            self._complete()
            return True
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._accept()
            return True
        return False

    def _move_sel(self, step: int):
        if self._rows:
            self._sel = max(0, min(len(self._rows) - 1, self._sel + step))
            self._render()

    def _complete(self):
        """Tab — extend the input to the rows' common prefix when that gains
        characters; otherwise adopt the selected row (dirs end in ``/``, so a
        second Tab then lists their content)."""
        if not self._rows:
            return
        typed = os.path.expanduser(self._input.text())
        prefix = openfile.common_prefix([c.path for c in self._rows])
        target = prefix if len(prefix) > len(typed) else (
            self._rows[self._sel].path)
        self._input.setText(target)

    def _accept(self):
        """Enter — descend into the selected directory, or pick the selected
        file. With no matches, open the typed path as a new file when its
        directory exists (mirrors the CLI: created on first save)."""
        if self._rows:
            cand = self._rows[self._sel]
            if cand.is_dir:
                self._input.setText(cand.path)   # descend: re-lists content
                return
            self.chosen.emit(cand.path)
            return
        typed = os.path.expanduser(self._input.text()).strip()
        if typed and openfile.looks_like_path(typed) \
                and os.path.isdir(os.path.dirname(typed)) \
                and not typed.endswith("/"):
            self.chosen.emit(os.path.abspath(typed))
