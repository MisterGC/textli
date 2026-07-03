"""In-document search: per-line fuzzy hits in document order, emphasis ranges,
and the n/N wrap-around navigation."""

from __future__ import annotations

from textli.search import Hit, find_hits, line_match, next_hit, rank

TEXT = (
    "# Verification plan\n"          # line 0
    "\n"
    "The pipeline emits artifacts.\n"  # line 2
    "Nothing here.\n"
    "A special_path appears once.\n"   # line 4
    "\n"
    "pipeline again, at the end.\n"    # line 6
)


def test_hits_are_per_line_and_in_document_order():
    hits = find_hits(TEXT, "pipeline")
    assert [h.line_no for h in hits] == [2, 6]
    assert all(isinstance(h, Hit) for h in hits)
    # offsets address the searched text
    assert TEXT[hits[0].start:hits[0].end] == "The pipeline emits artifacts."


def test_fuzzy_stays_inside_one_word():
    # in-word subsequence matches...
    assert [h.line_no for h in find_hits(TEXT, "spcl")] == [4]   # special_path
    # ...but fuzzy never crosses a word boundary
    assert find_hits(TEXT, "specialonce") == []
    assert find_hits(TEXT, "zzzz") == []


def test_multi_token_query_matches_word_per_token():
    hits = find_hits(TEXT, "special once")
    assert [h.line_no for h in hits] == [4]
    # both matched words carry an emphasis span
    line = hits[0].text
    marked = [line[a:b] for a, b in hits[0].spans]
    assert marked == ["special_path", "once."]


def test_case_insensitive_and_empty_query():
    assert [h.line_no for h in find_hits(TEXT, "VERIFICATION")] == [0]
    assert find_hits(TEXT, "") == []
    assert find_hits(TEXT, "   ") == []


def test_line_match_phrase_span():
    score, spans = line_match("pipeline", "The pipeline emits")
    assert spans == ((4, 12),)
    score, spans = line_match("PIPE", "The pipeline emits")
    assert spans == ((4, 8),)
    assert line_match("tpe", "The pipeline emits") is None   # crosses words


def test_cross_word_noise_never_matches():
    # Regression from the wild: "right" is a subsequence of soRts dynamIc …
    # paGes alpHabeTically — one stray char per word. Fuzzy is word-bounded,
    # so that line simply cannot match.
    noise = "   sorts dynamic module pages alphabetically below\n"
    assert find_hits(noise, "right") == []


def test_rank_puts_phrase_above_word_matches():
    text = ("once here, and special there\n"             # word-level match
            "a special once phrase in full\n")           # contiguous phrase
    hits = find_hits(text, "special once")
    assert [h.line_no for h in hits] == [0, 1]           # document order
    ranked = rank(hits)
    assert [h.line_no for h in ranked] == [1, 0]         # phrase first
    assert ranked[0].score > ranked[1].score


def test_next_hit_steps_and_wraps_both_ways():
    hits = find_hits(TEXT, "pipeline")
    first, second = hits
    assert next_hit(hits, 0, +1) == first
    assert next_hit(hits, first.start, +1) == second
    assert next_hit(hits, second.start, +1) == first          # wrap forward
    assert next_hit(hits, second.start, -1) == first
    assert next_hit(hits, first.start, -1) == second          # wrap backward
    assert next_hit([], 0, +1) is None
