"""Tests for the zen markdown Vim key handler."""

from __future__ import annotations

import os

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent, QTextCursor
from PySide6.QtWidgets import QApplication, QPlainTextEdit

from textli.constants import _CTRL_MOD
from textli.vim import VimKeyHandler, VimMode

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _key(key, text="", mods=Qt.KeyboardModifier.NoModifier) -> QKeyEvent:
    return QKeyEvent(QEvent.Type.KeyPress, key, mods, text)


def _handler(text: str) -> tuple[QPlainTextEdit, VimKeyHandler]:
    _app()
    editor = QPlainTextEdit(text)
    handler = VimKeyHandler(
        editor=editor,
        mode_changed=lambda mode: None,
        close_save=lambda: None,
        close_cancel=lambda: None,
    )
    return editor, handler


def test_normal_mode_autorepeat_moves_one_step():
    """Each auto-repeat event moves one step (Qt 6 sends individual events)."""
    editor, handler = _handler("abcd")
    event = QKeyEvent(
        QEvent.Type.KeyPress,
        Qt.Key.Key_L,
        Qt.KeyboardModifier.NoModifier,
        "l",
        True,
        1,
    )

    assert handler.handle_key(event) is True
    assert editor.textCursor().position() == 1


def test_normal_mode_autorepeat_deletes_one_char():
    """Each auto-repeat x event deletes one char (Qt 6 sends individual events)."""
    editor, handler = _handler("abcdef")
    event = QKeyEvent(
        QEvent.Type.KeyPress,
        Qt.Key.Key_X,
        Qt.KeyboardModifier.NoModifier,
        "x",
        True,
        1,
    )

    assert handler.handle_key(event) is True
    assert editor.toPlainText() == "bcdef"


def test_insert_mode_enter_inserts_newline():
    """Enter in insert mode inserts a newline and is consumed (the handler
    does it explicitly so macOS input-method handling can't swallow it)."""
    editor, handler = _handler("ab")
    editor.moveCursor(QTextCursor.MoveOperation.End)
    handler._set_mode(VimMode.INSERT)
    event = QKeyEvent(
        QEvent.Type.KeyPress, Qt.Key.Key_Return,
        Qt.KeyboardModifier.NoModifier, "\r",
    )
    assert handler.handle_key(event) is True
    assert editor.toPlainText() == "ab\n"


def test_normal_u_undoes_last_edit():
    """`u` in NORMAL undoes the last change on the editor's native undo stack."""
    editor, handler = _handler("abcdef")
    assert handler.handle_key(_key(Qt.Key.Key_X, "x")) is True   # → bcdef
    assert editor.toPlainText() == "bcdef"
    assert handler.handle_key(_key(Qt.Key.Key_U, "u")) is True
    assert editor.toPlainText() == "abcdef"


def test_normal_ctrl_r_redoes():
    """`Ctrl-r` redoes what `u` just undid (physical Ctrl, Meta on macOS)."""
    editor, handler = _handler("abcdef")
    handler.handle_key(_key(Qt.Key.Key_X, "x"))                  # → bcdef
    handler.handle_key(_key(Qt.Key.Key_U, "u"))                  # → abcdef
    assert handler.handle_key(_key(Qt.Key.Key_R, "r", _CTRL_MOD)) is True
    assert editor.toPlainText() == "bcdef"
