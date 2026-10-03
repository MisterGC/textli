"""Redo in the full editor (#76): `U` redoes in the write view, because ⌃R
belongs to the reading/write toggle and reaches vim never.

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
