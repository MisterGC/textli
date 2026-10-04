"""`R` and counted inserts in the full editor (#80): the keys the editor would
otherwise claim in NORMAL mode — `/` opens search, `n` steps to the next hit —
are typed over the text in REPLACE, and the whisper status line names the mode.

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
_SPECIAL = {_ESC: Qt.Key.Key_Escape, "/": Qt.Key.Key_Slash,
            ">": Qt.Key.Key_Greater, "<": Qt.Key.Key_Less}


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
        elif ch.isdigit():
            key = getattr(Qt.Key, f"Key_{ch}")
        else:
            key = getattr(Qt.Key, f"Key_{ch.upper()}")
            if ch.isupper():
                mods = Qt.KeyboardModifier.ShiftModifier
        QApplication.sendEvent(ed._editor, QKeyEvent(
            QEvent.Type.KeyPress, key, mods, "" if ch == _ESC else ch))


def test_R_types_over_keys_the_editor_claims_in_normal(tmp_path):
    ed = _editor("abcdef\n", tmp_path)
    _keys(ed, "Rn/")
    assert ed._vim.mode == VimMode.REPLACE
    assert ed._search_overlay is None        # `/` never opened search
    _keys(ed, _ESC)
    assert ed._editor.toPlainText() == "n/cdef\n"
    assert ed._vim.mode == VimMode.NORMAL


def test_the_status_line_names_replace(tmp_path):
    ed = _editor("abc\n", tmp_path)
    _keys(ed, "R")
    assert ed._status_label.text().startswith("REPLACE")


def test_a_counted_insert_repeats_in_the_write_view(tmp_path):
    ed = _editor("abc\n", tmp_path)
    _keys(ed, "3ihi" + _ESC)
    assert ed._editor.toPlainText() == "hihihiabc\n"


def test_shift_and_case_operators_in_the_write_view(tmp_path):
    ed = _editor("one two\nthree\n", tmp_path)
    _keys(ed, ">>")
    assert ed._editor.toPlainText() == "    one two\nthree\n"
    _keys(ed, "gUiw")
    assert ed._editor.toPlainText() == "    ONE two\nthree\n"
    _keys(ed, "<<")
    assert ed._editor.toPlainText() == "ONE two\nthree\n"
