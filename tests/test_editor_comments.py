"""Zen reading view: inline CriticMarkup comments are stripped from the prose,
their span highlighted, and the comment body kept out of the render."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from textli import comments as md_comments  # noqa: E402
from textli.constants import ZEN_MD_COMMENT_HL  # noqa: E402
from textli.editor import ZenMarkdownEditor  # noqa: E402

MD = (
    "# Notes\n\n"
    "The {==quarterly numbers==}{>>are these pre-audit?<<} look off here.\n"
)


def _editor(text: str) -> ZenMarkdownEditor:
    QApplication.instance() or QApplication([])
    parent = QWidget()
    parent.resize(1000, 700)
    ed = ZenMarkdownEditor(parent, text, title="T")
    ed._parent = parent  # keep a ref alive
    return ed


def test_comment_body_and_markers_absent_from_render():
    ed = _editor(MD)
    ed._toggle_rendered()
    shown = ed._rendered.toPlainText()
    # span text survives, untouched
    assert "quarterly numbers" in shown
    # comment body, CriticMarkup markers, and sentinels are all gone
    assert "are these pre-audit?" not in shown
    assert "{==" not in shown and "{>>" not in shown
    assert md_comments.SENTINEL_START not in shown
    assert md_comments.SENTINEL_END not in shown


def test_span_is_highlighted():
    ed = _editor(MD)
    ed._toggle_rendered()
    doc = ed._rendered.document()
    cur = doc.find("quarterly numbers")
    assert not cur.isNull()
    # every char of the span carries the comment highlight background
    start, end = cur.selectionStart(), cur.selectionEnd()
    for pos in range(start + 1, end + 1):
        cur.setPosition(pos)
        assert cur.charFormat().background().color() == ZEN_MD_COMMENT_HL


def test_uncommented_text_is_not_highlighted():
    ed = _editor(MD)
    ed._toggle_rendered()
    doc = ed._rendered.document()
    cur = doc.find("look off here")
    assert not cur.isNull()
    cur.setPosition(cur.selectionStart() + 1)
    assert cur.charFormat().background().color() != ZEN_MD_COMMENT_HL


def test_plain_markdown_renders_unchanged():
    ed = _editor("# Heading\n\nplain text only\n")
    ed._toggle_rendered()
    assert "<h1" in ed._rendered.toHtml().lower()
    assert "plain text only" in ed._rendered.toPlainText()


def test_commented_code_block_renders_as_code():
    # Regression: a comment wrapping a whole fenced block ({==``` … ```⏎==})
    # broke the read view from that section on — the fence went unrecognized,
    # the block's pseudo-HTML content got parsed as markup and swallowed, and
    # the raw CriticMarkup leaked into the render.
    md = ("Intro.\n\n"
          "{==```\n"
          "pipeline <app-overview [jsonLink]> stage\n"
          "second diagram line\n"
          "```\n"
          "==}{>>which versions does this cover?<<}\n\n"
          "**After** the block.\n")
    ed = _editor(md)
    ed._toggle_rendered()
    shown = ed._rendered.toPlainText()
    # block content is literal code — the pseudo-HTML tag survives as text
    assert "pipeline <app-overview [jsonLink]> stage" in shown
    assert "After the block." in shown
    assert "{==" not in shown and "{>>" not in shown
    assert "which versions" not in shown          # body hidden as usual
    assert len(ed._rendered_comments) == 1
    # the highlight covers the code content
    start, end, _c = ed._rendered_comments[0]
    assert "second diagram line" in shown[start:end]


def test_document_with_comment_lays_out_completely():
    # Regression: any mutation after setMarkdown (the comment formats and
    # sentinel deletions) can corrupt Qt's incremental layout — it then
    # permanently believes layout is finished while most blocks have no line
    # layouts, and the read view paints *blank* past the stuck point no matter
    # how far it is scrolled (hit the wild on a long doc with one comment and
    # a code block: everything after ~one viewport was invisible). The settle
    # now force-relays the whole document, so every block must end up with a
    # real line layout.
    md = ("# Top\n\nIntro {==with a comment==}{>>check<<} here.\n\n" +
          "\n\n".join(f"Paragraph {i} " + "word " * 30 for i in range(120)))
    QApplication.instance() or QApplication([])
    parent = QWidget()
    parent.resize(1000, 700)
    parent.show()          # line layouts only exist for shown widgets
    ed = ZenMarkdownEditor(parent, md, title="T")
    ed._parent = parent
    ed._toggle_rendered()
    doc = ed._rendered.document()
    block = doc.firstBlock()
    unlaid = []
    while block.isValid():
        if block.text().strip() and block.layout().lineCount() == 0:
            unlaid.append(block.blockNumber())
        block = block.next()
    assert unlaid == []
