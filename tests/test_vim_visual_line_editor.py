"""`V`, `gv` and the visual operators in the full editor (#81): the whisper
status line names VISUAL LINE, and keys the editor claims in NORMAL mode — `n`
steps to the next search hit — reach the selection instead.

Driven through ``ZenMarkdownEditor`` rather than ``VimKeyHandler`` alone: keys
go to the write view as events, so the editor's filter sees them first."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path  # noqa: E402

from PySide6.QtCore import QEvent, Qt  # noqa: E402
from PySide6.QtGui import QKeyEvent  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from textli.editor import ZenMarkdownEditor  # noqa: E402
from textli.vim import VimMode  # noqa: E402

_ESC = "\x1b"
_SPECIAL = {_ESC: Qt.Key.Key_Escape, ">": Qt.Key.Key_Greater,
            "<": Qt.Key.Key_Less, "~": Qt.Key.Key_AsciiTilde}


def _editor(text, tmp_path) -> ZenMarkdownEditor:
    QApplication.instance() or QApplication([])
    parent = QWidget()
    parent.resize(1000, 700)
    path = Path(tmp_path) / "doc.md"
    path.write_text(text, encoding="utf-8")
    ed = ZenMarkdownEditor(parent, text, title="T", file_path=path)
    ed._parent = parent
    if ed._rendered_mode:
        ed._toggle_rendered()
    cur = ed._editor.textCursor()
    cur.setPosition(0)
    ed._editor.setTextCursor(cur)
    return ed


def _keys(ed, keys: str):
    """Send ``keys`` to the write view as real key events."""
    for ch in keys:
        mods = Qt.KeyboardModifier.NoModifier
        if ch in _SPECIAL:
            key = _SPECIAL[ch]
        else:
            key = getattr(Qt.Key, f"Key_{ch.upper()}")
            if ch.isupper():
                mods = Qt.KeyboardModifier.ShiftModifier
        QApplication.sendEvent(ed._editor, QKeyEvent(
            QEvent.Type.KeyPress, key, mods, "" if ch == _ESC else ch))


def test_the_status_line_names_visual_line(tmp_path):
    ed = _editor("abc\n", tmp_path)
    _keys(ed, "V")
    assert ed._vim.mode == VimMode.VISUAL_LINE
    assert ed._status_label.text().startswith("VISUAL LINE")
    _keys(ed, "v")
    assert ed._status_label.text().startswith("VISUAL ·")


def test_V_and_gv_in_the_write_view(tmp_path):
    ed = _editor("one\ntwo\nthree\n", tmp_path)
    _keys(ed, "Vjy" + "G" + "p")
    assert ed._editor.toPlainText() == "one\ntwo\nthree\n\none\ntwo"
    _keys(ed, "gg" + "gv" + "d")
    assert ed._editor.toPlainText() == "three\n\none\ntwo"


def test_visual_operators_in_the_write_view(tmp_path):
    ed = _editor("one\ntwo\n", tmp_path)
    _keys(ed, "Vj>")
    assert ed._editor.toPlainText() == "    one\n    two\n"
    _keys(ed, "VjU")
    assert ed._editor.toPlainText() == "    ONE\n    TWO\n"
    _keys(ed, "Vj<" + "VjJ")
    assert ed._editor.toPlainText() == "ONE TWO\n"
    _keys(ed, "0vlrn")                 # `n` is the replacement, not a search step
    assert ed._editor.toPlainText() == "nnE TWO\n"
    assert ed._vim.mode == VimMode.NORMAL
