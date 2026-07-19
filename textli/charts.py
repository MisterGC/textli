"""Value tables as charts for the read view — a marker comment opts a table in.

A pipe table preceded by a ``chart:`` marker comment renders as a typeset chart
instead of a grid::

    <!-- chart: bar x=Quarter -->
    | Quarter | 2025 | 2026 |
    | ------- | ---- | ---- |
    | Q1      | 3.2  | 4.1  |
    | Q2      | 5.1  | 4.9  |

The marker is an ordinary HTML comment, so the source stays portable pandoc
Markdown: GitHub renders the table, pandoc converts it, the comment vanishes in
output. In textli the marker + table are swapped for a chart image; nothing of
the marker shows on the page.

The spec is three keys at most: ``type`` (the word after ``chart:`` — ``bar`` or
``line``), ``x=<column>`` (the column whose values label the x axis; default the
first), and ``y=<col,col>`` (an optional subset of series columns; default every
column but the x one). Series names come from the headers; a header's trailing
``[unit]`` labels the y axis.

Robustness mirrors the math pass: anything wrong — an unknown type, an ``x=`` that
names no column, a non-numeric data cell, a marker with no table under it — means
the table renders as a normal table and the marker is simply dropped (it never
shows). This module never raises on bad input; it just declines to build a chart.

Pure text logic, no Qt — same design line as `comments.py` / `formulas.py`, so it
is cheap to unit-test.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .comments import SENTINEL_END, SENTINEL_START, code_ranges

_SENTINELS = SENTINEL_START + SENTINEL_END

# The marker line: an HTML comment whose body starts with ``chart:``. It may be
# indented, and it may carry a glued prefix — a CriticMarkup opener or a sentinel
# — when the whole table has been commented/suggested on (the marker then sits
# just inside the mark). The prefix is kept *out* of ``marker`` so the region we
# rewrite starts exactly at ``<!--`` and any such prefix survives the rewrite.
_RE_MARKER = re.compile(
    r"(?m)^[^\S\n]*"
    r"(?:\{(?:==|\+\+|--|~~)|[" + _SENTINELS + r"])?"
    r"(?P<marker><!--[^\S\n]*chart:(?P<spec>[^\n]*?)-->)[^\S\n]*$"
)

# A pipe-table delimiter cell: dashes with optional alignment colons.
_RE_DELIM_CELL = re.compile(r"^:?-+:?$")

# A header's trailing unit, e.g. ``time [s]`` -> name ``time``, unit ``s``.
_RE_UNIT = re.compile(r"^(?P<name>.*?)\s*\[(?P<unit>[^\]]*)\]\s*$")

_KINDS = ("bar", "line")


@dataclass(frozen=True)
class Chart:
    """A parsed chart: its source region plus the values to plot. All-tuple, so
    it is hashable and can key the render cache directly."""

    kind: str                                       # "bar" | "line"
    x_label: str                                    # header of the x column
    x_values: tuple[str, ...]                       # x-axis category labels
    series: tuple[tuple[str, tuple[float, ...]], ...]  # (name, values) per column
    y_axis_label: str                               # a header's unit, or ""


@dataclass(frozen=True)
class Marker:
    """One ``chart:`` marker and the region it governs.

    ``chart`` is the parsed :class:`Chart` when the marker sits on a well-formed
    numeric table, else ``None`` (the marker is invisible and just stripped).
    ``fallback`` is what the region collapses to when a chart can't be drawn: the
    bare table for a valid-but-unrenderable chart, an empty string for a marker
    with nothing to chart.
    """

    start: int          # offset of the opening ``<!--``
    end: int            # offset just past the region the marker governs
    chart: Chart | None
    fallback: str


def _strip_edges(s: str) -> str:
    """Trim whitespace and sentinel markers from both ends of ``s``."""
    return s.strip().strip(_SENTINELS).strip()


def _row_cells(line: str) -> list[str] | None:
    """Cells of a bordered pipe-table row, or ``None`` when ``line`` isn't one.

    Requires the GFM border form (a leading and trailing ``|``) so the closing
    pipe is unambiguous — that's what lets the rewrite end exactly at the table
    and leave a trailing sentinel untouched."""
    core = _strip_edges(line)
    if not (core.startswith("|") and core.endswith("|")):
        return None
    return [_strip_edges(c) for c in core[1:-1].split("|")]


def _close_pipe(text: str, line_start: int, line_end: int) -> int:
    """Offset just past a bordered row's closing ``|`` (before any trailing
    whitespace or sentinel), for ``text[line_start:line_end]``."""
    trimmed = text[line_start:line_end].rstrip().rstrip(_SENTINELS).rstrip()
    return line_start + len(trimmed)


def _iter_lines(text: str, pos: int):
    """Yield ``(content, start, end)`` for each line from ``pos``, ``end`` being
    the offset of the newline (or end of text)."""
    n = len(text)
    while pos < n:
        nl = text.find("\n", pos)
        end = n if nl < 0 else nl
        yield text[pos:end], pos, end
        pos = n if nl < 0 else nl + 1


def _split_unit(header: str) -> tuple[str, str]:
    """A header split into ``(series_name, unit)`` — ``time [s]`` -> ``time``,
    ``s``; a plain header keeps its name and an empty unit."""
    m = _RE_UNIT.match(header)
    if m and m.group("name").strip():
        return m.group("name").strip(), m.group("unit").strip()
    return header, ""


def _parse_spec(spec: str):
    """``(kind, x_col, y_cols)`` for a marker spec, or ``None`` when it's malformed
    — an unknown type, an unknown key, or empty. ``x_col``/``y_cols`` are ``None``
    when the spec leaves them to default."""
    tokens = spec.split()
    if not tokens or tokens[0] not in _KINDS:
        return None
    kind = tokens[0]
    x_col: str | None = None
    y_cols: list[str] | None = None
    for tok in tokens[1:]:
        if tok.startswith("x="):
            x_col = tok[2:] or None
        elif tok.startswith("y="):
            y_cols = [c.strip() for c in tok[2:].split(",") if c.strip()] or None
        else:
            return None                      # a fourth key is out of spec
    return kind, x_col, y_cols


def _col_index(headers, name) -> int | None:
    """Index of the column ``name`` refers to — the raw header, or its
    unit-stripped name so ``y=latency`` finds the ``latency [ms]`` column."""
    if name in headers:
        return headers.index(name)
    for i, h in enumerate(headers):
        if _split_unit(h)[0] == name:
            return i
    return None


def _build_chart(kind, x_col, y_cols, headers, rows) -> Chart | None:
    """Assemble a :class:`Chart` from parsed spec + table, or ``None`` when the
    two don't fit: a named column that's missing, a non-numeric series cell, or
    no series left to plot."""
    if x_col is None:
        x_idx = 0
    else:
        x_idx = _col_index(headers, x_col)
        if x_idx is None:
            return None
    if y_cols is None:
        series_idx = [i for i in range(len(headers)) if i != x_idx]
    else:
        series_idx = []
        for name in y_cols:
            i = _col_index(headers, name)
            if i is None:
                return None
            if i != x_idx and i not in series_idx:
                series_idx.append(i)
    if not series_idx:
        return None
    x_values = tuple(r[x_idx] for r in rows)
    series: list[tuple[str, tuple[float, ...]]] = []
    y_axis_label = ""
    for i in series_idx:
        name, unit = _split_unit(headers[i])
        try:
            values = tuple(float(r[i]) for r in rows)
        except ValueError:
            return None
        if unit and not y_axis_label:
            y_axis_label = unit
        series.append((name, values))
    return Chart(kind=kind, x_label=headers[x_idx], x_values=x_values,
                 series=tuple(series), y_axis_label=y_axis_label)


def _parse_table(text: str, pos: int):
    """Parse a bordered pipe table that starts at ``pos`` (the line right after a
    marker). Returns ``(headers, rows, table_start, table_end)`` or ``None``.

    ``table_end`` is the offset just past the last row's closing pipe, so a
    sentinel glued after it (a commented table) stays outside the rewritten
    region."""
    lines = list(_iter_lines(text, pos))
    if len(lines) < 3:
        return None
    header = _row_cells(lines[0][0])
    delim = _row_cells(lines[1][0])
    if header is None or delim is None or len(delim) != len(header):
        return None
    if not all(_RE_DELIM_CELL.match(c) for c in delim):
        return None
    ncols = len(header)
    rows: list[list[str]] = []
    table_end = _close_pipe(text, lines[1][1], lines[1][2])
    table_start = lines[0][1]
    for content, start, end in lines[2:]:
        cells = _row_cells(content)
        if cells is None or len(cells) != ncols:
            break
        rows.append(cells)
        table_end = _close_pipe(text, start, end)
    if not rows:
        return None
    return header, rows, table_start, table_end


def parse(text: str) -> list[Marker]:
    """Every ``chart:`` marker in ``text``, in document order. A marker inside a
    code region is left literal (it's a documentation example, not a directive),
    exactly as `comments.py` treats its own syntax. Each :class:`Marker` carries a
    parsed :class:`Chart` when it governs a valid numeric table, else ``None``."""
    ranges = code_ranges(text)

    def in_code(pos: int) -> bool:
        return any(a <= pos < b for a, b in ranges)

    out: list[Marker] = []
    for m in _RE_MARKER.finditer(text):
        open_at = m.start("marker")
        if in_code(open_at):
            continue
        spec = _parse_spec(m.group("spec").strip())
        line_end = m.end()
        strip_end = min(len(text), line_end + 1)   # swallow the marker's newline
        if spec is None:
            out.append(Marker(open_at, strip_end, None, ""))
            continue
        table_pos = line_end + 1
        parsed = _parse_table(text, table_pos) if table_pos <= len(text) else None
        if parsed is None:
            out.append(Marker(open_at, strip_end, None, ""))
            continue
        headers, rows, table_start, table_end = parsed
        chart = _build_chart(*spec, headers, rows)
        if chart is None:
            out.append(Marker(open_at, table_end, None, text[table_start:table_end]))
            continue
        out.append(Marker(open_at, table_end, chart, text[table_start:table_end]))
    return out


def substitute(text: str, markers: list[Marker], replacement) -> str:
    """Rebuild ``text`` with each marker's region replaced by
    ``replacement(i, marker)`` and everything else untouched. ``markers`` must be
    :func:`parse` output for this same ``text`` (document order, non-overlapping)."""
    out: list[str] = []
    pos = 0
    for i, mk in enumerate(markers):
        out.append(text[pos:mk.start])
        out.append(replacement(i, mk))
        pos = mk.end
    out.append(text[pos:])
    return "".join(out)
