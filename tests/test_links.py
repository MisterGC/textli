"""Links: locate the one under the caret (pure), zen-styled rendering, and
Enter-to-follow from both views (#6)."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, Qt  # noqa: E402
from PySide6.QtGui import QKeyEvent  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from textli.constants import ZEN_MD_LINK_COLOR  # noqa: E402
from textli.editor import ZenMarkdownEditor  # noqa: E402
from textli.links import link_at  # noqa: E402

MD = ("# Title\n\n"
      "Read the [Qt docs](https://doc.qt.io) for details.\n\n"
      "Autolink <https://example.org/a> and bare https://bare.example/x.\n\n"
      "Jump to [the end](#target-section) instead.\n\n"
      "## Target Section\n\n"
      "Closing words.\n")


# ── link_at: pure text logic ──

def test_link_at_inline_link_covers_label_and_target():
    line = "Read the [Qt docs](https://doc.qt.io) for details."
    start, end = line.index("["), line.index(")") + 1
    for col in (start, start + 3, end - 1):
        assert link_at(line, col) == "https://doc.qt.io"
    assert link_at(line, start - 1) is None
    assert link_at(line, end) is None


def test_link_at_inline_link_with_title():
    line = 'See [x](https://a.b/c "the title") now.'
    assert link_at(line, line.index("[")) == "https://a.b/c"


def test_link_at_autolink_and_bare_url():
    line = "Autolink <https://example.org/a> and bare https://bare.example/x."
    assert link_at(line, line.index("<")) == "https://example.org/a"
    # trailing sentence punctuation is not part of a bare URL
    assert link_at(line, line.index("bare.example")) == "https://bare.example/x"


def test_link_at_mailto_and_anchor_targets():
    assert link_at("mail mailto:a@b.c please", 6) == "mailto:a@b.c"
    line = "Jump to [the end](#target-section) instead."
    assert link_at(line, line.index("[")) == "#target-section"


def test_link_at_plain_text_is_none():
    assert link_at("no links here at all", 5) is None


# ── Editor integration ──

def _editor(md: str = MD) -> ZenMarkdownEditor:
    QApplication.instance() or QApplication([])
    parent = QWidget()
    parent.resize(1000, 700)
    ed = ZenMarkdownEditor(parent, md, title="T")
    ed._parent = parent
    return ed


def _press_enter(ed) -> bool:
    ev = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return,
                   Qt.KeyboardModifier.NoModifier)
    return ed._handle_key(ev)


def _capture_external(ed):
    opened = []
    ed._open_external = lambda url: opened.append(url.toString())
    return opened


def test_write_view_enter_on_link_opens_browser():
    ed = _editor()
    opened = _capture_external(ed)
    cur = ed._editor.textCursor()
    cur.setPosition(ed._editor.toPlainText().index("Qt docs"))
    ed._editor.setTextCursor(cur)
    assert _press_enter(ed)
    assert opened == ["https://doc.qt.io"]


def test_write_view_enter_off_link_opens_nothing():
    ed = _editor()
    opened = _capture_external(ed)
    cur = ed._editor.textCursor()
    cur.setPosition(ed._editor.toPlainText().index("Title"))
    ed._editor.setTextCursor(cur)
    _press_enter(ed)
    assert opened == []


def test_write_view_insert_mode_keeps_enter_as_newline():
    ed = _editor()
    opened = _capture_external(ed)
    pos = ed._editor.toPlainText().index("Qt docs")
    cur = ed._editor.textCursor()
    cur.setPosition(pos)
    ed._editor.setTextCursor(cur)
    ed._vim._set_mode(type(ed._vim.mode).INSERT)
    assert _press_enter(ed)
    assert opened == []
    assert "\n" in ed._editor.toPlainText()[pos:pos + 1]


def test_write_view_enter_on_anchor_link_jumps_to_heading():
    ed = _editor()
    src = ed._editor.toPlainText()
    cur = ed._editor.textCursor()
    cur.setPosition(src.index("the end"))
    ed._editor.setTextCursor(cur)
    assert _press_enter(ed)
    block = ed._editor.textCursor().block()
    assert block.text() == "## Target Section"


def test_read_view_links_wear_the_zen_color():
    ed = _editor()
    ed._toggle_rendered()
    doc = ed._rendered.document()
    block = doc.begin()
    anchors = []
    while block.isValid():
        it = block.begin()
        while not it.atEnd():
            frag = it.fragment()
            if frag.charFormat().anchorHref():
                anchors.append(frag.charFormat())
            it += 1
        block = block.next()
    assert anchors, "rendered document should contain anchors"
    for fmt in anchors:
        assert fmt.foreground().color().name() == ZEN_MD_LINK_COLOR.name()
        assert fmt.fontUnderline()


def test_read_view_enter_on_link_opens_browser():
    ed = _editor()
    ed._toggle_rendered()
    opened = _capture_external(ed)
    pos = ed._rendered.toPlainText().index("Qt docs")
    cur = ed._rendered.textCursor()
    cur.setPosition(pos + 1)   # inside the rendered link text
    ed._rendered.setTextCursor(cur)
    assert _press_enter(ed)
    assert opened == ["https://doc.qt.io"]


def test_read_view_enter_at_link_start_probes_the_char_to_the_right():
    ed = _editor()
    ed._toggle_rendered()
    opened = _capture_external(ed)
    cur = ed._rendered.textCursor()
    cur.setPosition(ed._rendered.toPlainText().index("Qt docs"))
    ed._rendered.setTextCursor(cur)
    assert _press_enter(ed)
    assert opened == ["https://doc.qt.io"]


def test_read_view_enter_off_link_still_means_reveal_comment():
    ed = _editor("plain paragraph {==marked==}{>>note<<} here\n")
    ed._toggle_rendered()
    opened = _capture_external(ed)
    pos = ed._rendered.toPlainText().index("marked")
    cur = ed._rendered.textCursor()
    cur.setPosition(pos + 1)
    ed._rendered.setTextCursor(cur)
    assert _press_enter(ed)
    assert opened == []
    assert ed._comment_field is not None   # the comment editor opened
