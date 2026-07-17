"""Following a `path:line` source reference from the reading view (#37): the
chip opens the file as a read-only, monospace code page anchored on the line,
and `gb` walks back to the document, exactly like an `.md` link."""

from __future__ import annotations

import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path  # noqa: E402

import pytest  # noqa: E402

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from textli.constants import (  # noqa: E402
    FONT_FAMILY,
    READING_FONT_FAMILY,
    ZEN_MD_SRC_ANCHOR_BG,
)
from textli.editor import ZenMarkdownEditor  # noqa: E402

CODE = "".join(f"line_{i} = {i}\n" for i in range(1, 41))

DOC = """# Design

The dispatch lives in `pkg/mod.py:3` and the range `pkg/mod.py:5-7` covers
the loop. The module is `mod.py`, and a plain word like dispatch is not a
reference. See [the notes](notes.md) and [the page](page.html).
"""


@pytest.fixture
def repo(tmp_path):
    """A repo shaped like a real one: the doc sits two levels under the root
    it references, so resolution has to walk up."""
    (tmp_path / ".git").mkdir()
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "mod.py").write_text(CODE)
    (tmp_path / "mgc" / "groundwork").mkdir(parents=True)
    doc = tmp_path / "mgc" / "groundwork" / "design.md"
    doc.write_text(DOC)
    (tmp_path / "mgc" / "groundwork" / "notes.md").write_text("# Notes\n\nhi\n")
    (tmp_path / "mgc" / "groundwork" / "page.html").write_text("<p>hi</p>\n")
    return tmp_path


def _editor(doc: Path) -> ZenMarkdownEditor:
    app = QApplication.instance() or QApplication([])
    parent = QWidget()
    parent.resize(1200, 800)
    ed = ZenMarkdownEditor(parent, doc.read_text(), title="T")
    ed._parent = parent                 # keep a ref alive
    ed._file_path = doc
    # Shown, so the document layout has a real width: anything asserting about
    # wrapping or block geometry measures nothing on an unshown widget.
    parent.show()
    app.processEvents()
    ed._toggle_rendered()
    return ed


def _caret_on(ed, needle: str, offset: int = 0):
    """Park the read-view caret inside the first occurrence of ``needle``."""
    rendered = ed._rendered.document().toPlainText()
    cur = ed._rendered.textCursor()
    cur.setPosition(rendered.index(needle) + offset)
    ed._rendered.setTextCursor(cur)


def _enter(ed) -> bool:
    return ed._handle_rendered_key(
        _key(Qt.Key.Key_Return))


class _key:                              # a minimal QKeyEvent stand-in
    def __init__(self, key, mods=Qt.KeyboardModifier.NoModifier):
        self._k, self._m = key, mods

    def key(self):
        return self._k

    def modifiers(self):
        return self._m

    def text(self):
        return ""


# ── Reading the chip under the caret ─────────────────────────────────

def test_the_chip_under_the_caret_is_read_as_a_reference(repo):
    ed = _editor(repo / "mgc" / "groundwork" / "design.md")
    _caret_on(ed, "pkg/mod.py:3", 2)
    ref = ed._srcref_at_caret()
    assert ref is not None
    assert (ref.path, ref.line) == ("pkg/mod.py", 3)


def test_prose_under_the_caret_is_not_a_reference(repo):
    ed = _editor(repo / "mgc" / "groundwork" / "design.md")
    _caret_on(ed, "a plain word like dispatch", 18)
    assert ed._srcref_at_caret() is None


# ── Following it ─────────────────────────────────────────────────────

def test_enter_on_a_reference_opens_the_file_as_a_code_page(repo):
    ed = _editor(repo / "mgc" / "groundwork" / "design.md")
    _caret_on(ed, "pkg/mod.py:3", 2)
    assert _enter(ed) is True
    assert ed._source_path == repo / "pkg" / "mod.py"
    shown = ed._rendered.document().toPlainText()
    assert "line_1 = 1" in shown and "line_40 = 40" in shown
    # ...and the *document* is untouched underneath — this is a peek.
    assert ed._editor.toPlainText() == DOC
    assert ed._file_path == repo / "mgc" / "groundwork" / "design.md"


