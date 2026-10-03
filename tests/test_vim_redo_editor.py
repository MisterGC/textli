"""Undo and redo in the full editor: `U` redoes in the write view, because ⌃R
belongs to the reading/write toggle and reaches vim never (#76); one `u` takes
back one whole change, its insert leg included, and leaves the caret where the
change began (#79) — with the editor's highlighter and filter in the loop.

Driven through ``ZenMarkdownEditor`` rather than ``VimKeyHandler`` alone: keys
go to the write view as events, so the editor's filter sees them first — the
same path that takes ⌃R for the toggle."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path  # noqa: E402

from PySide6.QtCore import QEvent, Qt  # noqa: E402
from PySide6.QtGui import QKeyEvent  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from textli.constants import _CTRL_MOD  # noqa: E402
from textli.editor import ZenMarkdownEditor  # noqa: E402

DOC = "abcdef\n"


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
    return ed


def _send(ed, key, text="", mods=Qt.KeyboardModifier.NoModifier):
    QApplication.sendEvent(ed._editor, QKeyEvent(
        QEvent.Type.KeyPress, key, mods, text))


def test_u_then_shift_u_restores_the_change(tmp_path):
    ed = _editor(DOC, tmp_path)
    cur = ed._editor.textCursor()
    cur.setPosition(0)
    ed._editor.setTextCursor(cur)
    _send(ed, Qt.Key.Key_X, "x")
    assert ed._editor.toPlainText() == "bcdef\n"
    _send(ed, Qt.Key.Key_U, "u")
    assert ed._editor.toPlainText() == "abcdef\n"
    _send(ed, Qt.Key.Key_U, "U", Qt.KeyboardModifier.ShiftModifier)
    assert ed._editor.toPlainText() == "bcdef\n"
    assert not ed._rendered_mode


def test_ctrl_r_toggles_the_view_instead_of_redoing(tmp_path):
    ed = _editor(DOC, tmp_path)
    cur = ed._editor.textCursor()
    cur.setPosition(0)
    ed._editor.setTextCursor(cur)
    _send(ed, Qt.Key.Key_X, "x")
    _send(ed, Qt.Key.Key_U, "u")
    _send(ed, Qt.Key.Key_R, "r", _CTRL_MOD)
    assert ed._rendered_mode
    assert ed._editor.toPlainText() == "abcdef\n"


def test_one_u_undoes_cw_and_one_shift_u_redoes_it(tmp_path):
    ed = _editor("aaa bbb\n", tmp_path)
    cur = ed._editor.textCursor()
    cur.setPosition(0)
    ed._editor.setTextCursor(cur)
    for ch in "cwfoo":
        _send(ed, getattr(Qt.Key, f"Key_{ch.upper()}"), ch)
    _send(ed, Qt.Key.Key_Escape)
    assert ed._editor.toPlainText() == "foo bbb\n"
    _send(ed, Qt.Key.Key_U, "u")
    assert ed._editor.toPlainText() == "aaa bbb\n"
    assert ed._editor.textCursor().position() == 0
    _send(ed, Qt.Key.Key_U, "U", Qt.KeyboardModifier.ShiftModifier)
    assert ed._editor.toPlainText() == "foo bbb\n"


def test_dw_then_u_leaves_the_caret_where_the_change_began(tmp_path):
    ed = _editor("a b c\n", tmp_path)
    cur = ed._editor.textCursor()
    cur.setPosition(0)
    ed._editor.setTextCursor(cur)
    _send(ed, Qt.Key.Key_D, "d")
    _send(ed, Qt.Key.Key_W, "w")
    assert ed._editor.toPlainText() == "b c\n"
    _send(ed, Qt.Key.Key_U, "u")
    assert ed._editor.toPlainText() == "a b c\n"
    assert ed._editor.textCursor().position() == 0


def _keys(ed, keys, pos):
    cur = ed._editor.textCursor()
    cur.setPosition(pos)
    ed._editor.setTextCursor(cur)
    for ch in keys:
        if ch == "\x1b":
            _send(ed, Qt.Key.Key_Escape)
        elif ch.isupper():
            _send(ed, getattr(Qt.Key, f"Key_{ch}"), ch,
                  Qt.KeyboardModifier.ShiftModifier)
        elif ch.isdigit():
            _send(ed, getattr(Qt.Key, f"Key_{ch}"), ch)
        else:
            _send(ed, getattr(Qt.Key, f"Key_{ch.upper()}"), ch)
    return ed._editor.toPlainText(), ed._editor.textCursor().position()


def test_undo_puts_the_caret_where_a_leftward_change_began(tmp_path):
    # Carets checked against vim 9.2.
    for text, pos, keys, want in [
        ("abcdef\n", 3, "Xu", ("abcdef\n", 2)),
        ("abc def\n", 5, "dbu", ("abc def\n", 4)),
        ("abcdef\n", 4, "vhhdu", ("abcdef\n", 2)),
        ("abc def\n", 1, "Afoo\x1bu", ("abc def\n", 6)),
        ("# abc def\n", 4, "dbu", ("# abc def\n", 2)),
    ]:
        assert _keys(_editor(text, tmp_path), keys, pos) == want, keys


def test_two_inserts_in_a_row_undo_one_at_a_time(tmp_path):
    ed = _editor("abc def\n", tmp_path)
    assert _keys(ed, "ifoo\x1babar\x1bu", 0) == ("fooabc def\n", 3)
    _send(ed, Qt.Key.Key_U, "u")
    assert ed._editor.toPlainText() == "abc def\n"
