"""PDF export (#47) and the palette a page is printed on (#46)."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtGui import QTextFormat  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from textli import theme  # noqa: E402
from textli.editor import ZenMarkdownEditor  # noqa: E402

MD = (
    "# A paper\n\nProse with math $E = mc^2$.\n\n"
    "```python\ndef render(page: str, count: int = 42) -> str:\n"
    "    return 1\n```\n\n"
    "A {==span==}{>>remark<<} and a {++insert++}.\n"
)


def _app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _light():
    theme.set_theme("light")
    yield
    theme.set_theme("light")


def _editor(rendered=True):
    host = QWidget()
    ed = ZenMarkdownEditor(parent=host, text=MD, title="t.md")
    if rendered:
        ed._toggle_rendered()
    return host, ed


def _fence_format(doc):
    block = doc.begin()
    while block.isValid():
        if block.blockFormat().hasProperty(
                QTextFormat.Property.BlockCodeFence):
            return block.blockFormat()
        block = block.next()
    return None


def test_export_writes_a_pdf(tmp_path):
    _app()
    host, ed = _editor()
    out = ed.export_pdf(tmp_path / "paper.pdf")
    assert out.exists() and out.stat().st_size > 1000
    assert out.read_bytes().startswith(b"%PDF")


def test_export_works_from_the_write_view_and_returns_to_it(tmp_path):
    """The export is of the *typeset* page, so it renders on the way through
    — and leaves the reader in the view they were in."""
    _app()
    host, ed = _editor(rendered=False)
    assert not ed._rendered_mode
    ed.export_pdf(tmp_path / "paper.pdf")
    assert not ed._rendered_mode
    assert (tmp_path / "paper.pdf").exists()


def test_paper_is_never_themed(tmp_path):
    """#46 — on the dark palette the body ink still comes from the view's
    stylesheet, which paper doesn't carry, so a themed band would land as a
    near-black block behind black prose."""
    _app()
    theme.set_theme("dark")
    host, ed = _editor()
    with ed._on_paper():
        fmt = _fence_format(ed._baked_print_doc())
        assert fmt.background().color() == theme.LIGHT.ZEN_MD_CODE_BLOCK_BG
    assert theme.is_dark(), "the screen palette must be restored"


def test_a_dark_reader_gets_the_same_pdf_as_a_light_one(tmp_path):
    _app()
    host, ed = _editor()
    light = ed.export_pdf(tmp_path / "light.pdf").read_bytes()

    theme.set_theme("dark")
    host2, ed2 = _editor()
    dark = ed2.export_pdf(tmp_path / "dark.pdf").read_bytes()
    assert len(dark) == len(light)


def test_long_code_lines_wrap_rather_than_lose_their_tail():
    """Qt marks fences non-breakable; the wide reading column hides it, but a
    page *cuts* the overflow instead of wrapping, silently dropping code."""
    _app()
    host, ed = _editor()
    assert _fence_format(ed._rendered.document()).nonBreakableLines() is True
    assert _fence_format(ed._baked_print_doc()).nonBreakableLines() is False


def test_export_leaves_the_document_untouched(tmp_path):
    _app()
    host, ed = _editor()
    before = ed._editor.toPlainText()
    ed.export_pdf(tmp_path / "paper.pdf")
    assert ed._editor.toPlainText() == before
