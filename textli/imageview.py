"""Full-page image inspector for the reading view (#59).

An image on the page is drawn at the prose column's width — right for reading
around it, too small for reading *into* it. This lifts the picture off the
page and holds it against the desk: the whole window goes dark, the image is
scaled to fit it, and one key puts the page back.

It covers the window rather than the card on purpose. Charts and diagrams are
rasterised at the *column* width, and the card is only some 130px wider than
that — expanding into the card alone would enlarge a diagram by about a tenth,
which is not worth a keystroke. The window is wide enough to be worth it.

Deliberately not a viewport. There is no pan, no zoom step, no rotate — the
question it answers is "let me see that properly", and anything more would be
a second application living inside the reading view. It takes focus while it
is up so ``Esc`` lands here instead of saving and closing the editor.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QPainter,
    QPixmap,
)
from PySide6.QtWidgets import QWidget

from textli import theme
from textli.constants import READING_FONT_FAMILY, ZEN_MD_FONT_SIZE

# Breathing room between the picture and the edge of the window, so an
# expanded image reads as held up rather than bleeding off the screen.
_MARGIN = 40
# Room kept clear at the bottom for the way-out hint.
_HINT_BAND = 26
# How far the backdrop goes toward opaque — enough that the page beneath
# stops competing, short of pretending it isn't there.
_SCRIM_ALPHA = 244
# Ceiling on enlargement. Only ordinary Markdown images carry a full-size
# original; charts, diagrams and math are bitmaps rendered at the column
# width, and inline math can be under a hundred pixels wide. Without a cap
# those fill the window as a smear, which answers nobody's question. This
# never binds on column-width content, where the window is under 2x the
# image — it only stops the small stuff blowing up into mush.
_MAX_UPSCALE = 4.0


class ImageInspector(QWidget):
    """The expanded image, covering the editor."""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self._pixmap: QPixmap | None = None
        self._restore_focus_to: QWidget | None = None
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.hide()

    # ── lifecycle ──

    def open(self, pixmap: QPixmap, area: QRectF,
             restore_focus_to: QWidget | None = None) -> None:
        """Show ``pixmap`` over ``area`` (in the parent's coordinates)."""
        self._pixmap = pixmap
        self._restore_focus_to = restore_focus_to
        self.set_area(area)
        self.show()
        self.raise_()
        self.setFocus()
        self.update()

    def set_area(self, area: QRectF) -> None:
        """Follow the window — it can be resized while this is up."""
        self.setGeometry(area.toRect())

    def is_active(self) -> bool:
        return self.isVisible() and self._pixmap is not None

    def close_view(self) -> None:
        self._pixmap = None
        self.hide()
        if self._restore_focus_to is not None:
            self._restore_focus_to.setFocus()
        self._restore_focus_to = None

    # ── keys ──

    def keyPressEvent(self, event):
        """Esc or Enter puts the page back. Everything else is swallowed: the
        reader is looking at one picture, and a stray key doing something to
        the document underneath would be a surprise."""
        if event.key() in (Qt.Key.Key_Escape, Qt.Key.Key_Return,
                           Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.close_view()
        event.accept()

    def mousePressEvent(self, event):
        self.close_view()
        event.accept()

    # ── paint ──

    def paintEvent(self, _event):
        if self._pixmap is None or self._pixmap.isNull():
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        # The desk colour, near-opaque — the picture is held against the
        # surface the sheet was lying on, not against a black box.
        area = QRectF(self.rect())
        scrim = QColor(theme.ZEN_BACKDROP)
        scrim.setAlpha(_SCRIM_ALPHA)
        p.fillRect(area, scrim)

        frame = area.adjusted(_MARGIN, _MARGIN, -_MARGIN,
                              -(_MARGIN + _HINT_BAND))
        target = _fit(self._pixmap, frame)
        p.drawPixmap(target.toRect(), self._pixmap)

        hint = QFont(READING_FONT_FAMILY, max(8, ZEN_MD_FONT_SIZE - 5))
        p.setFont(hint)
        p.setPen(QColor(theme.ZEN_INK_ON_DARK_FILL))
        p.drawText(
            QRectF(area.left(), area.bottom() - _HINT_BAND - _MARGIN / 2,
                   area.width(), _HINT_BAND),
            int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter),
            "Esc to close")
        p.end()


def _fit(pixmap: QPixmap, frame: QRectF) -> QRectF:
    """``pixmap``'s rect scaled to fit inside ``frame``, centred, aspect kept.

    Scaling *up* is the point — a diagram too small to read is the reason to
    be here at all — but only as far as ``_MAX_UPSCALE``, past which a small
    bitmap is just a bigger blur. It uses the pixmap's device-independent
    size, or a 2x image on a retina panel would be treated as twice the
    picture it is and come out half as large.
    """
    dpr = pixmap.devicePixelRatio() or 1.0
    w = pixmap.width() / dpr
    h = pixmap.height() / dpr
    if w <= 0 or h <= 0 or frame.width() <= 0 or frame.height() <= 0:
        return QRectF(frame.center(), frame.center())
    scale = min(frame.width() / w, frame.height() / h, _MAX_UPSCALE)
    out = QRectF(0, 0, w * scale, h * scale)
    out.moveCenter(frame.center())
    return out
