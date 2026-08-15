"""An image marked by the caret or the selection keeps its own pixels and
gets a frame instead of a wash (#61)."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtGui import QColor, QImage, QTextCursor  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from textli import theme  # noqa: E402
from textli.editor import ZenMarkdownEditor  # noqa: E402

INK = "#cc4422"          # the test picture, a colour nothing else on the page uses


@pytest.fixture
def reader(tmp_path):
    QApplication.instance() or QApplication([])
    pic = QImage(1200, 600, QImage.Format.Format_RGB32)
    pic.fill(QColor(INK))
    pic.save(str(tmp_path / "pic.png"))
    md = "# T\n\nBefore.\n\n![pic](pic.png)\n\nAfter.\n"
    note = tmp_path / "n.md"
    note.write_text(md, encoding="utf-8")
    host = QWidget()
    host.resize(1200, 900)
    ed = ZenMarkdownEditor(host, md, title="T", file_path=note,
                           start_in_read=True)
    ed.resize(1200, 900)
    host.show()
    ed._opacity.setOpacity(1.0)
    ed._rendered.setFocus()
    ed._host = host
    app = QApplication.instance()
    for _ in range(3):
        app.processEvents()
        ed._refit_rendered()
        app.processEvents()
    return ed


def _image_pos(ed) -> int:
    doc = ed._rendered.document()
    block = doc.begin()
    while block.isValid():
        it = block.begin()
        while not it.atEnd():
            if it.fragment().charFormat().isImageFormat():
                return it.fragment().position()
            it += 1
        block = block.next()
    raise AssertionError("no image fragment")


def _box(ed):
    """The picture's bounding box on screen, found by its own colour."""
    QApplication.instance().processEvents()
    img = ed._rendered.viewport().grab().toImage()
    pts = [(x, y)
           for y in range(0, img.height(), 2)
           for x in range(0, img.width(), 4)
           if QColor(img.pixel(x, y)).name() == INK]
    assert pts, "the picture is not on screen"
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def _survey(ed, box):
    """(centre colour, share of true pixels, colour just above the picture)."""
    QApplication.instance().processEvents()
    img = ed._rendered.viewport().grab().toImage()
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    cells = [(x, y) for y in range(y0, y1, 2) for x in range(x0, x1, 4)]
    true = sum(1 for x, y in cells if QColor(img.pixel(x, y)).name() == INK)
    return (QColor(img.pixel(cx, cy)).name(),
            true / max(len(cells), 1),
            QColor(img.pixel(cx, max(0, y0 - 2))).name())


def _put_caret(ed, pos):
    cur = ed._rendered.textCursor()
    cur.setPosition(pos)
    ed._rendered.setTextCursor(cur)


def _select(ed, pos, length=1):
    cur = ed._rendered.textCursor()
    cur.setPosition(pos)
    cur.setPosition(pos + length, QTextCursor.MoveMode.KeepAnchor)
    ed._rendered.setTextCursor(cur)


# ── the picture keeps its pixels ──

def test_the_caret_no_longer_flattens_the_image(reader):
    """The block caret fills the glyph cell under it, and an image *is* one
    glyph — so the cell was the whole picture."""
    box = _box(reader)
    _put_caret(reader, _image_pos(reader))
    centre, share, _ = _survey(reader, box)
    assert centre == INK
    assert share == 1.0


def test_selecting_the_image_no_longer_flattens_it(reader):
    box = _box(reader)
    _select(reader, _image_pos(reader))
    centre, share, _ = _survey(reader, box)
    assert centre == INK
    assert share == 1.0


# ── ...and gains a frame saying so ──

def test_the_caret_frames_the_image_in_the_caret_colour(reader):
    box = _box(reader)
    _put_caret(reader, _image_pos(reader))
    _, _, above = _survey(reader, box)
    expected = QColor(theme.ZEN_MD_CARET)
    expected.setAlpha(255)
    assert above == expected.name()


def test_a_selected_image_is_framed_in_the_selection_colour(reader):
    box = _box(reader)
    _select(reader, _image_pos(reader))
    _, _, above = _survey(reader, box)
    assert above == theme.ZEN_SELECTION_BG.name()


def test_the_frame_is_opaque_even_though_the_caret_wash_is_not(reader):
    """``ZEN_MD_CARET`` is translucent because it covers a whole glyph cell;
    at that alpha a 2px stroke would barely register."""
    assert theme.ZEN_MD_CARET.alpha() < 255
    box = _box(reader)
    _put_caret(reader, _image_pos(reader))
    _, _, above = _survey(reader, box)
    assert QColor(above) == QColor(theme.ZEN_MD_CARET.rgb())   # alpha dropped


# ── an unmarked image is left completely alone ──

def test_an_unmarked_image_gets_no_frame(reader):
    box = _box(reader)
    _put_caret(reader, 0)
    centre, share, above = _survey(reader, box)
    assert centre == INK
    assert share == 1.0
    expected = QColor(theme.ZEN_MD_CARET)
    expected.setAlpha(255)
    assert above not in (expected.name(), theme.ZEN_SELECTION_BG.name())


# ── text is untouched ──

def test_text_keeps_its_wash(reader):
    """The wash reads well over text — it tints the paper between letters
    rather than covering content — and none of this touches it."""
    doc = reader._rendered.document()
    block = doc.begin()
    target = None
    while block.isValid():
        if "Before." in block.text():
            target = block.position()
            break
        block = block.next()
    assert target is not None
    _select(reader, target, len("Before."))
    QApplication.instance().processEvents()
    img = reader._rendered.viewport().grab().toImage()
    layout = doc.documentLayout()
    rect = layout.blockBoundingRect(doc.findBlock(target))
    y = int(rect.center().y() - reader._rendered.verticalScrollBar().value())
    row = [QColor(img.pixel(x, y)).name()
           for x in range(4, 200, 2) if 0 <= y < img.height()]
    assert theme.ZEN_SELECTION_BG.name() in row, "selected text lost its wash"


def test_the_caret_still_washes_a_plain_glyph(reader):
    """Only images are exempt — the soft block caret over a letter stays."""
    assert reader._rendered._caret_on_image() is False
    _put_caret(reader, _image_pos(reader))
    assert reader._rendered._caret_on_image() is True
