"""In-document search: per-line fuzzy hits in document order, emphasis ranges,
and the n/N wrap-around navigation."""

from __future__ import annotations

from textli.search import Hit, find_hits, initial_index, match_range, next_hit

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


def test_fuzzy_matches_scattered_words():
    # subsequence across the line — same scorer as the go dialog
    hits = find_hits(TEXT, "specialonce")
    assert [h.line_no for h in hits] == [4]
    assert find_hits(TEXT, "zzzz") == []


def test_case_insensitive_and_empty_query():
    assert [h.line_no for h in find_hits(TEXT, "VERIFICATION")] == [0]
    assert find_hits(TEXT, "") == []
    assert find_hits(TEXT, "   ") == []


def test_match_range_substring_vs_scattered():
    assert match_range("pipeline", "The pipeline emits") == (4, 12)
    assert match_range("PIPE", "The pipeline emits") == (4, 8)
    assert match_range("tpe", "The pipeline emits") is None


def test_initial_index_anchors_at_caret():
    hits = find_hits(TEXT, "pipeline")
    assert initial_index(hits, 0) == 0
    after_first = hits[0].end + 1
    assert initial_index(hits, after_first) == 1
    assert initial_index(hits, len(TEXT)) == 0        # past everything — wrap


def test_next_hit_steps_and_wraps_both_ways():
    hits = find_hits(TEXT, "pipeline")
    first, second = hits
    assert next_hit(hits, 0, +1) == first
    assert next_hit(hits, first.start, +1) == second
    assert next_hit(hits, second.start, +1) == first          # wrap forward
    assert next_hit(hits, second.start, -1) == first
    assert next_hit(hits, first.start, -1) == second          # wrap backward
    assert next_hit([], 0, +1) is None
