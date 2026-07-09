"""Whisper status line content (textli.status) — pure formatting, no Qt."""

from __future__ import annotations

from textli.status import read_status, word_count, write_status


def test_word_count_counts_the_accepted_prose():
    # suggestions resolve as accepted, comment bodies drop, spans stay
    src = "one {--gone --}{~~old~>two~~} {++three ++}{==four==}{>>note<<}\n"
    assert word_count(src) == 4
    assert word_count("") == 0
    assert word_count("plain words here\n") == 3


def test_write_status_mode_words_and_delta():
    assert write_status("NORMAL", 1234, 0) == "NORMAL · 1,234 words"
    assert write_status("INSERT", 1290, 56) == "INSERT · 1,290 words · +56"
    assert write_status("NORMAL", 1200, -34) == "NORMAL · 1,200 words · -34"


def test_read_status_progress_and_time_left():
    # 220 words/min: 440 words at the top ≈ 2 min of reading ahead
    assert read_status(0.0, 440) == "0% · ~2 min left"
    # at the end there is nothing left to read
    assert read_status(1.0, 440) == "100%"
    assert read_status(2.5, 440) == "100%"          # clamped
    # partial progress rounds the percent, ceils the minutes
    assert read_status(0.42, 1000).startswith("42% · ~3 min left")


def test_read_status_review_counts_and_plurals():
    s = read_status(0.5, 220, changes=3, comment_count=1)
    assert s.endswith("3 changes · 1 comment")
    assert "change" not in read_status(0.5, 220)     # nothing pending, no noise


def test_read_status_section_breadcrumb_leads():
    # the section under the caret prefixes the whisper, then progress etc.
    assert read_status(0.42, 1000, section="Design").startswith(
        "§ Design · 42%")
    s = read_status(0.5, 220, changes=2, section="Architecture")
    assert s == "§ Architecture · 50% · ~1 min left · 2 changes"
    # no section (before the first heading) → no breadcrumb, no stray marker
    assert "§" not in read_status(0.5, 220)


def test_read_status_section_elides_when_long():
    long = "A very long heading that would otherwise crowd the whole whisper"
    s = read_status(0.0, 220, section=long)
    head = s.split(" · ")[0]
    assert head.startswith("§ ") and head.endswith("…")
    assert len(head) <= 2 + 48        # "§ " + capped section


def test_read_status_link_target_leads_and_wins_over_section():
    # on a link, the whisper shows where Enter goes instead of the section
    s = read_status(0.3, 500, section="Design", link="other.md")
    assert s.startswith("→ other.md · 30%")
    assert "§" not in s
    # progress/review parts still follow the link crumb
    s2 = read_status(0.5, 220, changes=2, link="https://example.com")
    assert s2 == "→ https://example.com · 50% · ~1 min left · 2 changes"
