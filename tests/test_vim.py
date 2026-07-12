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


_SPECIAL = {"$": Qt.Key.Key_Dollar}


def _press(handler, ch, *, shift=False, ctrl=False):
    """Send one vim keystroke by character (letters, digits, `$`)."""
    mods = Qt.KeyboardModifier.NoModifier
    if shift:
        mods |= Qt.KeyboardModifier.ShiftModifier
    if ctrl:
        mods |= _CTRL_MOD
    if ch.isalpha():
        key = getattr(Qt.Key, f"Key_{ch.upper()}")
    elif ch.isdigit():
        key = getattr(Qt.Key, f"Key_{ch}")
    else:
        key = _SPECIAL[ch]
    handler.handle_key(_key(key, ch, mods))


def _at(editor, pos):
    c = editor.textCursor()
    c.setPosition(pos)
    editor.setTextCursor(c)


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


# ── Counts ──

def test_count_repeats_motion():
    editor, handler = _handler("abcdefgh")
    _press(handler, "3")
    _press(handler, "l")
    assert editor.textCursor().position() == 3
    # the count is spent — the next motion moves a single step
    _press(handler, "l")
    assert editor.textCursor().position() == 4


def test_count_repeats_x():
    editor, handler = _handler("abcdef")
    _press(handler, "3")
    _press(handler, "x")
    assert editor.toPlainText() == "def"


def test_count_dd_deletes_n_lines():
    editor, handler = _handler("l1\nl2\nl3\nl4")
    _press(handler, "2")
    _press(handler, "d")
    _press(handler, "d")
    assert editor.toPlainText() == "l3\nl4"


def test_count_G_jumps_to_line():
    editor, handler = _handler("aa\nbb\ncc")
    _press(handler, "2")
    _press(handler, "G", shift=True)
    assert editor.textCursor().position() == 3   # start of line 2


def test_gg_goes_to_first_line():
    editor, handler = _handler("aa\nbb\ncc")
    _at(editor, 7)
    _press(handler, "g")
    _press(handler, "g")
    assert editor.textCursor().position() == 0


# ── Yank / paste ──

def test_yy_p_duplicates_line_below():
    editor, handler = _handler("one\ntwo")
    _at(editor, 0)
    _press(handler, "y")
    _press(handler, "y")
    _press(handler, "p")
    assert editor.toPlainText() == "one\none\ntwo"


def test_yy_P_pastes_line_above():
    editor, handler = _handler("one\ntwo")
    _at(editor, 0)
    _press(handler, "y")
    _press(handler, "y")
    _press(handler, "P", shift=True)
    assert editor.toPlainText() == "one\none\ntwo"


def test_dd_then_p_moves_line_down():
    editor, handler = _handler("a\nb\nc")
    _at(editor, 0)
    _press(handler, "d")
    _press(handler, "d")            # delete "a" → cursor on "b"
    _press(handler, "p")            # paste "a" below "b"
    assert editor.toPlainText() == "b\na\nc"


def test_charwise_x_then_p_pastes_after():
    editor, handler = _handler("abc")
    _at(editor, 0)
    _press(handler, "x")            # delete 'a' → "bc", register 'a'
    _press(handler, "p")            # paste after 'b' → "bac"
    assert editor.toPlainText() == "bac"


# ── Visual mode ──

def test_v_enters_visual():
    _editor, handler = _handler("hello")
    _press(handler, "v")
    assert handler.mode == VimMode.VISUAL


def test_visual_delete_selection():
    editor, handler = _handler("hello world")
    _at(editor, 0)
    _press(handler, "v")
    _press(handler, "l")
    _press(handler, "l")
    _press(handler, "l")            # select "hel"
    _press(handler, "d")
    assert editor.toPlainText() == "lo world"
    assert handler.mode == VimMode.NORMAL


def test_visual_change_enters_insert():
    editor, handler = _handler("hello")
    _at(editor, 0)
    _press(handler, "v")
    _press(handler, "l")
    _press(handler, "l")            # select "he"
    _press(handler, "c")
    assert editor.toPlainText() == "llo"
    assert handler.mode == VimMode.INSERT


def test_visual_yank_then_paste():
    editor, handler = _handler("ab")
    _at(editor, 0)
    _press(handler, "v")
    _press(handler, "l")            # select "a"
    _press(handler, "y")            # yank "a", back to NORMAL at start
    assert handler.mode == VimMode.NORMAL
    _press(handler, "$")            # end of line
    _press(handler, "p")            # paste "a" after end → "aba"
    assert editor.toPlainText() == "aba"


def test_visual_esc_leaves_without_deleting():
    editor, handler = _handler("hello")
    _at(editor, 0)
    _press(handler, "v")
    _press(handler, "l")
    _press(handler, "l")
    handler.handle_key(_key(Qt.Key.Key_Escape))
    assert handler.mode == VimMode.NORMAL
    assert editor.toPlainText() == "hello"