def test_the_source_page_is_monospace_and_the_document_is_not(repo):
    # D3: the face is the mode indicator — code never wears the reading serif.
    ed = _editor(repo / "mgc" / "groundwork" / "design.md")
    assert ed._rendered.font().family() == READING_FONT_FAMILY
    _caret_on(ed, "pkg/mod.py:3", 2)
    _enter(ed)
    assert ed._rendered.font().family() == FONT_FAMILY
    blocks = ed._source_blocks()
    assert blocks, "the file should render as fenced code"
    for block in blocks[:3]:
        it = block.begin()
        while not it.atEnd():
            fmt = it.fragment().charFormat()
            assert fmt.fontFamilies() == [FONT_FAMILY]
            it += 1
    ed._navigate_back()
    assert ed._rendered.font().family() == READING_FONT_FAMILY


def test_the_anchored_line_is_lifted_and_centred(repo):
    ed = _editor(repo / "mgc" / "groundwork" / "design.md")
    _caret_on(ed, "pkg/mod.py:3", 2)
    _enter(ed)
    blocks = ed._source_blocks()
    assert len(blocks) == 40                    # one block per line of the file
    assert blocks[2].text() == "line_3 = 3"     # 1-based anchor → third block
    assert ed._rendered._anchor_band == (blocks[2].position(),
                                         blocks[2].position())
    assert ed._rendered.textCursor().position() == blocks[2].position()


def test_a_range_reference_lifts_the_whole_range(repo):
    ed = _editor(repo / "mgc" / "groundwork" / "design.md")
    _caret_on(ed, "pkg/mod.py:5-7", 2)
    _enter(ed)
    blocks = ed._source_blocks()
    assert ed._rendered._anchor_band == (blocks[4].position(),
                                         blocks[6].position())


def test_a_bare_module_name_resolves_and_opens_at_the_top(repo):
    # `mod.py` — the way prose names a module — found by the repo sweep.
    ed = _editor(repo / "mgc" / "groundwork" / "design.md")
    _caret_on(ed, "The module is mod.py", len("The module is m"))
    assert _enter(ed) is True
    assert ed._source_path == repo / "pkg" / "mod.py"
    assert ed._rendered._anchor_band is None      # no anchor → no lift
    assert ed._rendered.verticalScrollBar().value() == 0


def test_an_unresolvable_reference_whispers_and_stays_put(repo):
    doc = repo / "mgc" / "groundwork" / "design.md"
    doc.write_text("See `pkg/ghost.py:9` for that.\n")
    ed = _editor(doc)
    _caret_on(ed, "pkg/ghost.py:9", 2)
    assert _enter(ed) is True                     # handled — not a fallthrough
    assert ed._source_path is None
    assert ed._nav_stack == []


# ── Coming back ──────────────────────────────────────────────────────

def test_gb_walks_back_to_the_document_where_it_was_left(repo):
    ed = _editor(repo / "mgc" / "groundwork" / "design.md")
    _caret_on(ed, "pkg/mod.py:3", 2)
    was = ed._rendered.textCursor().position()
    _enter(ed)
    ed._navigate_back()
    assert ed._source_path is None
    assert ed._rendered.textCursor().position() == was
    assert "The dispatch lives in" in ed._rendered.document().toPlainText()
    assert ed._rendered._anchor_band is None


def test_following_a_second_reference_stacks(repo):
    ed = _editor(repo / "mgc" / "groundwork" / "design.md")
    _caret_on(ed, "pkg/mod.py:3", 2)
    _enter(ed)
    assert len(ed._nav_stack) == 1
    ed._navigate_back()
    _caret_on(ed, "pkg/mod.py:5-7", 2)
    _enter(ed)
    ed._navigate_back()
    assert ed._nav_stack == []
    assert ed._source_path is None


def test_a_link_followed_from_a_source_page_returns_through_it(repo):
    # doc → source → (gb) → doc → notes.md → (gb) → doc
    ed = _editor(repo / "mgc" / "groundwork" / "design.md")
    _caret_on(ed, "pkg/mod.py:3", 2)
    _enter(ed)
    ed._follow_rendered_link("notes.md")          # from the source page
    assert ed._source_path is None
    assert ed._file_path == repo / "mgc" / "groundwork" / "notes.md"
    ed._navigate_back()                           # back onto the source page
    assert ed._source_path == repo / "pkg" / "mod.py"
    assert ed._file_path == repo / "mgc" / "groundwork" / "design.md"
    assert "line_3 = 3" in ed._rendered.document().toPlainText()
    ed._navigate_back()                           # back to the document
    assert ed._source_path is None
    assert "The dispatch lives in" in ed._rendered.document().toPlainText()


