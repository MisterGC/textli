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

from PySide6.QtCore import QEasingCurve, QRectF, Qt, QVariantAnimation
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
# The picture travels between where it sits on the page and where it lands
# full-window, rather than the two swapping in one frame (#64) — the eye
# follows one object instead of reconciling two. Same clock and curves the
# editor's own fade in and out use, so the app keeps one motion vocabulary.
_OPEN_MS = 320
_CLOSE_MS = 240


class ImageInspector(QWidget):
    """The expanded image, covering the editor."""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self._pixmap: QPixmap | None = None
        self._restore_focus_to: QWidget | None = None
        self._from_rect: QRectF | None = None   # where it sits on the page
        self._t = 1.0                           # 0 = on the page, 1 = expanded
        self._closing = False
        self._anim: QVariantAnimation | None = None
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.hide()

    # ── lifecycle ──

    def open(self, pixmap: QPixmap, area: QRectF,
             restore_focus_to: QWidget | None = None,
             from_rect: QRectF | None = None) -> None:
        """Show ``pixmap`` over ``area`` (in the parent's coordinates).

        ``from_rect`` is where the picture sits on the page, in the same
        coordinates; the view grows out of it. Without one it simply fades.
        """
        self._pixmap = pixmap
        self._restore_focus_to = restore_focus_to
        self._from_rect = from_rect
        self._closing = False
        # Start *at* the picture on the page, so the tween has somewhere to
        # travel from. Without a rect there is nothing to grow out of and it
        # simply appears.
        self._t = 0.0 if from_rect is not None else 1.0
        self.set_area(area)
        self.show()
        self.raise_()
        self.setFocus()
        self._run(1.0, _OPEN_MS, QEasingCurve.Type.OutCubic)

    def _run(self, to: float, ms: int, curve, done=None) -> None:
        """Tween ``_t`` to ``to``. Reversing mid-flight picks up from wherever
        the picture currently is, so a quick open-then-close doesn't jump."""
        if self._anim is not None:
            self._anim.stop()
        if self._from_rect is None:      # nothing to travel from — just be there
            self._t = to
            self.update()
            if done:
                done()
            return
        anim = QVariantAnimation(self)
        anim.setStartValue(float(self._t))
        anim.setEndValue(float(to))
        anim.setDuration(ms)
        anim.setEasingCurve(curve)
        anim.valueChanged.connect(self._on_tick)
        if done:
            anim.finished.connect(done)
        self._anim = anim               # hold a ref so it isn't collected
        anim.start()

    def _on_tick(self, value):
        self._t = float(value)
        self.update()

    def set_area(self, area: QRectF) -> None:
        """Follow the window — it can be resized while this is up."""
        self.setGeometry(area.toRect())

    def is_active(self) -> bool:
        """Showing a picture. False the moment closing starts, even though the
        widget stays visible until the tween lands."""
        return (self.isVisible() and self._pixmap is not None
                and not self._closing)

    def close_view(self) -> None:
        if self._pixmap is None or self._closing:
            return
        self._closing = True
        if self._restore_focus_to is not None:
            self._restore_focus_to.setFocus()
        self._run(0.0, _CLOSE_MS, QEasingCurve.Type.InCubic, self._finish_close)

    def _finish_close(self) -> None:
        self._pixmap = None
        self._from_rect = None
        self._closing = False
        self._t = 1.0
        self._restore_focus_to = None
        self.hide()

    # ── keys ──

    def keyPressEvent(self, event):
        """Esc or Enter puts the page back. Everything else is swallowed: the
        reader is looking at one picture, and a stray key doing something to
        the document underneath would be a surprise. That holds while it is
        closing too — the tween is still on screen."""
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
        scrim.setAlpha(int(round(_SCRIM_ALPHA * self._t)))
        p.fillRect(area, scrim)

        frame = area.adjusted(_MARGIN, _MARGIN, -_MARGIN,
                              -(_MARGIN + _HINT_BAND))
        target = _lerp(self._from_rect, _fit(self._pixmap, frame), self._t)
        p.drawPixmap(target.toRect(), self._pixmap)

        hint = QFont(READING_FONT_FAMILY, max(8, ZEN_MD_FONT_SIZE - 5))
        p.setFont(hint)
        ink = QColor(theme.ZEN_INK_ON_DARK_FILL)
        ink.setAlpha(int(round(255 * self._t)))
        p.setPen(ink)
        p.drawText(
            QRectF(area.left(), area.bottom() - _HINT_BAND - _MARGIN / 2,
                   area.width(), _HINT_BAND),
            int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter),
            "Esc to close")
        p.end()


def _lerp(start: QRectF | None, end: QRectF, t: float) -> QRectF:
    """``start`` blended toward ``end``. With no start there is nothing to
    travel from, so the picture is simply at ``end``."""
    if start is None or t >= 1.0:
        return end
    return QRectF(
        start.x() + (end.x() - start.x()) * t,
        start.y() + (end.y() - start.y()) * t,
        start.width() + (end.width() - start.width()) * t,
        start.height() + (end.height() - start.height()) * t,
    )


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
