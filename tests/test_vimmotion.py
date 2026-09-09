"""Where vim motions land and what text objects cover — pure text, no widget.

These are the rules that make the handler feel like vim (or not), so they're
pinned here directly rather than only through key sequences.
"""

from __future__ import annotations

from textli import vimmotion as vm

# f0 o1 o2 (3 b4 a5 r6 )7 ␣8 b9 a10 z11
LINE = "foo(bar) baz"
DOC = "first one\nsecond two\n\nafter blank\n"


def test_word_forward_stops_between_word_and_punctuation():
    assert vm.word_forward(LINE, 0) == 3        # foo -> (
    assert vm.word_forward(LINE, 3) == 4        # (   -> bar
    assert vm.word_forward(LINE, 4) == 7        # bar -> )
    assert vm.word_forward(LINE, 7) == 9        # )   -> baz


def test_big_word_forward_is_whitespace_delimited():
    assert vm.word_forward(LINE, 0, big=True) == 9      # foo(bar) is one WORD


def test_word_forward_counts_and_clamps():
    assert vm.word_forward(LINE, 0, 3) == 7
    assert vm.word_forward(LINE, 0, 99) == len(LINE)


def test_word_end_is_the_last_character_of_the_word():
    assert vm.word_end(LINE, 0) == 2            # end of foo
    assert vm.word_end(LINE, 0, 2) == 3         # end of (
    assert vm.word_end(LINE, 9) == 11           # end of baz
    assert vm.word_end(LINE, 0, big=True) == 7  # end of foo(bar)


def test_word_backward():
    assert vm.word_backward(LINE, 11) == 9
    assert vm.word_backward(LINE, 9) == 7
    assert vm.word_backward(LINE, 0) == 0       # clamps at the start
    assert vm.word_backward(LINE, 11, big=True) == 9


def test_word_motions_stop_on_an_empty_line():
    # An empty line is a word of its own in vim, so `w` pauses there rather
    # than skipping the paragraph break.
    text = "one\n\ntwo\n"
    assert vm.word_forward(text, 0) == 4        # the empty line
    assert vm.word_forward(text, 4) == 5        # then the next word


def test_line_helpers():
    assert vm.line_start(DOC, 12) == 10
    assert vm.line_end(DOC, 12) == 20
    assert vm.first_non_blank("   indented", 8) == 3
    assert vm.first_non_blank("      ", 2) == 6   # all blank -> the line end
    assert vm.line_number(DOC, 0) == 1
    assert vm.line_number(DOC, 12) == 2


def test_goto_line_clamps_and_lands_on_the_first_non_blank():
    assert vm.goto_line("a\n  b\nc\n", 2) == 4
    assert vm.goto_line("a\nb\n", 99) == 4        # past the end -> last line
    assert vm.goto_line("a\nb\n", 0) == 0


def test_paragraph_motions_land_on_the_blank_line():
    assert vm.paragraph_forward(DOC, 0) == 21    # the empty line
    assert vm.paragraph_forward(DOC, 0, 2) == len(DOC)   # then the end
    assert vm.paragraph_backward(DOC, 25) == 21
    assert vm.paragraph_backward(DOC, 5) == 0


def test_find_char_stays_on_its_line():
    assert vm.find_char(LINE, 0, "b") == 4
    assert vm.find_char(LINE, 0, "b", 2) == 9
    assert vm.find_char(LINE, 0, "b", till=True) == 3
    assert vm.find_char(LINE, 11, "f", forward=False) == 0
    assert vm.find_char(LINE, 0, "Q") is None
    # A hit on the *next* line must not count.
    assert vm.find_char("ab\ncd\n", 0, "c") is None


def test_matching_bracket_is_nesting_aware():
    assert vm.matching_bracket("f(a b) x", 1) == 5
    assert vm.matching_bracket("f(a b) x", 5) == 1
    assert vm.matching_bracket("f(a (b) c)", 0) == 9
    assert vm.matching_bracket("no brackets", 0) is None


def test_word_object_inner_and_a():
    assert LINE[slice(*vm.word_object(LINE, 5, inner=True))] == "bar"
    assert LINE[slice(*vm.word_object(LINE, 5, inner=False))] == "bar"
    # `aw` takes the trailing space when there is one...
    text = "aaa bbb ccc"
    assert text[slice(*vm.word_object(text, 4, inner=False))] == "bbb "
    # ...and the leading one when the word ends the line.
    assert text[slice(*vm.word_object(text, 8, inner=False))] == " ccc"


def test_word_object_does_not_cross_a_newline():
    text = "one\ntwo"
    assert text[slice(*vm.word_object(text, 0, inner=True))] == "one"
    assert vm.word_object(text, 3, inner=True) is None    # on the newline


def test_bracket_object():
    assert LINE[slice(*vm.bracket_object(LINE, 5, "(", ")", inner=True))] == "bar"
    assert LINE[slice(*vm.bracket_object(LINE, 5, "(", ")", inner=False))] == "(bar)"
    # From the bracket itself, and through a nested pair.
    assert LINE[slice(*vm.bracket_object(LINE, 3, "(", ")", inner=True))] == "bar"
    nested = "f(a (b) c)"
    assert nested[slice(*vm.bracket_object(nested, 5, "(", ")", inner=True))] == "b"
    assert nested[slice(*vm.bracket_object(nested, 2, "(", ")", inner=True))] == "a (b) c"
    assert vm.bracket_object("none here", 2, "(", ")", inner=True) is None


def test_bracket_object_spans_lines():
    text = "f(\n  a\n)"
    assert text[slice(*vm.bracket_object(text, 4, "(", ")", inner=True))] == "\n  a\n"


def test_quote_object_pairs_from_the_left_and_honours_escapes():
    q = 'say "hello" ok'
    assert q[slice(*vm.quote_object(q, 6, '"', inner=True))] == "hello"
    assert q[slice(*vm.quote_object(q, 6, '"', inner=False))] == '"hello"'
    # Looking forward from before the opening quote finds the string.
    assert q[slice(*vm.quote_object(q, 0, '"', inner=True))] == "hello"
    esc = 'a "b \\" c" d'
    assert esc[slice(*vm.quote_object(esc, 3, '"', inner=True))] == 'b \\" c'
    assert vm.quote_object("no quotes", 2, '"', inner=True) is None


def test_paragraph_object():
    assert DOC[slice(*vm.paragraph_object(DOC, 0, inner=True))] == \
        "first one\nsecond two"
    assert DOC[slice(*vm.paragraph_object(DOC, 0, inner=False))] == \
        "first one\nsecond two\n"
