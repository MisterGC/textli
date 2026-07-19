"""Charts in the read view (#41): a `<!-- chart: … -->` marker turns the pipe
table under it into a typeset chart image. Covers the pure parser, the QPainter
renderer, and the editor integration (image swap, fallbacks, coexistence with
CriticMarkup, and review semantics)."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QTextCursor, QTextTable  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from textli import charts, chartrender  # noqa: E402
from textli.editor import ZenMarkdownEditor, _CHART_SCHEME  # noqa: E402
from textli.fonts import register_bundled_fonts  # noqa: E402

OBJ = "￼"   # Qt's object-replacement char — a rendered image reads as this

BAR = (
    "<!-- chart: bar x=Quarter -->\n"
    "| Quarter | 2025 | 2026 |\n"
    "| ------- | ---- | ---- |\n"
    "| Q1      | 3.2  | 4.1  |\n"
    "| Q2      | 5.1  | 4.9  |\n"
)
LINE = (
    "<!-- chart: line -->\n"
    "| t | speed [m/s] |\n"
    "| - | ----------- |\n"
    "| 0 | 1.0 |\n"
    "| 1 | 2.5 |\n"
    "| 2 | 1.8 |\n"
)


# ── charts.py: parsing (pure, no Qt needed) ──────────────────────────────

def _only(markers):
    assert len(markers) == 1
    return markers[0]


def test_bar_marker_parses_headers_and_numeric_series():
    ch = _only(charts.parse(BAR)).chart
    assert ch is not None
    assert ch.kind == "bar"
    assert ch.x_label == "Quarter"
    assert ch.x_values == ("Q1", "Q2")
    assert ch.series == (("2025", (3.2, 5.1)), ("2026", (4.1, 4.9)))


def test_x_defaults_to_first_column():
    md = "<!-- chart: bar -->\n| A | B |\n| - | - |\n| p | 1 |\n| q | 2 |\n"
    ch = _only(charts.parse(md)).chart
    assert ch.x_label == "A" and ch.x_values == ("p", "q")
    assert ch.series == (("B", (1.0, 2.0)),)


def test_y_selects_a_subset_of_series():
    md = ("<!-- chart: bar x=Quarter y=2026 -->\n"
          "| Quarter | 2025 | 2026 |\n| - | - | - |\n| Q1 | 3 | 4 |\n")
    ch = _only(charts.parse(md)).chart
    assert [name for name, _ in ch.series] == ["2026"]
    assert ch.series[0][1] == (4.0,)


def test_y_matches_a_unit_stripped_header():
    md = ("<!-- chart: line x=build y=latency -->\n"
          "| build | latency [ms] | throughput |\n| - | - | - |\n"
          "| v1 | 120 | 900 |\n")
    ch = _only(charts.parse(md)).chart
    assert ch is not None
    assert [name for name, _ in ch.series] == ["latency"]
    assert ch.y_axis_label == "ms"


def test_line_chart_and_unit_header():
    ch = _only(charts.parse(LINE)).chart
    assert ch.kind == "line"
    assert ch.series == (("speed", (1.0, 2.5, 1.8)),)   # name stripped of unit
    assert ch.y_axis_label == "m/s"                      # unit lifts to the axis


def test_unknown_type_is_no_chart_and_leaves_the_table():
    md = "<!-- chart: pie -->\n| A | B |\n| - | - |\n| 1 | 2 |\n"
    mk = _only(charts.parse(md))
    assert mk.chart is None
    # substitute strips only the marker line; the table text is left in place
    out = charts.substitute(md, [mk], lambda i, m: "IMG" if m.chart else m.fallback)
    assert "IMG" not in out and "| A | B |" in out and "chart:" not in out


def test_missing_x_column_falls_back_to_the_table():
    md = "<!-- chart: bar x=Nope -->\n| A | B |\n| - | - |\n| 1 | 2 |\n"
    mk = _only(charts.parse(md))
    assert mk.chart is None
    out = charts.substitute(md, [mk], lambda i, m: "IMG" if m.chart else m.fallback)
    assert "| A | B |" in out and "chart:" not in out


def test_non_numeric_cell_falls_back_to_the_table():
    md = "<!-- chart: bar -->\n| A | B |\n| - | - |\n| x | y |\n"
    assert _only(charts.parse(md)).chart is None


def test_marker_without_a_table_is_stripped_to_nothing():
    md = "<!-- chart: bar -->\n\njust prose, no table\n"
    mk = _only(charts.parse(md))
    assert mk.chart is None and mk.fallback == ""
    out = charts.substitute(md, [mk], lambda i, m: "IMG" if m.chart else m.fallback)
    assert "chart:" not in out and "just prose" in out


def test_table_without_a_marker_is_untouched():
    md = "| A | B |\n| - | - |\n| 1 | 2 |\n"
    assert charts.parse(md) == []


def test_marker_inside_a_code_fence_is_literal():
    md = "```\n<!-- chart: bar -->\n| A | B |\n| - | - |\n| 1 | 2 |\n```\n"
    assert charts.parse(md) == []


# ── chartrender.py: rasterization + cache ────────────────────────────────

def _q():
    QApplication.instance() or QApplication([])
    register_bundled_fonts()


def test_bar_renders_a_plausible_image():
    _q()
    ch = charts.parse(BAR)[0].chart
    rc = chartrender.render(ch, width_px=600, height_px=320, dpr=2.0)
    assert rc is not None and not rc.image.isNull()
    assert rc.image.width() == 1200 and rc.image.height() == 640   # dpr-scaled


def test_line_renders_a_plausible_image():
    _q()
    ch = charts.parse(LINE)[0].chart
    rc = chartrender.render(ch, width_px=600, height_px=320, dpr=1.0)
    assert rc is not None and not rc.image.isNull()


def test_render_is_cached_across_calls():
    _q()
    ch = charts.parse(BAR)[0].chart
    a = chartrender.render(ch, width_px=500, height_px=280, dpr=1.0)
    b = chartrender.render(ch, width_px=500, height_px=280, dpr=1.0)
    assert a is b                                    # served from the cache


def test_tiny_frame_is_declined_not_crashed():
    _q()
    ch = charts.parse(BAR)[0].chart
    assert chartrender.render(ch, width_px=20, height_px=20, dpr=1.0) is None


# ── editor integration ───────────────────────────────────────────────────

def _editor(md: str) -> ZenMarkdownEditor:
    QApplication.instance() or QApplication([])
    parent = QWidget()
    parent.resize(1000, 700)
    ed = ZenMarkdownEditor(parent, md, title="c")
    ed._parent = parent            # keep a ref alive
    ed._suggest_animate = False    # deterministic — no tween
    return ed


def _image_names(ed) -> list[str]:
    doc = ed._rendered.document()
    names = []
    block = doc.begin()
    while block.isValid():
        it = block.begin()
        while not it.atEnd():
            cf = it.fragment().charFormat()
            if cf.isImageFormat():
                names.append(cf.toImageFormat().name())
            it += 1
        block = block.next()
    return names


def _has_table(ed) -> bool:
    doc = ed._rendered.document()
    return any(isinstance(f, QTextTable) for f in doc.rootFrame().childFrames())


def test_chart_marker_becomes_an_image_and_table_text_is_gone():
    ed = _editor(f"Intro.\n\n{BAR}\nOutro.\n")
    ed._toggle_rendered()
    text = ed._rendered.document().toPlainText()
    assert any(n.startswith(f"{_CHART_SCHEME}://") for n in _image_names(ed))
    assert "| Quarter |" not in text and "chart:" not in text
    assert text.count(OBJ) == 1
    assert not _has_table(ed)                        # replaced, not gridded


def test_malformed_marker_renders_a_plain_table():
    ed = _editor(f"Intro.\n\n<!-- chart: pie -->\n"
                 "| Quarter | 2025 |\n| - | - |\n| Q1 | 3.2 |\n\nOutro.\n")
    ed._toggle_rendered()
    text = ed._rendered.document().toPlainText()
    assert _image_names(ed) == []                    # no chart image
    assert "chart:" not in text                      # marker still invisible
    assert _has_table(ed)                            # the table stands as a table
    assert "Quarter" in text and "3.2" in text


def test_chart_coexists_with_a_criticmarkup_comment():
    md = (f"Intro para.\n\n{BAR}\n"
          "A {==commented word==}{>>a note<<} elsewhere.\n")
    ed = _editor(md)
    ed._toggle_rendered()
    # the chart rendered as an image
    assert any(n.startswith(f"{_CHART_SCHEME}://") for n in _image_names(ed))
    # and the comment mark survived intact, styled on its span
    assert len(ed._rendered_comments) == 1
    _s, _e, comment = ed._rendered_comments[0]
    assert comment.span == "commented word"


def test_comment_a_chart_via_caret_gesture_lands_on_the_table_source():
    ed = _editor(f"Intro.\n\n{BAR}\nOutro.\n")
    ed._toggle_rendered()
    assert len(ed._rendered_charts) == 1
    pos = ed._rendered_charts[0][0]
    cur = ed._rendered.textCursor()
    cur.setPosition(pos)
    ed._rendered.setTextCursor(cur)
    ed._comment_selection()
    assert ed._comment_field is not None             # authoring opened
    ed._comment_field.setPlainText("why the Q2 dip?")
    ed._commit_comment_field()
    src = ed._editor.toPlainText()
    # the whole marker + table is wrapped as one comment span
    assert "{==<!-- chart: bar x=Quarter -->" in src
    assert "==}{>>why the Q2 dip?<<}" in src
    assert len(ed._rendered_comments) == 1
    # and it still renders as a chart, now under the comment
    assert any(n.startswith(f"{_CHART_SCHEME}://") for n in _image_names(ed))


def test_suggest_a_chart_replaces_the_table_source():
    ed = _editor(f"Intro.\n\n{BAR}\nOutro.\n")
    ed._toggle_rendered()
    pos = ed._rendered_charts[0][0]
    ed._begin_suggestion_for_span(pos, pos + 1)
    assert ed._comment_field is not None
    ed._comment_field.setPlainText("| Quarter | 2027 |\n| - | - |\n| Q1 | 9 |")
    ed._commit_new_suggestion(ed._comment_field.toPlainText())
    src = ed._editor.toPlainText()
    assert "{~~<!-- chart: bar x=Quarter -->" in src   # substitution of the table
    assert len(ed._rendered_suggestions) == 1