# ── What a source page refuses ───────────────────────────────────────

def test_a_source_page_refuses_to_be_annotated(repo):
    ed = _editor(repo / "mgc" / "groundwork" / "design.md")
    _caret_on(ed, "pkg/mod.py:3", 2)
    _enter(ed)
    blocks = ed._source_blocks()
    cur = ed._rendered.textCursor()
    cur.setPosition(blocks[0].position())
    cur.setPosition(blocks[0].position() + 6,
                    cur.MoveMode.KeepAnchor)
    ed._rendered.setTextCursor(cur)
    ed._comment_selection()
    ed._suggest_selection()
    assert ed._comment_field is None              # nothing authored
    assert ed._editor.toPlainText() == DOC        # the document is untouched


def test_cmd_r_does_not_leave_a_source_page_for_the_write_view(repo):
    ed = _editor(repo / "mgc" / "groundwork" / "design.md")
    _caret_on(ed, "pkg/mod.py:3", 2)
    _enter(ed)
    ed._toggle_rendered()
    assert ed._rendered_mode is True              # still reading
    assert ed._source_path == repo / "pkg" / "mod.py"


def test_the_clean_preview_is_not_offered_on_a_source_page(repo):
    ed = _editor(repo / "mgc" / "groundwork" / "design.md")
    _caret_on(ed, "pkg/mod.py:3", 2)
    _enter(ed)
    ed._toggle_preview()
    assert ed._preview is False
    assert "line_3 = 3" in ed._rendered.document().toPlainText()


def test_an_external_change_does_not_yank_the_reader_off_the_page(repo):
    doc = repo / "mgc" / "groundwork" / "design.md"
    ed = _editor(doc)
    _caret_on(ed, "pkg/mod.py:3", 2)
    _enter(ed)
    ed._reload_from_disk(DOC + "\nAn agent appended this.\n")
    assert ed._source_path == repo / "pkg" / "mod.py"
    assert "line_3 = 3" in ed._rendered.document().toPlainText()
    assert "An agent appended this." in ed._editor.toPlainText()   # buffer took it
    ed._navigate_back()
    assert "An agent appended this." in ed._rendered.document().toPlainText()


# ── Routing links by what the file is ────────────────────────────────

def test_a_link_to_a_source_file_opens_it_in_place(repo):
    doc = repo / "mgc" / "groundwork" / "design.md"
    doc.write_text("See [the module](../../pkg/mod.py).\n")
    ed = _editor(doc)
    opened = []
    ed._open_external = lambda url: opened.append(url)
    ed._follow_rendered_link("../../pkg/mod.py")
    assert ed._source_path == repo / "pkg" / "mod.py"
    assert opened == []


def test_a_link_to_a_rendered_format_still_goes_to_the_system_handler(repo):
    # page.html is text, but a *link* to it means "show me the page".
    ed = _editor(repo / "mgc" / "groundwork" / "design.md")
    opened = []
    ed._open_external = lambda url: opened.append(url)
    ed._follow_rendered_link("page.html")
    assert len(opened) == 1
    assert ed._source_path is None


# ── The page code gets: a code size, a code-shaped column ────────────

def test_the_source_page_is_sized_and_measured_for_code(repo):
    # The prose column holds ~50 columns of mono at the reading size; source is
    # written for ~80. Both the size and the column step to code while a peek
    # is up, and step back when it ends.
    wide = repo / "pkg" / "wide.py"
    wide.write_text("x = 1  # " + "y" * 66 + "\n")          # a 75-column line
    doc = repo / "mgc" / "groundwork" / "design.md"
    doc.write_text("See `pkg/wide.py:1`.\n")
    ed = _editor(doc)
    prose_card = ed._card_rect().width()
    _caret_on(ed, "pkg/wide.py:1", 2)
    _enter(ed)
    assert ed._rendered.font().pointSize() < ed._font_size      # code size
    assert ed._card_rect().width() > prose_card                 # code column
    # The line lands as written — not wrapped, not behind a scrollbar.
    doc_layout = ed._rendered.document().documentLayout()
    line = ed._source_blocks()[0]
    one_row = doc_layout.blockBoundingRect(line).height()
    row_h = ed._rendered.fontMetrics().height()
    assert 0 < one_row < 2 * row_h              # a real, single rendered row
    assert ed._rendered.horizontalScrollBar().maximum() == 0
    ed._navigate_back()
    assert ed._card_rect().width() == prose_card


