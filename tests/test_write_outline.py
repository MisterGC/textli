"""Headings overview (`gh`) in the write view (#28): the reading view's
outline jump-list works over the source editor too — parsed from the source
(fenced `#` lines skipped), previewing on j/k, keeping on Enter, restoring on
Esc — the same contract as the reading view, driving the QPlainTextEdit."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, Qt  # noqa: E402
from PySide6.QtGui import QKeyEvent  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from textli.editor import ZenMarkdownEditor  # noqa: E402

_SRC = (
    "# Title\n\nintro\n\n"
    "## Alpha\n\naaa\n\n"
    "```\n# not a heading (fenced)\n```\n\n"
    "## Beta\n\nbbb\n"
)


def _open() -> ZenMarkdownEditor:
    QApplication.instance() or QApplication([])
    parent = QWidget()
    parent.resize(900, 700)
    ed = ZenMarkdownEditor(parent, _SRC, title="t")
    ed._parent = parent
    return ed


def _press(ed, key, text=""):
    ed.eventFilter(ed._editor, QKeyEvent(
        QEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier, text))


def test_source_outline_skips_fenced_hashes():
    ed = _open()
    rows = ed._build_source_headings_list()
    assert [(lvl, txt) for (_s, _e, lvl, txt) in rows] == [
        (1, "Title"), (2, "Alpha"), (2, "Beta")]


def test_gh_opens_outline_over_the_write_view():
    ed = _open()
    assert not ed._rendered_mode
    _press(ed, Qt.Key.Key_G, "g")
    _press(ed, Qt.Key.Key_H, "h")
    assert ed._overview_overlay is not None
    assert ed._overview_view is ed._editor          # drives the source editor
    assert len(ed._overview_rows) == 3


def test_j_previews_and_enter_lands_on_the_heading():
    ed = _open()
    _press(ed, Qt.Key.Key_G, "g")
    _press(ed, Qt.Key.Key_H, "h")
    _press(ed, Qt.Key.Key_J, "j")                   # preview the next heading
    _press(ed, Qt.Key.Key_Return, "\r")             # keep it
    assert ed._overview_overlay is None
    assert ed._editor.textCursor().block().text().strip() == "## Alpha"


def test_esc_restores_the_origin():
    ed = _open()
    _press(ed, Qt.Key.Key_G, "g")
    _press(ed, Qt.Key.Key_H, "h")
    origin = ed._editor.textCursor().position()
    _press(ed, Qt.Key.Key_J, "j")
    _press(ed, Qt.Key.Key_Escape, "\x1b")
    assert ed._overview_overlay is None
    assert ed._editor.textCursor().position() == origin
