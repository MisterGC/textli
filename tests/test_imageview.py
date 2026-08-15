"""Full-page image inspector in the reading view (#59): `↵` expands, `Esc`
puts the page back — and must not fall through to save-and-close."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path  # noqa: E402

import pytest  # noqa: E402
from PySide6.QtCore import QEvent, QRectF, Qt  # noqa: E402
from PySide6.QtGui import QImage, QKeyEvent, QPixmap  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from textli.editor import ZenMarkdownEditor  # noqa: E402
from textli.imageview import (  # noqa: E402
    ImageInspector, _CLOSE_MS, _OPEN_MS, _fit, _lerp,
)

PIC_W, PIC_H = 1600, 900


@pytest.fixture
def reader(tmp_path):
    """A reading-view editor on a document holding one 1600x900 picture."""
    QApplication.instance() or QApplication([])
    QImage(PIC_W, PIC_H, QImage.Format.Format_RGB32).save(
        str(tmp_path / "pic.png"))
    md = ("# Title\n\nBefore the picture.\n\n"
          "![a picture](pic.png)\n\nAfter the picture.\n")
    note = tmp_path / "n.md"
    note.write_text(md, encoding="utf-8")
    host = QWidget()
    host.resize(1200, 800)
    ed = ZenMarkdownEditor(host, md, title="T", file_path=note,
                           start_in_read=True)
    ed.resize(1200, 800)
    host.show()
    ed._opacity.setOpacity(1.0)      # the fade-in leaves it painting nothing
    ed._host = host                  # keep a ref alive
    return ed


def _press(ed, key):
    return ed._handle_key(
        QKeyEvent(QEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier))


def _caret_to(ed, text: str):
    """Park the read-view caret in the first block containing ``text`` — or,
    for the image, on the image fragment itself."""
    doc = ed._rendered.document()
    block = doc.begin()
    while block.isValid():
        it = block.begin()
        while not it.atEnd():
            frag = it.fragment()
            hit = (frag.charFormat().isImageFormat() if text == "<image>"
                   else text in frag.text())
            if hit:
                cur = ed._rendered.textCursor()
                cur.setPosition(frag.position())
                ed._rendered.setTextCursor(cur)
                return frag.position()
            it += 1
        block = block.next()
    raise AssertionError(f"no fragment for {text!r}")


# ── opening ──

def test_enter_on_an_image_covers_the_window(reader):
    """The window, not the card. Charts and diagrams are rasterised at the
    column width and the card is only ~130px wider, so expanding into the
    card alone would enlarge a diagram by a tenth."""
    _caret_to(reader, "<image>")
    assert _press(reader, Qt.Key.Key_Return) is True
    view = reader._image_view
    assert view.is_active()
    assert view.geometry() == reader.rect()
    assert view.geometry().width() > reader._card_rect().width()


def test_the_expanded_image_is_the_full_resolution_original(reader):
    """The page draws the picture at the prose column's width; expanding it
    has to go back to what is on disk or there is nothing to look closer at."""
    _caret_to(reader, "<image>")
    pixmap = reader._image_pixmap_at_caret()
    assert pixmap is not None
    assert pixmap.size().width() == PIC_W
    assert pixmap.size().height() == PIC_H


def test_enter_anywhere_in_the_image_block_works(reader):
    """An image alone in a paragraph is one object-replacement character, so
    the caret is beside it as often as on it."""
    pos = _caret_to(reader, "<image>")
    cur = reader._rendered.textCursor()
    cur.setPosition(pos + 1)
    reader._rendered.setTextCursor(cur)
    assert _press(reader, Qt.Key.Key_Return) is True
    assert reader._image_view.is_active()


def test_enter_on_ordinary_prose_does_not_open_it(reader):
    _caret_to(reader, "Before the picture")
    _press(reader, Qt.Key.Key_Return)
    assert reader._image_view is None or not reader._image_view.is_active()


def test_the_write_view_has_no_inspector(reader):
    reader._toggle_rendered()                 # back to the source
    assert reader._rendered_mode is False
    assert reader._image_pixmap_at_caret() is None


# ── closing ──

def test_escape_closes_it_and_returns_focus(reader):
    _caret_to(reader, "<image>")
    _press(reader, Qt.Key.Key_Return)
    assert _press(reader, Qt.Key.Key_Escape) is True
    assert not reader._image_view.is_active()
    assert reader._rendered.hasFocus()


def test_enter_closes_it_too(reader):
    _caret_to(reader, "<image>")
    _press(reader, Qt.Key.Key_Return)
    _press(reader, Qt.Key.Key_Return)
    assert not reader._image_view.is_active()


def test_escape_does_not_reach_save_and_close(reader, monkeypatch):
    """The guard this feature most needs: `Esc` in the reading view saves and
    closes the editor, and an expanded image has to swallow it first — for the
    whole of the closing tween as well, since that is still on screen (#64)."""
    from PySide6.QtTest import QTest
    closed = []
    monkeypatch.setattr(ZenMarkdownEditor, "_close_save",
                        lambda self: closed.append("save"))
    monkeypatch.setattr(ZenMarkdownEditor, "_close_cancel",
                        lambda self: closed.append("cancel"))
    _caret_to(reader, "<image>")
    _press(reader, Qt.Key.Key_Return)
    _press(reader, Qt.Key.Key_Escape)
    assert closed == []                        # swallowed by the inspector
    _press(reader, Qt.Key.Key_Escape)          # still closing — still swallowed
    assert closed == []
    QTest.qWait(_CLOSE_MS + 150)               # let it land
    _press(reader, Qt.Key.Key_Escape)          # now it reaches the editor
    assert closed == ["save"]


def test_other_keys_are_swallowed_while_it_is_up(reader):
    """One picture is on screen; a stray key doing something to the document
    underneath would be a surprise."""
    _caret_to(reader, "<image>")
    _press(reader, Qt.Key.Key_Return)
    before = reader._rendered.textCursor().position()
    assert _press(reader, Qt.Key.Key_J) is True
    assert reader._rendered.textCursor().position() == before
    assert reader._image_view.is_active()


# ── it follows the card ──

def test_it_follows_the_window_on_resize(reader):
    _caret_to(reader, "<image>")
    _press(reader, Qt.Key.Key_Return)
    reader._host.resize(900, 600)
    reader.resize(900, 600)
    assert reader._image_view.geometry() == reader.rect()


# ── fitting ──

def test_fit_scales_up_and_keeps_the_aspect_ratio():
    QApplication.instance() or QApplication([])
    frame = QRectF(0, 0, 1000, 1000)
    out = _fit(QPixmap(400, 200), frame)          # 2.5x — under the cap
    assert out.width() == pytest.approx(1000)     # scaling up is the point
    assert out.height() == pytest.approx(500)
    assert out.center() == frame.center()


def test_fit_refuses_to_blow_a_small_bitmap_up_into_mush():
    """Inline math can be under a hundred pixels wide, and charts, diagrams
    and math have no original to go back to — past a point a bigger picture
    is only a bigger blur."""
    QApplication.instance() or QApplication([])
    out = _fit(QPixmap(80, 20), QRectF(0, 0, 1200, 800))
    assert out.width() == pytest.approx(320)      # 4x, not 1200
    assert out.height() == pytest.approx(80)


def test_the_cap_never_binds_on_column_width_content():
    """A diagram drawn at the prose column's width against a maximised
    window is well under the cap, so the guard costs it nothing."""
    QApplication.instance() or QApplication([])
    out = _fit(QPixmap(700, 400), QRectF(0, 0, 1840, 1000))
    assert out.width() == pytest.approx(1750)     # 2.5x, uncapped
    assert out.width() / 700 < 4.0


def test_fit_is_bounded_by_the_tighter_side():
    QApplication.instance() or QApplication([])
    out = _fit(QPixmap(200, 100), QRectF(0, 0, 1000, 300))
    assert out.height() == pytest.approx(300)
    assert out.width() == pytest.approx(600)


def test_fit_reads_a_retina_pixmap_at_its_logical_size():
    """A 2x pixmap is the same picture at twice the pixels — measuring it in
    device pixels would show it at half the size it should be."""
    QApplication.instance() or QApplication([])
    plain = QPixmap(200, 100)
    retina = QPixmap(400, 200)
    retina.setDevicePixelRatio(2.0)
    frame = QRectF(0, 0, 1000, 1000)
    assert _fit(retina, frame) == _fit(plain, frame)


def test_an_inspector_with_no_picture_is_not_active():
    QApplication.instance() or QApplication([])
    parent = QWidget()
    view = ImageInspector(parent)
    assert not view.is_active()
    view.close_view()                             # idempotent, no crash
    assert not view.is_active()


# ── it travels between the page and the window (#64) ──

def test_it_grows_out_of_where_the_picture_sits_on_the_page(reader):
    """A cut leaves the reader re-finding their place; travelling keeps one
    object in view."""
    from PySide6.QtTest import QTest
    _caret_to(reader, "<image>")
    assert reader._image_cell_in_self() is not None
    _press(reader, Qt.Key.Key_Return)
    view = reader._image_view
    assert view._from_rect is not None
    assert view._t < 1.0                       # starts at the page, not the end
    QTest.qWait(_OPEN_MS + 150)
    assert view._t == pytest.approx(1.0)       # and arrives


def test_closing_travels_back_and_only_then_hides(reader):
    from PySide6.QtTest import QTest
    _caret_to(reader, "<image>")
    _press(reader, Qt.Key.Key_Return)
    QTest.qWait(_OPEN_MS + 150)
    _press(reader, Qt.Key.Key_Escape)
    assert not view_active(reader)             # logically closed at once...
    assert reader._image_view.isVisible()      # ...but still on screen
    QTest.qWait(_CLOSE_MS + 150)
    assert not reader._image_view.isVisible()


def view_active(ed):
    return ed._image_view is not None and ed._image_view.is_active()


def test_reversing_mid_flight_picks_up_where_it_is(reader):
    """A quick open-then-close must not snap back to the far end first."""
    from PySide6.QtTest import QTest
    _caret_to(reader, "<image>")
    _press(reader, Qt.Key.Key_Return)
    QTest.qWait(60)                            # part-way out
    part_way = reader._image_view._t
    assert 0.0 < part_way < 1.0
    _press(reader, Qt.Key.Key_Escape)
    assert reader._image_view._t == pytest.approx(part_way, abs=0.25)


def test_the_on_page_rectangle_is_the_drawn_one_in_editor_coordinates(reader):
    """The travel is only convincing if it starts where the picture actually
    is. The reading view's viewport is a child of the editor, so the rect has
    to come up into the editor's coordinates — same size, shifted origin."""
    from PySide6.QtCore import QPointF
    _caret_to(reader, "<image>")
    doc = reader._rendered.document()
    pos = reader._rendered.textCursor().position()
    block = doc.findBlock(pos)
    frag = next(it.fragment() for it in [block.begin()]
                if it.fragment().charFormat().isImageFormat())
    off = QPointF(-reader._rendered.horizontalScrollBar().value(),
                  -reader._rendered.verticalScrollBar().value())
    in_view = reader._rendered._image_cell(doc, doc.documentLayout(),
                                           block, frag, off)
    in_editor = reader._image_cell_in_self()
    assert in_editor is not None
    assert in_editor.width() == pytest.approx(in_view.width())
    assert in_editor.height() == pytest.approx(in_view.height())
    vp = reader._rendered.viewport()
    shift = vp.mapTo(reader, vp.rect().topLeft())
    assert in_editor.x() == pytest.approx(in_view.x() + shift.x(), abs=1)
    assert in_editor.y() == pytest.approx(in_view.y() + shift.y(), abs=1)


# ── the blend itself ──

def test_lerp_walks_from_one_rect_to_the_other():
    start, end = QRectF(0, 0, 10, 10), QRectF(100, 200, 110, 210)
    assert _lerp(start, end, 0.0) == start
    assert _lerp(start, end, 1.0) == end
    mid = _lerp(start, end, 0.5)
    assert mid.x() == pytest.approx(50)
    assert mid.width() == pytest.approx(60)


def test_lerp_with_nowhere_to_come_from_is_just_the_destination():
    end = QRectF(1, 2, 3, 4)
    assert _lerp(None, end, 0.0) == end
