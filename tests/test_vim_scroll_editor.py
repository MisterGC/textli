"""The write view scrolls and jumps like vim (#82): `H M L` land on the
screen's top, middle and bottom line and work as line-wise motions, `⌃d ⌃u
⌃f ⌃b ⌃e ⌃y` scroll with the caret riding along, and `zz zt zb` put the caret
line mid, top or bottom.

Driven through ``ZenMarkdownEditor`` rather than ``VimKeyHandler`` alone: the
editor's filter sees every Ctrl key first, and the screen these keys measure
is the write view's own. The window is shown so the view has real geometry.
Where a check needs to know which rows are on screen it measures them itself,
from the caret rectangles, rather than asking the handler that is under
test."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path  # noqa: E402

from PySide6.QtCore import QEvent, Qt  # noqa: E402
from PySide6.QtGui import QKeyEvent, QTextCursor  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from textli.constants import _CTRL_MOD  # noqa: E402
from textli.editor import ZenMarkdownEditor  # noqa: E402
from textli.vim import VimMode  # noqa: E402

_LINES = "\n".join(f"line {i}" for i in range(1, 201))


def _editor(text, tmp_path, pos=0) -> ZenMarkdownEditor:
    app = QApplication.instance() or QApplication([])
    parent = QWidget()
    parent.resize(1000, 700)
    path = Path(tmp_path) / "doc.md"
    path.write_text(text, encoding="utf-8")
    ed = ZenMarkdownEditor(parent, text, title="T", file_path=path)
    ed._parent = parent
    if ed._rendered_mode:
        ed._toggle_rendered()
    parent.show()
    app.processEvents()
    cur = ed._editor.textCursor()
    cur.setPosition(pos)
    ed._editor.setTextCursor(cur)
    app.processEvents()
    return ed


def _send(ed, key, text="", mods=Qt.KeyboardModifier.NoModifier):
    QApplication.sendEvent(ed._editor, QKeyEvent(
        QEvent.Type.KeyPress, key, mods, text))
    QApplication.processEvents()


def _type(ed, keys):
    for ch in keys:
        if ch == ".":
            key = Qt.Key.Key_Period
        elif ch.isalpha():
            key = getattr(Qt.Key, f"Key_{ch.upper()}")
        else:
            key = getattr(Qt.Key, f"Key_{ch}")
        mods = (Qt.KeyboardModifier.ShiftModifier if ch.isupper()
                else Qt.KeyboardModifier.NoModifier)
        _send(ed, key, ch, mods)


def _ctrl(ed, letter, count=""):
    _type(ed, count)
    _send(ed, getattr(Qt.Key, f"Key_{letter.upper()}"), "", _CTRL_MOD)


def _line(ed) -> int:
    """The caret's line, 1-based."""
    return ed._editor.textCursor().blockNumber() + 1


def _top(ed) -> int:
    """The first line on screen, 1-based."""
    return ed._editor.firstVisibleBlock().blockNumber() + 1


def _rect(ed, pos):
    c = QTextCursor(ed._editor.document())
    c.setPosition(pos)
    return ed._editor.cursorRect(c)


def _whole(ed, pos) -> bool:
    """Whether the display row holding ``pos`` is entirely on screen."""
    r = _rect(ed, pos)
    return r.top() >= 0 and r.bottom() < ed._editor.viewport().height()


def _rows(ed) -> list[int]:
    """The 1-based line numbers of the one-row lines wholly on screen."""
    doc = ed._editor.document()
    return [n + 1 for n in range(doc.blockCount())
            if _whole(ed, doc.findBlockByNumber(n).position())]


# ── H M L ──


