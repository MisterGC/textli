"""`o`, `O` and Enter continue a Markdown list and keep its indent; `cc` and
`S` keep the indent too (#83).

Driven through ``ZenMarkdownEditor`` rather than ``VimKeyHandler`` alone: the
editor claims Enter in NORMAL mode (to follow a link), so keys go to the write
view as events and its filter sees them first."""

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
_CR = "\r"
_SPECIAL = {_ESC: Qt.Key.Key_Escape, _CR: Qt.Key.Key_Return,
            ".": Qt.Key.Key_Period}


def _editor(text, tmp_path, pos=0) -> ZenMarkdownEditor:
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
    cur.setPosition(pos)
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


def _text(ed) -> str:
    return ed._editor.toPlainText()


# ── o and O ──

def test_o_continues_a_bullet_list(tmp_path):
    ed = _editor("- item\n", tmp_path)
    _keys(ed, "onext" + _ESC)
    assert _text(ed) == "- item\n- next\n"


def test_o_counts_on_a_numbered_list(tmp_path):
    ed = _editor("1. a\n", tmp_path)
    _keys(ed, "ob" + _ESC)
    assert _text(ed) == "1. a\n2. b\n"


def test_o_opens_an_unchecked_task(tmp_path):
    ed = _editor("- [x] x\n", tmp_path)
    _keys(ed, "oy" + _ESC)
    assert _text(ed) == "- [x] x\n- [ ] y\n"


def test_o_keeps_a_nested_items_indent(tmp_path):
    ed = _editor("- a\n  - [ ] x\n", tmp_path, pos=4)
    _keys(ed, "oy" + _ESC)
    assert _text(ed) == "- a\n  - [ ] x\n  - [ ] y\n"


def test_O_opens_the_same_item_above(tmp_path):
    ed = _editor("  - item\n", tmp_path)
    _keys(ed, "Onew" + _ESC)
    assert _text(ed) == "  - new\n  - item\n"
    ed = _editor("1. a\n", tmp_path)
    _keys(ed, "Oz" + _ESC)
    assert _text(ed) == "1. z\n1. a\n"
    ed = _editor("- [ ] x\n", tmp_path)
    _keys(ed, "Ow" + _ESC)
    assert _text(ed) == "- [ ] w\n- [ ] x\n"


def test_o_keeps_the_indent_of_a_plain_line(tmp_path):
    ed = _editor("  ab\n", tmp_path)
    _keys(ed, "ocd" + _ESC)
    assert _text(ed) == "  ab\n  cd\n"


def test_o_on_prose_opens_a_bare_line(tmp_path):
    ed = _editor("ab\n", tmp_path)
    _keys(ed, "ocd" + _ESC)
    assert _text(ed) == "ab\ncd\n"


def test_a_counted_o_numbers_each_copy(tmp_path):
    ed = _editor("1. a\n", tmp_path)
    _keys(ed, "3ox" + _ESC)
    assert _text(ed) == "1. a\n2. x\n3. x\n4. x\n"


def test_a_counted_o_with_nothing_typed_opens_empty_lines(tmp_path):
    ed = _editor("- a\n", tmp_path)
    _keys(ed, "3o" + _ESC)
    assert _text(ed) == "- a\n\n\n\n"


def test_dot_repeats_o_with_the_next_number(tmp_path):
    ed = _editor("1. a\n", tmp_path)
    _keys(ed, "ox" + _ESC + ".")
    assert _text(ed) == "1. a\n2. x\n3. x\n"


# ── Enter in INSERT ──

def test_enter_continues_the_list(tmp_path):
    ed = _editor("- item\n", tmp_path)
    _keys(ed, "A" + _CR + "next" + _ESC)
    assert _text(ed) == "- item\n- next\n"
    ed = _editor("1. a\n", tmp_path)
    _keys(ed, "A" + _CR + "b" + _ESC)
    assert _text(ed) == "1. a\n2. b\n"
    ed = _editor("  - [ ] x\n", tmp_path)
    _keys(ed, "A" + _CR + "y" + _ESC)
    assert _text(ed) == "  - [ ] x\n  - [ ] y\n"


def test_enter_mid_item_splits_it_into_two_items(tmp_path):
    ed = _editor("- abcd\n", tmp_path, pos=4)
    _keys(ed, "i" + _CR + _ESC)
    assert _text(ed) == "- ab\n- cd\n"


def test_enter_on_an_empty_item_ends_the_list(tmp_path):
    ed = _editor("- a\n", tmp_path)
    _keys(ed, "A" + _CR + _CR + "after" + _ESC)
    assert _text(ed) == "- a\nafter\n"
    ed = _editor("  1. a\n", tmp_path)
    _keys(ed, "A" + _CR + _CR + _ESC)
    assert _text(ed) == "  1. a\n\n"
    assert ed._vim.mode == VimMode.NORMAL


def test_enter_keeps_the_indent_of_a_plain_line(tmp_path):
    ed = _editor("  ab\n", tmp_path)
    _keys(ed, "A" + _CR + "cd" + _ESC)
    assert _text(ed) == "  ab\n  cd\n"


def test_enter_before_the_marker_pushes_the_line_down(tmp_path):
    ed = _editor("- a\n", tmp_path)
    _keys(ed, "i" + _CR + _ESC)
    assert _text(ed) == "\n- a\n"


def test_enter_in_normal_with_no_link_leaves_the_text_alone(tmp_path):
    ed = _editor("- a\n", tmp_path)
    _keys(ed, _CR)
    assert _text(ed) == "- a\n"
    assert ed._vim.mode == VimMode.NORMAL


# ── cc and S ──

def test_cc_keeps_the_indent(tmp_path):
    ed = _editor("  ab\n", tmp_path, pos=3)
    _keys(ed, "cc")
    assert _text(ed) == "  \n"
    assert ed._editor.textCursor().position() == 2
    _keys(ed, "xy" + _ESC)
    assert _text(ed) == "  xy\n"


def test_S_keeps_the_indent(tmp_path):
    ed = _editor("  ab\n", tmp_path)
    _keys(ed, "Sxy" + _ESC)
    assert _text(ed) == "  xy\n"


def test_cc_still_yanks_the_whole_line(tmp_path):
    ed = _editor("  ab\nz\n", tmp_path)
    _keys(ed, "ccq" + _ESC + "jp")
    assert _text(ed) == "  q\nz\n  ab\n"


def test_counted_cc_keeps_the_first_lines_indent(tmp_path):
    ed = _editor("  ab\n  cd\nz\n", tmp_path)
    _keys(ed, "2ccx" + _ESC)
    assert _text(ed) == "  x\nz\n"
