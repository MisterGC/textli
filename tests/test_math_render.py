"""Read-view math rendering: pandoc math becomes typeset formula images,
prose dollars and code stay untouched, broken TeX falls back to raw text."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from textli.editor import ZenMarkdownEditor, _MATH_SCHEME  # noqa: E402

OBJ = "￼"   # Qt's object-replacement char — an inline image in the doc


def _editor(md: str) -> ZenMarkdownEditor:
    QApplication.instance() or QApplication([])
    parent = QWidget()
    parent.resize(1000, 700)
    ed = ZenMarkdownEditor(parent, md, title="m")
    ed._parent = parent  # keep a ref alive
    return ed


def _rendered_text(ed: ZenMarkdownEditor) -> str:
    ed._toggle_rendered()
    return ed._rendered.document().toPlainText()


def _math_images(ed: ZenMarkdownEditor) -> list[str]:
    doc = ed._rendered.document()
    names = []
    block = doc.begin()
    while block.isValid():
        it = block.begin()
        while not it.atEnd():
            cf = it.fragment().charFormat()
            if cf.isImageFormat():
                name = cf.toImageFormat().name()
                if name.startswith(f"{_MATH_SCHEME}://"):
                    names.append(name)
            it += 1
        block = block.next()
    return names


def test_inline_and_display_math_become_images():
    ed = _editor("inline $E = mc^2$ and display:\n\n$$\\int_0^1 x\\,dx$$\n")
    text = _rendered_text(ed)
    assert "$" not in text          # no raw TeX survives
    assert text.count(OBJ) == 2
    assert len(_math_images(ed)) == 2


def test_prose_dollars_and_code_render_unchanged():
    md = ("it costs $5 and $10 in total, `price = $x$` in code\n\n"
          "```sh\necho $HOME $$\n```\n")
    ed = _editor(md)
    text = _rendered_text(ed)
    assert _math_images(ed) == []
    assert "costs $5 and $10" in text
    assert "price = $x$" in text
    assert "echo $HOME $$" in text


def test_no_math_render_is_untouched_by_the_math_pass():
    md = "# Title\n\nPlain prose, a `chip`, and **bold**.\n"
    ed = _editor(md)
    out, maths = ed._prepare_math(md)
    assert out == md and maths == {}


def test_pathological_render_is_rejected_not_page_wrecking():
    # A bare \lVert makes ziamath stretch the delimiter absurdly (~125 em).
    # The renderer must either produce a sane image or refuse (fallback) —
    # never hand the page a glyph taller than any plausible formula.
    from textli import mathrender
    r = mathrender.render(r"\lVert x \rVert_2", display=True, px_size=16,
                          color="#403A30", dpr=1.0)
    assert r is None or r.image.height() <= 50 * 16


def test_broken_formula_falls_back_to_raw_tex():
    ed = _editor("a broken $\\frac{oops$ formula\n")
    text = _rendered_text(ed)
    assert _math_images(ed) == []
    assert "$\\frac{oops$" in text   # raw TeX shown (chip-styled), page intact


def test_math_inside_comment_span_still_renders():
    ed = _editor("see {==the $E=mc^2$ term==}{>>units?<<} here\n")
    _rendered_text(ed)
    assert len(_math_images(ed)) == 1
    # The comment survives as a rendered span, math image inside it.
    assert len(ed._rendered_comments) == 1


def test_preview_mode_renders_math_too():
    ed = _editor("with {++$a^2$ added++} suggestion\n")
    ed._toggle_rendered()
    ed._toggle_preview()
    assert len(_math_images(ed)) == 1


def test_display_math_paragraph_is_centered():
    from PySide6.QtCore import Qt
    ed = _editor("above\n\n$$e^{i\\pi} + 1 = 0$$\n\nbelow\n")
    ed._toggle_rendered()
    doc = ed._rendered.document()
    block = doc.begin()
    found = False
    while block.isValid():
        if OBJ in block.text():
            assert block.blockFormat().alignment() & Qt.AlignmentFlag.AlignHCenter
            found = True
        block = block.next()
    assert found
