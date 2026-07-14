"""Unit tests for pandoc-style math extraction (textli.formulas)."""

from __future__ import annotations

from textli import formulas as mf
from textli.comments import SENTINEL_END, SENTINEL_START


def test_no_math_is_identity():
    src = "# Title\n\nJust plain prose, nothing mathematical."
    assert mf.parse(src) == []
    assert mf.substitute(src, [], lambda i, f: "") == src


def test_inline_math_parsed():
    src = "The relation $E = mc^2$ holds."
    (f,) = mf.parse(src)
    assert f.tex == "E = mc^2"
    assert not f.display
    assert src[f.start:f.end] == "$E = mc^2$"


def test_display_math_parsed():
    src = "Behold:\n\n$$\\int_0^1 x\\,dx = \\tfrac12$$\n\nQ.E.D."
    (f,) = mf.parse(src)
    assert f.tex == "\\int_0^1 x\\,dx = \\tfrac12"
    assert f.display


def test_display_math_spans_lines_but_not_blank_lines():
    src = "$$\na + b\n= c\n$$"
    (f,) = mf.parse(src)
    assert f.display
    assert "a + b" in f.tex
    assert mf.parse("$$a\n\nb$$") == []


def test_dollar_amounts_stay_prose():
    for src in (
        "It costs $5 and $10 in total.",
        "Pay $5, get $10 back.",
        "A $20 bill.",
        "between $1.5M and $2M",
    ):
        assert mf.parse(src) == [], src


def test_space_padded_dollars_are_not_math():
    assert mf.parse("a $ b $ c") == []
    assert mf.parse("a $x $ b") == []
    assert mf.parse("a $ x$ b") == []


def test_closing_dollar_before_digit_is_not_math():
    # "$a$5" would need the closing $ to sit before a digit — prose.
    assert mf.parse("win $a$5 more") == []


def test_escaped_dollar_never_opens():
    assert mf.parse(r"literal \$5 and \$x\$ stay put") == []


def test_math_inside_inline_code_is_literal():
    assert mf.parse("use `$x$` to write math") == []


def test_math_inside_fenced_block_is_literal():
    src = "```\nprice = $x$\n$$block$$\n```\n"
    assert mf.parse(src) == []


def test_math_after_fenced_block_is_found():
    src = "```\n$nope$\n```\n\nbut $yes$ here"
    (f,) = mf.parse(src)
    assert f.tex == "yes"


def test_inline_math_may_contain_dollarless_tex():
    (f,) = mf.parse(r"so $\sigma^2 = \frac{1}{N}\sum (x_i-\mu)^2$ then")
    assert f.tex == r"\sigma^2 = \frac{1}{N}\sum (x_i-\mu)^2"


def test_no_phantom_inline_inside_display():
    # A lone $ inside display content must not spawn an inline span around it.
    src = "$$a \\text{x $b$ y} c$$"
    spans = mf.parse(src)
    assert len(spans) == 1
    assert spans[0].display


def test_inline_math_never_crosses_lines():
    assert mf.parse("a $x\ny$ b") == []


def test_math_does_not_cross_sentinels():
    # A $ pair straddling a comment-highlight boundary is not a formula.
    src = f"a $x {SENTINEL_START}y$ z{SENTINEL_END} b"
    assert mf.parse(src) == []


def test_math_inside_sentineled_span_is_found():
    # Math wholly inside a commented span still renders.
    src = f"a {SENTINEL_START}the $x^2$ term{SENTINEL_END} b"
    (f,) = mf.parse(src)
    assert f.tex == "x^2"


def test_adjacent_inline_spans_stay_separate():
    a, b = mf.parse("$a$ and $b$")
    assert (a.tex, b.tex) == ("a", "b")


def test_substitute_replaces_in_order():
    src = "x $a$ y $$b$$ z"
    spans = mf.parse(src)
    out = mf.substitute(src, spans, lambda i, f: f"<{i}>")
    assert out == "x <0> y <1> z"


def test_code_span_wraps_with_longer_run():
    assert mf.code_span("$x$") == "`$x$`"
    assert mf.code_span("$a `b` c$") == "``$a `b` c$``"


def test_spans_in_line_finds_both_kinds():
    line = "a $x$ b $$y$$ c"
    assert mf.spans_in_line(line) == [(2, 5, False), (8, 13, True)]


def test_spans_in_line_ignores_prose_dollars():
    assert mf.spans_in_line("costs $5 and $10 today") == []
