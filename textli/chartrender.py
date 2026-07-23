"""Chart → ``QImage`` rendering for the read view's value tables (`charts.py`).

A hand-rolled QPainter renderer — no chart library, no new dependency. Bars and
lines are drawn in textli's own visual language: Literata labels in the page ink,
thin warm axis lines and whisper-faint gridlines, accent colors from the zen
palette, and a transparent background so the chart sits on the paper the way a
formula does. No borders, no title, a quiet inline legend only when more than one
series shares the frame — the same calm the read view keeps everywhere.

Kept out of `editor.py` so the drawing math and the render cache live in one
place, exactly like `mathrender.py`; the cache pays for the frequent re-renders
(file watch, zoom, view toggles) since a document repeats its charts across them.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetricsF,
    QImage,
    QPainter,
    QPen,
    QPolygonF,
)

from .charts import Chart
from .constants import (
    READING_FONT_FAMILY,
    ZEN_CODE_NUMBER,
    ZEN_CODE_STRING,
    ZEN_HINT_COLOR,
    ZEN_MD_COMMENT_INK,
    ZEN_MD_TABLE_BORDER,
    ZEN_TEXT_COLOR,
    ZEN_TITLE_COLOR,
)

# Series accent colors, cycled — the zen blue, warm red, amber, and comment ink.
# Drawn from the palette so a chart shares the page's few colors and nothing new
# enters it.
_SERIES_COLORS = (
    ZEN_TITLE_COLOR,
    ZEN_CODE_STRING,
    ZEN_CODE_NUMBER,
    ZEN_MD_COMMENT_INK,
)


@dataclass(frozen=True)
class RenderedChart:
    """A rasterized chart — device-pixel-ratio scaled, transparent background."""

    image: QImage


# (chart, width, height, dpr) -> RenderedChart | None. Chart is hashable (all
# tuples), so it keys the cache directly; a chart that can't be drawn caches its
# ``None`` too, so it doesn't re-attempt on every re-render.
_cache: dict[tuple, RenderedChart | None] = {}
_CACHE_MAX = 256


def render(chart: Chart, *, width_px: float, height_px: float,
           dpr: float) -> RenderedChart | None:
    """Rasterize ``chart`` into a ``width_px`` x ``height_px`` logical image at
    ``dpr``, or ``None`` when the frame is too small to draw into."""
    key = (chart, round(width_px, 1), round(height_px, 1), round(dpr, 2))
    if key in _cache:
        return _cache[key]
    if len(_cache) >= _CACHE_MAX:
        _cache.clear()
    result = _render(chart, width_px, height_px, dpr)
    _cache[key] = result
    return result


def _render(chart: Chart, width_px: float, height_px: float,
            dpr: float) -> RenderedChart | None:
    if width_px < 80 or height_px < 60:
        return None
    image = QImage(math.ceil(width_px * dpr), math.ceil(height_px * dpr),
                   QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    painter.scale(dpr, dpr)                      # draw in logical coordinates
    try:
        _draw(painter, chart, width_px, height_px)
    finally:
        painter.end()
    image.setDevicePixelRatio(dpr)
    return RenderedChart(image=image)


def _nice(x: float, round_down: bool) -> float:
    """A 1/2/5 x 10^n 'nice' number near ``x`` — the classic axis-tick step."""
    if x <= 0:
        return 1.0
    exp = math.floor(math.log10(x))
    frac = x / 10 ** exp
    if round_down:
        nice = 1 if frac < 1.5 else 2 if frac < 3 else 5 if frac < 7 else 10
    else:
        nice = 1 if frac <= 1 else 2 if frac <= 2 else 5 if frac <= 5 else 10
    return nice * 10 ** exp


def _ticks(lo: float, hi: float, target: int = 4):
    """Nice tick values spanning ``[lo, hi]`` plus the padded ``(min, max)`` the
    axis maps against."""
    if hi <= lo:
        hi = lo + 1.0
    step = _nice((hi - lo) / max(1, target), False)
    nlo = math.floor(lo / step) * step
    nhi = math.ceil(hi / step) * step
    ticks = []
    v = nlo
    while v <= nhi + step * 0.5:
        ticks.append(round(v, 10))
        v += step
    return ticks, nlo, nhi


def _fmt(v: float) -> str:
    """A tick/label number without trailing noise — ``3`` not ``3.0``."""
    if abs(v - round(v)) < 1e-9:
        return str(int(round(v)))
    return f"{v:g}"


def _draw(p: QPainter, chart: Chart, w: float, h: float) -> None:
    label_px = max(9.0, min(13.0, h / 20))
    font = QFont(READING_FONT_FAMILY)
    font.setPixelSize(round(label_px))
    p.setFont(font)
    fm = QFontMetricsF(font)

    values = [v for _, vals in chart.series for v in vals]
    dmin, dmax = (min(values), max(values)) if values else (0.0, 1.0)
    # Bars are read against zero, so the baseline must be in frame; lines just
    # need their own range.
    lo = min(0.0, dmin) if chart.kind == "bar" else dmin
    hi = max(0.0, dmax) if chart.kind == "bar" else dmax
    ticks, ymin, ymax = _ticks(lo, hi)
    yspan = ymax - ymin or 1.0

    multi = len(chart.series) > 1
    legend_h = fm.height() + 6 if multi else 0.0
    y_tick_w = max(fm.horizontalAdvance(_fmt(t)) for t in ticks) + 8
    unit_w = fm.height() + 4 if chart.y_axis_label else 0.0
    left = unit_w + y_tick_w
    right = 8.0
    top = 6.0 + legend_h
    bottom = fm.height() + 8
    plot = QRectF(left, top, max(1.0, w - left - right),
                  max(1.0, h - top - bottom))

    def ypix(val: float) -> float:
        return plot.bottom() - (val - ymin) / yspan * plot.height()

    # Whisper-faint gridlines + right-aligned tick labels.
    grid = QColor(ZEN_MD_TABLE_BORDER)
    grid.setAlpha(38)
    p.setPen(QColor(ZEN_HINT_COLOR))
    for t in ticks:
        y = ypix(t)
        p.setPen(QPen(grid, 1))
        p.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
        p.setPen(QColor(ZEN_HINT_COLOR))
        p.drawText(QRectF(0, y - fm.height() / 2, left - 8, fm.height()),
                   int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
                   _fmt(t))

    # Axis lines — a thin warm L, no box.
    p.setPen(QPen(ZEN_MD_TABLE_BORDER, 1.2))
    p.drawLine(QPointF(plot.left(), plot.top()), QPointF(plot.left(), plot.bottom()))
    p.drawLine(QPointF(plot.left(), ypix(min(ymax, max(ymin, 0.0)))),
               QPointF(plot.right(), ypix(min(ymax, max(ymin, 0.0)))))

    n = len(chart.x_values)
    if chart.kind == "bar":
        _draw_bars(p, chart, plot, ypix, n)
    else:
        _draw_lines(p, chart, plot, ypix, n)

    # X-axis category labels, centered under each slot.
    p.setPen(QColor(ZEN_TEXT_COLOR))
    if n:
        slot = plot.width() / n
        for i, label in enumerate(chart.x_values):
            cx = plot.left() + (i + 0.5) * slot
            p.drawText(QRectF(cx - slot / 2, plot.bottom() + 3, slot, fm.height()),
                       int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop),
                       _elide(fm, label, slot))

    if chart.y_axis_label:
        p.save()
        p.translate(fm.height() - 2, plot.center().y())
        p.rotate(-90)
        p.setPen(QColor(ZEN_HINT_COLOR))
        p.drawText(QRectF(-plot.height() / 2, -fm.height() / 2,
                          plot.height(), fm.height()),
                   int(Qt.AlignmentFlag.AlignCenter), chart.y_axis_label)
        p.restore()

    if multi:
        _draw_legend(p, chart, fm, left, w)


def _draw_bars(p, chart: Chart, plot: QRectF, ypix, n: int) -> None:
    if not n:
        return
    slot = plot.width() / n
    ns = len(chart.series)
    group_w = slot * 0.72
    bar_w = group_w / ns
    base = ypix(0.0)
    for i in range(n):
        slot_left = plot.left() + i * slot + (slot - group_w) / 2
        for j, (_, vals) in enumerate(chart.series):
            val = vals[i] if i < len(vals) else 0.0
            x = slot_left + j * bar_w
            y = ypix(val)
            rect = QRectF(x + bar_w * 0.08, min(y, base),
                          bar_w * 0.84, abs(base - y))
            p.fillRect(rect, _SERIES_COLORS[j % len(_SERIES_COLORS)])


def _draw_lines(p, chart: Chart, plot: QRectF, ypix, n: int) -> None:
    if not n:
        return
    xs = [plot.left() + (i + 0.5) * (plot.width() / n) for i in range(n)]
    for j, (_, vals) in enumerate(chart.series):
        color = _SERIES_COLORS[j % len(_SERIES_COLORS)]
        poly = QPolygonF([QPointF(xs[i], ypix(vals[i]))
                          for i in range(min(n, len(vals)))])
        p.setPen(QPen(color, 2.0, Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.drawPolyline(poly)
        p.setBrush(color)
        p.setPen(QPen(color, 1))
        for pt in poly:
            p.drawEllipse(pt, 2.6, 2.6)
    p.setBrush(Qt.BrushStyle.NoBrush)


def _draw_legend(p, chart: Chart, fm: QFontMetricsF, left: float, w: float) -> None:
    p.setPen(QColor(ZEN_TEXT_COLOR))
    gap = fm.horizontalAdvance("x")
    swatch = fm.height() * 0.55
    x = left
    y = 3.0
    for j, (name, _) in enumerate(chart.series):
        color = _SERIES_COLORS[j % len(_SERIES_COLORS)]
        p.fillRect(QRectF(x, y + (fm.height() - swatch) / 2, swatch, swatch), color)
        x += swatch + 4
        p.setPen(QColor(ZEN_TEXT_COLOR))
        p.drawText(QPointF(x, y + fm.ascent()), name)
        x += fm.horizontalAdvance(name) + gap
        if x > w - 40:                       # keep the legend on one quiet row
            break


def _elide(fm: QFontMetricsF, text: str, width: float) -> str:
    """Middle-elide ``text`` to ``width`` so a long category label never bleeds
    into its neighbour."""
    from PySide6.QtCore import Qt as _Qt
    return fm.elidedText(text, _Qt.TextElideMode.ElideRight, int(width))
