# Charts in textli — a cheatsheet

Open this file with `textli examples/charts.md` and press `⌘R` — every
table below with a `<!-- chart: … -->` marker over it renders as a typeset
chart. The marker is a plain HTML comment, so on GitHub (and through
pandoc) each one stays an ordinary table; textli is where it becomes a
chart.

## Bar chart

`type` is the word after `chart:`; `x=` names the column that labels the x
axis. Every other column is a series, named by its header:

<!-- chart: bar x=Quarter -->
| Quarter | 2025 | 2026 |
| ------- | ---- | ---- |
| Q1      | 3.2  | 4.1  |
| Q2      | 5.1  | 4.9  |
| Q3      | 4.4  | 5.6  |
| Q4      | 6.0  | 6.3  |

## Line chart, a `y=` subset and a unit

`line` draws a polyline per series. `y=` picks which columns to plot — here
just `latency`, leaving `throughput` out — and a header's trailing unit
(`latency [ms]`) lifts to the y-axis label:

<!-- chart: line x=build y=latency -->
| build | latency [ms] | throughput |
| ----- | ------------ | ---------- |
| v1    | 120          | 900        |
| v2    | 96           | 1100       |
| v3    | 88           | 1180       |
| v4    | 71           | 1240       |

Leave `y=` off and every non-x column is plotted; leave `x=` off and the
first column labels the axis.

## Chart *and* table — the `table` flag

Sometimes the reader needs the exact values, not just the shape. A bare
`table` flag keeps the data on the page — the chart renders first, the
table follows:

<!-- chart: bar x=Method table -->
| Method   | precision | recall |
| -------- | --------- | ------ |
| baseline | 0.71      | 0.64   |
| ours     | 0.83      | 0.79   |

That's the whole vocabulary — three keys and one flag, no styling.

## When it's just a table

Anything the marker gets wrong falls back to the plain table, and the
marker stays invisible. An unknown type:

<!-- chart: pie x=part -->
| part | share |
| ---- | ----- |
| a    | 40    |
| b    | 60    |

A non-numeric cell, an `x=` that names no column, or a marker with no table
under it does the same. The page is never broken — worst case, you get the
table you wrote.

## Review works on charts

A chart reviews like a formula: put the caret on it and press `c` to
comment or `s` to suggest. The annotation lands on the whole marker + table
source, and the chart keeps rendering under the mark.
