"""Images fit the prose column (#60): a wide picture is scaled down to it
instead of breaking the page sideways, and everything wide refits when the
column moves."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtCore import QUrl  # noqa: E402
from PySide6.QtGui import QImage  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from textli.constants import ZEN_MD_PICTURE_WIDTH_SHARE  # noqa: E402
from textli.editor import ZenMarkdownEditor  # noqa: E402

WIDE_W, WIDE_H = 2400, 1350
ICON_W, ICON_H = 120, 80

CHART = ("<!-- chart: bar x=x -->\n"
         "| x | y |\n|---|---|\n| a | 1 |\n| b | 3 |\n")


def _reader(tmp_path, md: str):
    QApplication.instance() or QApplication([])
    QImage(WIDE_W, WIDE_H, QImage.Format.Format_RGB32).save(
        str(tmp_path / "wide.png"))
    QImage(ICON_W, ICON_H, QImage.Format.Format_RGB32).save(
        str(tmp_path / "icon.png"))
    note = tmp_path / "n.md"
    note.write_text(md, encoding="utf-8")
    host = QWidget()
    host.resize(1600, 1000)
    ed = ZenMarkdownEditor(host, md, title="T", file_path=note,
                           start_in_read=True)
    ed.resize(1600, 1000)
    host.show()
    ed._opacity.setOpacity(1.0)
    ed._host = host
    _settle(ed)
    return ed


def _settle(ed, rounds: int = 4):
    """Run the refit the way the coalescing timer would, until the column
    stops moving. The viewport resizes on a later layout pass than the card,
    so one pass can render against a width that is already stale."""
    app = QApplication.instance()
    for _ in range(rounds):
        app.processEvents()
        ed._refit_rendered()
        app.processEvents()


def _images(ed) -> dict[str, tuple[float, int]]:
    """``{resource name: (displayed width, source width)}``."""
    doc = ed._rendered.document()
    out = {}
    block = doc.begin()
    while block.isValid():
        it = block.begin()
        while not it.atEnd():
            fmt = it.fragment().charFormat()
            if fmt.isImageFormat():
                imf = fmt.toImageFormat()
                res = doc.resource(doc.ResourceType.ImageResource,
                                   QUrl(imf.name()))
                out[imf.name()] = (imf.width(), res.width())
            it += 1
        block = block.next()
    return out


@pytest.fixture
def wide(tmp_path):
    return _reader(tmp_path, "# T\n\n![wide](wide.png)\n\nProse.\n")


# ── fitting ──

def _fills_the_cap(shown: float, ed) -> bool:
    """Within a scrollbar's width of the picture cap. Not slop for its own
    sake: the scrollbar coming and going moves the column by its 8px, so the
    fit settles near the cap rather than exactly on it (``_REFIT_EPSILON``)."""
    cap = ed._picture_width_px()
    return cap - 16 <= shown <= cap + 1


def test_a_wide_image_is_scaled_down_to_the_cap(wide):
    shown, source = _images(wide)["wide.png"]
    assert source == WIDE_W                       # the file is untouched
    assert _fills_the_cap(shown, wide)


def test_the_cap_is_a_share_of_the_column(wide):
    """A picture drawn to the full measure is as tall as its aspect ratio
    makes it — three quarters of the width is three quarters of the height
    too, and `↵` still has the original to enlarge (#62)."""
    assert wide._picture_width_px() == pytest.approx(
        wide._page_width_px() * ZEN_MD_PICTURE_WIDTH_SHARE)
    shown, _ = _images(wide)["wide.png"]
    assert shown < wide._page_width_px() * 0.85   # visibly short of the column


def test_the_cap_buys_back_vertical_space(wide):
    """The point of the cap: less page spent on something the reader is
    mostly reading around."""
    doc = wide._rendered.document()
    block = doc.begin()
    while block.isValid():
        if "￼" in block.text():
            height = doc.documentLayout().blockBoundingRect(block).height()
            at_full_column = wide._page_width_px() * WIDE_H / WIDE_W
            assert height < at_full_column * 0.8
            return
        block = block.next()
    raise AssertionError("no image block")


def test_a_chart_is_rasterised_at_the_cap_not_scaled_down_to_it(tmp_path):
    """Rendering to the full column and drawing it smaller would be
    needlessly soft."""
    ed = _reader(tmp_path, "# T\n\n" + CHART)
    name = next(k for k in _images(ed) if k.startswith("textli-chart"))
    shown, source = _images(ed)[name]
    assert source == pytest.approx(shown, abs=1)  # drawn at its own size
    assert source == pytest.approx(ed._picture_width_px(), abs=16)


def test_a_wide_image_no_longer_breaks_the_page_sideways(wide):
    """Qt draws an image at natural pixel size, so a screenshot used to push
    the document's ideal width past the viewport and grow a scrollbar."""
    doc = wide._rendered.document()
    assert doc.idealWidth() <= wide._rendered.viewport().width() + 1
    assert wide._rendered.horizontalScrollBar().maximum() == 0


def test_the_aspect_ratio_is_kept(wide):
    doc = wide._rendered.document()
    block = doc.begin()
    while block.isValid():
        it = block.begin()
        while not it.atEnd():
            fmt = it.fragment().charFormat()
            if fmt.isImageFormat():
                imf = fmt.toImageFormat()
                assert imf.width() / imf.height() == pytest.approx(
                    WIDE_W / WIDE_H, rel=0.01)
                return
            it += 1
        block = block.next()
    raise AssertionError("no image fragment")


def test_a_small_image_is_left_alone(tmp_path):
    """Downscale only — an icon stretched to fill the measure is worse than
    an icon. Width 0 is Qt's 'draw me at natural size'."""
    ed = _reader(tmp_path, "# T\n\n![icon](icon.png)\n")
    shown, source = _images(ed)["icon.png"]
    assert source == ICON_W
    assert shown == 0


def test_the_full_resolution_source_survives_for_the_expanded_view(wide):
    """#59 reads the resource, not the displayed size — scaling the page
    copy down must not cost the zoom its detail."""
    doc = wide._rendered.document()
    block = doc.begin()
    while block.isValid():
        it = block.begin()
        while not it.atEnd():
            frag = it.fragment()
            if frag.charFormat().isImageFormat():
                cur = wide._rendered.textCursor()
                cur.setPosition(frag.position())
                wide._rendered.setTextCursor(cur)
                assert wide._image_pixmap_at_caret().width() == WIDE_W
                return
            it += 1
        block = block.next()
    raise AssertionError("no image fragment")


def test_generated_images_keep_the_size_they_were_rendered_at(tmp_path):
    """Math, charts and diagrams carry an explicit size already; refitting
    them would fight the width they were rasterised for."""
    ed = _reader(tmp_path, "# T\n\nMath: $$E = mc^2$$\n")
    shown, source = next(
        (v for k, v in _images(ed).items() if k.startswith("textli-math")),
        (None, None))
    assert shown is not None
    assert shown == pytest.approx(source, abs=1)   # untouched by the fit pass


# ── refitting when the column moves ──

def test_widening_the_column_refits_the_image(wide):
    before, _ = _images(wide)["wide.png"]
    for _ in range(3):
        wide._change_width(+1)
    _settle(wide)                                  # what the timer fires
    after, source = _images(wide)["wide.png"]
    assert after > before
    assert _fills_the_cap(after, wide)
    assert source == WIDE_W                        # still the whole picture


def test_narrowing_the_column_refits_the_image(wide):
    before, _ = _images(wide)["wide.png"]
    for _ in range(3):
        wide._change_width(-1)
    _settle(wide)
    after, _ = _images(wide)["wide.png"]
    assert after < before
    assert _fills_the_cap(after, wide)


def test_a_chart_re_rasterises_at_the_new_column(tmp_path):
    """This never worked: a width step resized the card but nothing
    re-rendered, so a chart kept the bitmap it was drawn at."""
    ed = _reader(tmp_path, "# T\n\n" + CHART)
    name = next(k for k in _images(ed) if k.startswith("textli-chart"))
    _, before = _images(ed)[name]
    for _ in range(3):
        ed._change_width(+1)
    _settle(ed)
    name = next(k for k in _images(ed) if k.startswith("textli-chart"))
    _, after = _images(ed)[name]
    assert after > before


def test_a_refit_that_changes_nothing_does_not_re_render(wide):
    """The window resizing fires this too, so an unchanged column has to be
    cheap — re-rendering shells out to grafli for every diagram on the page."""
    doc_before = wide._rendered.document()
    wide._refit_rendered()
    assert wide._rendered.document() is doc_before


def test_the_refit_keeps_the_reader_roughly_where_they_were(tmp_path):
    """A narrower column makes the same document taller, so the old pixel
    offset would land elsewhere — the position is carried as a fraction."""
    ed = _reader(tmp_path, "# T\n\n" + ("Some prose to scroll past.\n\n" * 120)
                 + "![wide](wide.png)\n")
    bar = ed._rendered.verticalScrollBar()
    assert bar.maximum() > 0, "fixture must be long enough to scroll"
    bar.setValue(int(bar.maximum() * 0.5))
    for _ in range(3):
        ed._change_width(-1)
    _settle(ed)
    bar = ed._rendered.verticalScrollBar()
    assert bar.value() == pytest.approx(bar.maximum() * 0.5, rel=0.15)


def test_the_write_view_is_never_refitted(wide):
    """Only the read view rasterises anything to the column, and re-rendering
    it while the reader is in the source would be pure cost."""
    wide._toggle_rendered()                        # back to the source
    assert wide._rendered_mode is False
    doc_before = wide._rendered.document()
    wide._change_width(+1)
    wide._refit_rendered()
    assert wide._rendered.document() is doc_before
