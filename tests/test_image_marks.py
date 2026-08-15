"""An image marked by the caret or the selection keeps its own pixels and
gets corner brackets instead of a wash (#61)."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtCore import QPointF  # noqa: E402
from PySide6.QtGui import QColor, QImage, QTextCursor  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from textli import theme  # noqa: E402
from textli.editor import ZenMarkdownEditor, _MARK_INSET  # noqa: E402

INK = "#cc4422"          # the test picture — a colour nothing else on the page uses


def _caret_ink() -> str:
    c = QColor(theme.ZEN_MD_CARET)
    c.setAlpha(255)
    return c.name()


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


def _shot(ed):
    QApplication.instance().processEvents()
    return ed._rendered.viewport().grab().toImage()


def _box(ed):
    """The picture's exact bounding box on screen, found by its own colour.

    Seeded coarsely then walked out pixel by pixel along one row and one
    column. Sampling every other pixel instead would put the edge up to a
    pixel off, which is enough to make a bracket sitting flush *on* the edge
    look as though it hangs outside.
    """
    img = _shot(ed)
    seed = next(((x, y)
                 for y in range(0, img.height(), 4)
                 for x in range(0, img.width(), 4)
                 if QColor(img.pixel(x, y)).name() == INK), None)
    assert seed is not None, "the picture is not on screen"
    sx, sy = seed

    def walk(x, y, dx, dy):
        while True:
            nx, ny = x + dx, y + dy
            if not (0 <= nx < img.width() and 0 <= ny < img.height()):
                return x, y
            if QColor(img.pixel(nx, ny)).name() != INK:
                return x, y
            x, y = nx, ny

    x0 = walk(sx, sy, -1, 0)[0]
    x1 = walk(sx, sy, 1, 0)[0]
    y0 = walk(sx, sy, 0, -1)[1]
    y1 = walk(sx, sy, 0, 1)[1]
    return x0, y0, x1, y1


def _put_caret(ed, pos):
    cur = ed._rendered.textCursor()
    cur.setPosition(pos)
    ed._rendered.setTextCursor(cur)


def _select(ed, pos, length=1):
    cur = ed._rendered.textCursor()
    cur.setPosition(pos)
    cur.setPosition(pos + length, QTextCursor.MoveMode.KeepAnchor)
    ed._rendered.setTextCursor(cur)


def _true_share(ed, box) -> float:
    img = _shot(ed)
    x0, y0, x1, y1 = box
    cells = [(x, y) for y in range(y0, y1, 2) for x in range(x0, x1, 4)]
    true = sum(1 for x, y in cells if QColor(img.pixel(x, y)).name() == INK)
    return true / max(len(cells), 1)


def _mark_pixels(ed, box, colour) -> tuple[int, int]:
    """(mark pixels inside the picture, mark pixels in a band just outside)."""
    img = _shot(ed)
    x0, y0, x1, y1 = box
    inside = sum(1 for y in range(y0, y1) for x in range(x0, x1, 2)
                 if QColor(img.pixel(x, y)).name() == colour)
    outside = 0
    for y in range(max(0, y0 - 6), min(img.height(), y1 + 7)):
        for x in (list(range(max(0, x0 - 6), x0))
                  + list(range(x1 + 1, min(img.width(), x1 + 7)))):
            if QColor(img.pixel(x, y)).name() == colour:
                outside += 1
    for x in range(x0, x1, 2):
        for y in (list(range(max(0, y0 - 6), y0))
                  + list(range(y1 + 1, min(img.height(), y1 + 7)))):
            if QColor(img.pixel(x, y)).name() == colour:
                outside += 1
    return inside, outside


# ── the picture keeps its own pixels ──

def test_the_caret_no_longer_flattens_the_image(reader):
    """The block caret fills the glyph cell under it, and an image *is* one
    glyph — so the cell used to be the whole picture."""
    box = _box(reader)
    _put_caret(reader, _image_pos(reader))
    img = _shot(reader)
    cx, cy = (box[0] + box[2]) // 2, (box[1] + box[3]) // 2
    assert QColor(img.pixel(cx, cy)).name() == INK
    assert _true_share(reader, box) > 0.95        # only the brackets sit on it


def test_selecting_the_image_no_longer_flattens_it(reader):
    box = _box(reader)
    _select(reader, _image_pos(reader))
    img = _shot(reader)
    cx, cy = (box[0] + box[2]) // 2, (box[1] + box[3]) // 2
    assert QColor(img.pixel(cx, cy)).name() == INK
    assert _true_share(reader, box) > 0.95


# ── ...and gets brackets inside it saying so ──

def test_the_caret_marks_the_image_from_the_inside(reader):
    """Brackets sit *inside* the picture: an outline hung outside has to line
    up with the drawn edge exactly or it reads as broken, and it claims layout
    room the image never reserved."""
    box = _box(reader)
    _put_caret(reader, _image_pos(reader))
    inside, outside = _mark_pixels(reader, box, _caret_ink())
    assert inside > 0
    assert outside == 0


def test_a_selected_image_is_marked_in_the_selection_colour(reader):
    box = _box(reader)
    _select(reader, _image_pos(reader))
    inside, _ = _mark_pixels(reader, box, theme.ZEN_SELECTION_BG.name())
    assert inside > 0


def test_the_marks_are_at_the_corners_not_along_the_edges(reader):
    box = _box(reader)
    _put_caret(reader, _image_pos(reader))
    img = _shot(reader)
    x0, y0, x1, y1 = box
    ink = _caret_ink()
    probe = int(_MARK_INSET) + 2

    def band(xs, ys):
        return sum(1 for x in xs for y in ys
                   if QColor(img.pixel(x, y)).name() == ink)

    corner = band(range(x0, x0 + 20), range(y0, y0 + 20))
    mid_top = band(range((x0 + x1) // 2 - 20, (x0 + x1) // 2 + 20),
                   range(y0, y0 + probe + 4))
    mid_left = band(range(x0, x0 + probe + 4),
                    range((y0 + y1) // 2 - 20, (y0 + y1) // 2 + 20))
    assert corner > 0, "no bracket at the top-left corner"
    assert mid_top == 0, "the mark runs along the top edge — that's a frame"
    assert mid_left == 0, "the mark runs down the left edge — that's a frame"


def test_the_mark_is_opaque_even_though_the_caret_wash_is_not(reader):
    """``ZEN_MD_CARET`` is translucent because it covers a whole glyph cell;
    at that alpha a thin bracket would barely register."""
    assert theme.ZEN_MD_CARET.alpha() < 255
    box = _box(reader)
    _put_caret(reader, _image_pos(reader))
    inside, _ = _mark_pixels(reader, box, _caret_ink())
    assert inside > 0


# ── an unmarked image is left completely alone ──

def test_an_unmarked_image_gets_no_marks(reader):
    box = _box(reader)
    _put_caret(reader, 0)
    assert _true_share(reader, box) == 1.0
    assert _mark_pixels(reader, box, _caret_ink()) == (0, 0)


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
    img = _shot(reader)
    rect = doc.documentLayout().blockBoundingRect(doc.findBlock(target))
    y = int(rect.center().y() - reader._rendered.verticalScrollBar().value())
    row = [QColor(img.pixel(x, y)).name() for x in range(4, 200, 2)]
    assert theme.ZEN_SELECTION_BG.name() in row, "selected text lost its wash"


def test_only_images_are_exempt_from_the_caret_wash(reader):
    assert reader._rendered._caret_on_image() is False
    _put_caret(reader, _image_pos(reader))
    assert reader._rendered._caret_on_image() is True


# ── a rendered formula is text, not a picture (#61) ──

def _kinds(tmp_path):
    """An editor holding one of each image kind, and their fragment positions
    by resource scheme."""
    QApplication.instance() or QApplication([])
    pic = QImage(1200, 600, QImage.Format.Format_RGB32)
    pic.fill(QColor(INK))
    pic.save(str(tmp_path / "pic.png"))
    (tmp_path / "a.grafli").write_text("node A 'x'\nnode B 'y'\nA -> B\n",
                                       encoding="utf-8")
    md = ("# T\n\nA formula $E = mc^2$ inline.\n\n![pic](pic.png)\n\n"
          "<!-- chart: bar x=x -->\n| x | y |\n|---|---|\n| a | 1 |\n| b | 3 |\n\n"
          "![](a.grafli)\n")
    note = tmp_path / "n.md"
    note.write_text(md, encoding="utf-8")
    host = QWidget()
    host.resize(1200, 2200)
    ed = ZenMarkdownEditor(host, md, title="T", file_path=note,
                           start_in_read=True)
    ed.resize(1200, 2200)
    host.show()
    ed._opacity.setOpacity(1.0)
    ed._rendered.setFocus()
    ed._host = host
    app = QApplication.instance()
    for _ in range(3):
        app.processEvents()
        ed._refit_rendered()
        app.processEvents()
    found = {}
    doc = ed._rendered.document()
    block = doc.begin()
    while block.isValid():
        it = block.begin()
        while not it.atEnd():
            frag = it.fragment()
            fmt = frag.charFormat()
            if fmt.isImageFormat():
                name = fmt.toImageFormat().name()
                key = name.split("://")[0] if "://" in name else "file"
                found[key] = frag.position()
            it += 1
        block = block.next()
    return ed, found


def test_a_rendered_formula_keeps_the_wash(tmp_path):
    """A formula is typeset text that happens to arrive as a bitmap — it sits
    in a sentence, it is small, and the wash reads over it exactly as it reads
    over the letters around it."""
    ed, found = _kinds(tmp_path)
    assert "textli-math" in found, "fixture produced no formula"
    _put_caret(ed, found["textli-math"])
    assert ed._rendered._caret_on_image() is False      # so the caret washes it
    marks = ed._rendered._marked_image_rects(
        ed._rendered.document(), ed._rendered.document().documentLayout(),
        QPointF(0, 0))
    assert marks == []


@pytest.mark.parametrize("kind", ["file", "textli-chart", "textli-grafli"])
def test_pictures_get_the_brackets(tmp_path, kind):
    """A screenshot, a chart and a diagram all have detail to inspect, and a
    wash flattens them the same way."""
    ed, found = _kinds(tmp_path)
    assert kind in found, f"fixture produced no {kind}"
    _put_caret(ed, found[kind])
    assert ed._rendered._caret_on_image() is True
    marks = ed._rendered._marked_image_rects(
        ed._rendered.document(), ed._rendered.document().documentLayout(),
        QPointF(0, 0))
    assert len(marks) == 1
