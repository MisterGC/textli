"""Read-view table styling (#18): paper-shade bold header row, thin collapsed
gridlines, cell padding — real QTextTable formats, so they also print."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QFont, QTextTable  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from textli.constants import (  # noqa: E402
    ZEN_MD_TABLE_BORDER,
    ZEN_MD_TABLE_HEADER_BG,
    ZEN_MD_TABLE_PAD,
)
from textli.editor import ZenMarkdownEditor  # noqa: E402

MD = ("# Roster\n\n"
      "| Name | Role |\n| --- | --- |\n| Ann | dev |\n| Bo | ops |\n\n"
      "after\n")


def _editor(md: str = MD) -> ZenMarkdownEditor:
    QApplication.instance() or QApplication([])
    parent = QWidget()
    parent.resize(900, 640)
    ed = ZenMarkdownEditor(parent, md, title="T")
    ed._parent = parent
    ed._toggle_rendered()
    return ed


def _table(ed):
    doc = ed._rendered.document()
    tables = [f for f in doc.rootFrame().childFrames()
              if isinstance(f, QTextTable)]
    assert len(tables) == 1
    return tables[0]


def test_table_gets_collapsed_gridlines_and_padding():
    t = _table(_editor())
    tf = t.format()
    assert tf.border() == 1
    assert tf.borderCollapse() is True
    assert tf.cellPadding() == ZEN_MD_TABLE_PAD
    assert tf.borderBrush().color() == ZEN_MD_TABLE_BORDER


def test_header_row_is_shaded_and_bold():
    t = _table(_editor())
    for col in range(t.columns()):
        cell = t.cellAt(0, col)
        assert cell.format().background().color() == ZEN_MD_TABLE_HEADER_BG
        assert cell.format().toCharFormat().fontWeight() == QFont.Weight.Bold


def test_body_rows_are_not_shaded():
    t = _table(_editor())
    body = t.cellAt(1, 0)
    assert body.format().background().color() != ZEN_MD_TABLE_HEADER_BG


def test_table_styling_survives_print_clone():
    # the print clone keeps the table formats (they're document formats, not
    # view-painting like the code band)
    ed = _editor()
    printed = ed._baked_print_doc()
    tables = [f for f in printed.rootFrame().childFrames()
              if isinstance(f, QTextTable)]
    assert len(tables) == 1
    assert tables[0].cellAt(0, 0).format().background().color() \
        == ZEN_MD_TABLE_HEADER_BG
