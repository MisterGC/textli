"""The `/` search overlay: key routing in both views, live hit selection,
jump-on-Enter, Esc position restore, and n/N navigation with wrap."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, Qt  # noqa: E402
from PySide6.QtGui import QKeyEvent  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from textli.constants import ZEN_SEARCH_CURRENT, ZEN_SEARCH_HIT  # noqa: E402
from textli.editor import ZenMarkdownEditor  # noqa: E402
from textli.vim import VimMode  # noqa: E402

MD = ("# Title\n\n"
      "alpha paragraph mentioning pipeline here.\n\n"
      "beta paragraph, nothing else.\n\n"
      "gamma paragraph mentioning pipeline again.\n")


def _ev(key, text="", shift=False):
    mods = Qt.KeyboardModifier.ShiftModifier if shift \
        else Qt.KeyboardModifier.NoModifier
    return QKeyEvent(QEvent.Type.KeyPress, key, mods, text, False, 1)


def _editor(text=MD, show=True) -> ZenMarkdownEditor:
    QApplication.instance() or QApplication([])
    parent = QWidget()
    parent.resize(900, 600)
    if show:
        parent.show()
    ed = ZenMarkdownEditor(parent, text, title="t")
    ed._parent = parent
    return ed


# ── opening ──

def test_slash_opens_search_in_write_normal_mode():
    ed = _editor()
    assert ed._handle_key(_ev(Qt.Key.Key_Slash, "/")) is True
    assert ed._search_overlay is not None


def test_slash_types_literally_in_insert_mode():
    ed = _editor(text="")
    ed._vim.handle_key(_ev(Qt.Key.Key_I, "i"))
    assert ed._vim.mode == VimMode.INSERT
    assert ed._handle_key(_ev(Qt.Key.Key_Slash, "/")) is False  # falls through
    assert ed._search_overlay is None


def test_slash_opens_search_in_read_view():
    ed = _editor()
    ed._toggle_rendered()
    assert ed._handle_rendered_key(_ev(Qt.Key.Key_Slash, "/")) is True
    assert ed._search_overlay is not None


# ── the overlay ──

def test_typing_lists_hits_in_document_order():
    ed = _editor()
    ed._open_search()
    ov = ed._search_overlay
    ov._input.setText("pipeline")
    assert [h.line_no for h in ov.hits] == [2, 6]
    assert ov._sel == 0


def test_enter_jumps_and_highlights_and_keeps_query():
    ed = _editor()
    ed._open_search()
    ov = ed._search_overlay
    ov._input.setText("pipeline")
    first_hit = ov.hits[0]
    ov._handle_key(_ev(Qt.Key.Key_Return))
    assert ed._search_overlay is None
    assert ed._search_query == "pipeline"
    assert ed._editor.textCursor().position() == first_hit.start
    sels = ed._editor.extraSelections()
    assert len(sels) == 2
    colors = {s.format.background().color().rgba() for s in sels}
    assert ZEN_SEARCH_CURRENT.rgba() in colors
    assert ZEN_SEARCH_HIT.rgba() in colors


def test_selection_moves_and_previews():
    ed = _editor()
    ed._open_search()
    ov = ed._search_overlay
    ov._input.setText("pipeline")
    ov._handle_key(_ev(Qt.Key.Key_Down))
    assert ov._sel == 1
    # live preview parked the caret on the selected hit
    assert ed._editor.textCursor().position() == ov.hits[1].start


def test_escape_restores_position_and_clears_highlights():
    ed = _editor()
    cur = ed._editor.textCursor()
    cur.setPosition(5)
    ed._editor.setTextCursor(cur)
    ed._open_search()
    ov = ed._search_overlay
    ov._input.setText("pipeline")        # preview moved the caret
    ov._handle_key(_ev(Qt.Key.Key_Escape))
    assert ed._search_overlay is None
    assert ed._editor.textCursor().position() == 5
    assert ed._editor.extraSelections() == []


# ── n / N ──

def test_n_and_shift_n_step_with_wrap():
    ed = _editor()
    ed._open_search()
    ov = ed._search_overlay
    ov._input.setText("pipeline")
    h0, h1 = ov.hits
    ov._handle_key(_ev(Qt.Key.Key_Return))          # at hit 0
    ed._handle_key(_ev(Qt.Key.Key_N, "n"))
    assert ed._editor.textCursor().position() == h1.start
    ed._handle_key(_ev(Qt.Key.Key_N, "n"))          # wraps forward
    assert ed._editor.textCursor().position() == h0.start
    ed._handle_key(_ev(Qt.Key.Key_N, "N", shift=True))   # wraps backward
    assert ed._editor.textCursor().position() == h1.start


def test_query_survives_view_toggle():
    ed = _editor()
    ed._open_search()
    ov = ed._search_overlay
    ov._input.setText("pipeline")
    ov._handle_key(_ev(Qt.Key.Key_Return))
    ed._toggle_rendered()
    assert ed._rendered.extraSelections() == []     # stale offsets cleared
    ed._handle_rendered_key(_ev(Qt.Key.Key_N, "n"))
    pos = ed._rendered.textCursor().position()
    shown = ed._rendered.toPlainText()
    assert shown[pos:pos + 5] in ("alpha", "gamma")  # on a hit line
    assert ed._rendered.extraSelections() != []


def test_n_without_query_is_a_noop():
    ed = _editor()
    before = ed._editor.textCursor().position()
    ed._handle_key(_ev(Qt.Key.Key_N, "n"))
    assert ed._editor.textCursor().position() == before