def test_a_pathological_line_wraps_rather_than_hiding(repo):
    # Nothing may sit off-column: a line no page could hold wraps instead.
    (repo / "pkg" / "long.py").write_text("x = '" + "z" * 400 + "'\n")
    doc = repo / "mgc" / "groundwork" / "design.md"
    doc.write_text("See `pkg/long.py:1`.\n")
    ed = _editor(doc)
    _caret_on(ed, "pkg/long.py:1", 2)
    _enter(ed)
    assert ed._rendered.horizontalScrollBar().maximum() == 0
    line = ed._source_blocks()[0]
    rect = ed._rendered.document().documentLayout().blockBoundingRect(line)
    assert rect.height() > 3 * ed._rendered.fontMetrics().height()   # wrapped


def test_a_readers_wider_column_is_not_narrowed_by_a_peek(repo):
    ed = _editor(repo / "mgc" / "groundwork" / "design.md")
    ed._content_width = 1400
    wide_card = ed._card_rect().width()
    _caret_on(ed, "pkg/mod.py:3", 2)
    _enter(ed)
    assert ed._card_rect().width() == wide_card


# ── Opening a big file stays quick ───────────────────────────────────

def test_a_big_file_opens_without_a_stall(repo):
    """A whole file is one huge fence, which turns any per-line or per-span
    work in a render pass into a document-sized cost. Two such bugs made a
    4,500-line file take **15 seconds** to open: format merges outside an edit
    block (each settling the whole layout), and a per-span scan of every line
    (21M steps). Both are super-linear, so assert the *shape* — an 18×-bigger
    file may cost at most 18× — which is robust on a loaded machine in a way a
    millisecond budget isn't. Measured here: 5× with the fix, 45× without."""
    lines = "".join(f"def f_{i}(x):  # comment {i}\n    return x + {i}\n"
                    for i in range(1500))          # 3,000 lines
    (repo / "pkg" / "big.py").write_text(lines)
    (repo / "pkg" / "small.py").write_text(lines[:len(lines) // 20])
    doc = repo / "mgc" / "groundwork" / "design.md"
    doc.write_text("Big `pkg/big.py:2000` and small `pkg/small.py:20`.\n")
    ed = _editor(doc)

    def follow(ref: str) -> float:
        _caret_on(ed, ref, 2)
        t0 = time.perf_counter()
        _enter(ed)
        elapsed = time.perf_counter() - t0
        ed._navigate_back()
        return elapsed

    small = follow("pkg/small.py:20")               # ~164 lines
    big = follow("pkg/big.py:2000")                 # 3,000 lines — 18× more
    assert ed._source_path is None and ed._source_lines == 0    # left no state
    assert big < max(0.25, small * 20), f"big={big:.3f}s small={small:.3f}s"


# ── The whisper ──────────────────────────────────────────────────────

def test_the_whisper_names_the_file_repo_relative_with_its_anchor(repo):
    ed = _editor(repo / "mgc" / "groundwork" / "design.md")
    _caret_on(ed, "pkg/mod.py:3", 2)
    _enter(ed)
    ed._refresh_status()
    text = ed._status_label.text()
    assert "pkg/mod.py:3" in text
    assert "40 lines" in text
    assert "min left" not in text          # code isn't prose read at 220 wpm


# ── The lift paints ──────────────────────────────────────────────────

def test_the_source_page_paints(repo):
    ed = _editor(repo / "mgc" / "groundwork" / "design.md")
    _caret_on(ed, "pkg/mod.py:5-7", 2)
    _enter(ed)
    ed.setGraphicsEffect(None)             # nested painters break grab()
    img = ed._rendered.grab().toImage()
    assert not img.isNull()
    # The lifted lines wear the page color where the band would otherwise be.
    band = ed._rendered._anchor_band
    assert band is not None
    layout = ed._rendered.document().documentLayout()
    block = ed._rendered.document().findBlock(band[0])
    rect = layout.blockBoundingRect(block)
    y = int(rect.center().y() - ed._rendered.verticalScrollBar().value())
    if 0 <= y < img.height():
        assert img.pixelColor(4, y).rgb() == ZEN_MD_SRC_ANCHOR_BG.rgb()