def test_H_M_L_land_on_the_top_middle_and_bottom_line(tmp_path):
    ed = _editor(_LINES, tmp_path)
    _ctrl(ed, "e", "5")                       # scroll so H isn't line 1
    rows = _rows(ed)
    assert len(rows) > 6 and rows[0] == 6
    _type(ed, "L")
    assert _line(ed) == rows[-1]
    _type(ed, "M")
    assert _line(ed) == rows[(len(rows) - 1) // 2]
    _type(ed, "H")
    assert _line(ed) == rows[0]
    assert _rows(ed) == rows                  # none of them scrolled


def test_H_and_L_take_a_count_from_their_edge(tmp_path):
    ed = _editor(_LINES, tmp_path)
    rows = _rows(ed)
    _type(ed, "3H")
    assert _line(ed) == rows[2]
    _type(ed, "3L")
    assert _line(ed) == rows[-3]


def test_H_lands_on_the_first_non_blank(tmp_path):
    ed = _editor("    indented\nline 2\n", tmp_path, pos=16)
    _type(ed, "H")
    assert ed._editor.textCursor().position() == 4


def test_M_on_a_short_text_is_the_middle_of_the_text(tmp_path):
    ed = _editor("a\nb\nc\nd\ne\n", tmp_path)
    _type(ed, "M")
    assert _line(ed) == 3


def test_dL_deletes_line_wise_to_the_bottom_of_the_screen(tmp_path):
    ed = _editor(_LINES, tmp_path)
    rows = _rows(ed)
    _type(ed, "jdL")
    lines = ed._editor.toPlainText().split("\n")
    assert lines[0] == "line 1"
    assert lines[1] == f"line {rows[-1] + 1}"
    assert ed._vim._register == "\n".join(
        f"line {n}" for n in range(2, rows[-1] + 1)) + "\n"


def test_yH_yanks_from_the_top_of_the_screen(tmp_path):
    ed = _editor(_LINES, tmp_path)
    _type(ed, "jjyH")
    assert ed._vim._register == "line 1\nline 2\nline 3\n"
    assert ed._editor.toPlainText() == _LINES


def test_L_extends_a_visual_line_selection(tmp_path):
    ed = _editor(_LINES, tmp_path)
    rows = _rows(ed)
    _type(ed, "VL")
    assert ed._vim.mode == VimMode.VISUAL_LINE
    _type(ed, "d")
    assert ed._editor.toPlainText().split("\n")[0] == f"line {rows[-1] + 1}"


# ── ⌃d ⌃u ⌃f ⌃b ⌃e ⌃y ──


def test_ctrl_d_and_ctrl_u_scroll_half_the_view_and_carry_the_caret(tmp_path):
    ed = _editor(_LINES, tmp_path)
    _type(ed, "jj")
    half = len(_rows(ed)) // 2
    _ctrl(ed, "d")
    assert (_line(ed), _top(ed)) == (3 + half, 1 + half)
    _ctrl(ed, "d")
    assert (_line(ed), _top(ed)) == (3 + 2 * half, 1 + 2 * half)
    _ctrl(ed, "u")
    assert (_line(ed), _top(ed)) == (3 + half, 1 + half)


def test_a_count_on_ctrl_d_sets_how_far_it_and_ctrl_u_scroll(tmp_path):
    ed = _editor(_LINES, tmp_path)
    _ctrl(ed, "d", "3")
    assert (_line(ed), _top(ed)) == (4, 4)
    _ctrl(ed, "d")                            # vim keeps the count
    assert (_line(ed), _top(ed)) == (7, 7)
    _ctrl(ed, "u")
    assert (_line(ed), _top(ed)) == (4, 4)


def test_ctrl_f_and_ctrl_b_scroll_a_page_less_two_lines(tmp_path):
    ed = _editor(_LINES, tmp_path)
    page = len(_rows(ed)) - 2
    _ctrl(ed, "f")
    assert _top(ed) == 1 + page
    assert _line(ed) == _top(ed)              # the caret went to the top
    _ctrl(ed, "f", "2")
    assert _top(ed) == 1 + 3 * page
    _type(ed, "L")
    bottom = _line(ed)
    _ctrl(ed, "b")
    assert _top(ed) == 1 + 2 * page
    assert _line(ed) == _rows(ed)[-1]         # the caret went to the bottom
    assert _line(ed) < bottom


def test_ctrl_f_at_the_end_takes_the_caret_to_the_last_line(tmp_path):
    ed = _editor(_LINES, tmp_path)
    for _ in range(40):
        _ctrl(ed, "f")
    assert _line(ed) == 200
    for _ in range(40):
        _ctrl(ed, "b")
    assert _line(ed) == 1


def test_ctrl_e_and_ctrl_y_scroll_a_line_and_keep_the_caret_on_screen(tmp_path):
    ed = _editor(_LINES, tmp_path)
    _type(ed, "jjjll")
    _ctrl(ed, "e")
    assert (_top(ed), _line(ed)) == (2, 4)    # the caret stays put
    _ctrl(ed, "e", "3")
    assert (_top(ed), _line(ed)) == (5, 5)    # pushed onto the top row
    assert ed._editor.textCursor().positionInBlock() == 2
    bottom = _rows(ed)[-1]
    _type(ed, "L")
    _ctrl(ed, "y")
    assert _top(ed) == 4
    assert _line(ed) == bottom - 1            # pulled onto the bottom row


def test_ctrl_d_in_visual_extends_the_selection(tmp_path):
    ed = _editor(_LINES, tmp_path)
    _type(ed, "V")
    _ctrl(ed, "d", "2")
    assert ed._vim.mode == VimMode.VISUAL_LINE
    _type(ed, "d")
    assert ed._editor.toPlainText().split("\n")[0] == "line 4"


def test_a_scroll_abandons_a_pending_operator(tmp_path):
    ed = _editor(_LINES, tmp_path)
    _type(ed, "d")
    _ctrl(ed, "d")
    _type(ed, "j")
    assert ed._editor.toPlainText() == _LINES
    assert not ed._vim.has_pending


def test_keys_the_editor_owns_keep_their_meaning(tmp_path):
    ed = _editor(_LINES, tmp_path)
    typewriter = ed._typewriter
    _ctrl(ed, "t")
    assert ed._typewriter != typewriter
    _ctrl(ed, "t")
    _ctrl(ed, "r")
    assert ed._rendered_mode


# ── zz zt zb ──


def test_zt_zz_zb_put_the_caret_line_top_middle_bottom(tmp_path):
    ed = _editor(_LINES, tmp_path)
    _type(ed, "50G")
    _type(ed, "zt")
    assert _top(ed) == 50 and _line(ed) == 50
    _type(ed, "zb")
    rows = _rows(ed)
    assert rows[-1] == 50 and _line(ed) == 50
    _type(ed, "zz")
    rows = _rows(ed)
    middle = rows[(len(rows) - 1) // 2]
    assert abs(middle - 50) <= 1 and _line(ed) == 50
    view = ed._editor.viewport().height()
    assert abs(_rect(ed, ed._editor.textCursor().position()).center().y()
               - view / 2) <= _rect(ed, 0).height()


def test_a_count_on_zt_takes_that_line(tmp_path):
    ed = _editor(_LINES, tmp_path)
    _type(ed, "30zt")
    assert (_top(ed), _line(ed)) == (30, 30)


def test_z_never_becomes_the_change_dot_repeats(tmp_path):
    ed = _editor("abcdef\n", tmp_path)
    _type(ed, "xzz.")
    assert ed._editor.toPlainText() == "cdef\n"


def test_zt_on_wrapped_prose_takes_the_caret_row_not_the_paragraph(tmp_path):
    prose = " ".join(f"word{i}" for i in range(1500))
    ed = _editor(prose, tmp_path)
    mid = len(prose) // 2
    c = ed._editor.textCursor()
    c.setPosition(mid)
    ed._editor.setTextCursor(c)
    _type(ed, "zt")
    rect = _rect(ed, mid)
    assert 0 <= rect.top() < rect.height()
    _type(ed, "H")
    pos = ed._editor.textCursor().position()
    assert 0 < pos <= mid                     # the row's start, not the block's
    assert _rect(ed, pos).top() == rect.top()
    _type(ed, "zb")
    rect = _rect(ed, pos)
    view = ed._editor.viewport().height()
    assert view - 2 * rect.height() < rect.bottom() < view
