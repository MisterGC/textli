"""Open-file matching: history is fuzzy over full paths, the filesystem only
completes per segment, and the two merge into one ranked suggestion list."""

from __future__ import annotations

import os

from textli.openfile import (
    HISTORY_MAX,
    Candidate,
    common_prefix,
    fuzzy_score,
    history_dirs,
    looks_like_path,
    push_history,
    rank_history,
    segment_complete,
    suggestions,
)


# ── history LRU ──

def test_push_history_promotes_dedupes_and_caps():
    h = []
    h = push_history(h, "/a/one.md")
    h = push_history(h, "/a/two.md")
    h = push_history(h, "/a/one.md")            # reopened — moves to front
    assert h == ["/a/one.md", "/a/two.md"]
    for i in range(HISTORY_MAX + 50):
        h = push_history(h, f"/bulk/f{i}.md")
    assert len(h) == HISTORY_MAX
    assert h[0] == f"/bulk/f{HISTORY_MAX + 49}.md"


def test_history_dirs_derives_recent_first_with_trailing_slash():
    h = ["/docs/b.md", "/docs/a.md", "/notes/x.md"]
    assert history_dirs(h) == ["/docs/", "/notes/"]


# ── fuzzy scoring ──

def test_fuzzy_segment_start_matches_mid_path():
    # the user's canonical case: type a late segment, get the full path
    s = fuzzy_score("special", "/my/cool/special_path/doc.md")
    assert s is not None and s > 100    # contiguous + boundary


def test_fuzzy_prefers_boundary_and_basename():
    boundary = fuzzy_score("doc", "/x/doc_plan.md")
    buried = fuzzy_score("doc", "/x/undocked.md")
    assert boundary is not None and buried is not None
    assert boundary > buried


def test_fuzzy_subsequence_matches_and_nonmatch_is_none():
    assert fuzzy_score("mcd", "/my/cool/doc.md") is not None
    assert fuzzy_score("xyz", "/my/cool/doc.md") is None


def test_fuzzy_shorter_candidate_wins_ties():
    short = fuzzy_score("notes", "/a/notes.md")
    long = fuzzy_score("notes", "/a/very/long/way/down/notes.md")
    assert short is not None and long is not None
    assert short > long


def test_rank_history_recency_breaks_ties():
    h = ["/recent/notes.md", "/older/notes.md"]
    ranked = rank_history("notes", h)
    assert ranked.index("/recent/notes.md") < ranked.index("/older/notes.md")


def test_rank_history_includes_matching_dirs():
    h = ["/mydocs/my_cool_doc1.md"]
    ranked = rank_history("my", h)
    assert "/mydocs/my_cool_doc1.md" in ranked
    assert "/mydocs/" in ranked


# ── filesystem segment completion ──

def test_bare_word_is_not_a_path():
    assert not looks_like_path("my")
    assert looks_like_path("/Ho")
    assert looks_like_path("~/no")
    assert looks_like_path("docs/ch")


def test_segment_complete_matches_only_the_last_segment(tmp_path):
    (tmp_path / "Home").mkdir()
    (tmp_path / "Hollow").mkdir()
    (tmp_path / "other").mkdir()
    (tmp_path / "other" / "Home").mkdir()      # deep — must NOT surface
    got = segment_complete(f"{tmp_path}/Ho")
    assert got == [f"{tmp_path}/Hollow/", f"{tmp_path}/Home/"]   # name order


def test_segment_complete_lists_dirs_and_md_only(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "note.md").touch()
    (tmp_path / "image.png").touch()
    (tmp_path / ".hidden.md").touch()
    got = segment_complete(f"{tmp_path}/")
    assert got == [f"{tmp_path}/sub/", f"{tmp_path}/note.md"]


def test_segment_complete_hidden_only_when_asked(tmp_path):
    (tmp_path / ".hidden.md").touch()
    assert segment_complete(f"{tmp_path}/.h") == [f"{tmp_path}/.hidden.md"]


def test_segment_complete_bad_dir_is_empty():
    assert segment_complete("/definitely/not/there/x") == []


def test_bare_word_never_hits_the_filesystem(tmp_path, monkeypatch):
    (tmp_path / "myfile.md").touch()
    monkeypatch.chdir(tmp_path)
    assert segment_complete("my") == []


# ── merged suggestions ──

def test_suggestions_history_first_then_filesystem(tmp_path):
    (tmp_path / "Home").mkdir()
    (tmp_path / "Hotel").mkdir()               # filesystem-only candidate
    hist = [f"{tmp_path}/Home/old.md"]
    rows = suggestions(f"{tmp_path}/Ho", hist)
    assert rows[0] == Candidate(f"{tmp_path}/Home/old.md", from_history=True)
    # Home/ is a *history-derived* dir (old.md's parent) — deduped as history;
    # Hotel/ is unknown to history, so it arrives via segment completion, after.
    assert Candidate(f"{tmp_path}/Home/", from_history=True) in rows
    fs_only = Candidate(f"{tmp_path}/Hotel/", from_history=False)
    assert fs_only in rows
    assert rows.index(fs_only) > rows.index(
        Candidate(f"{tmp_path}/Home/", from_history=True))


def test_suggestions_dedupe_history_over_filesystem(tmp_path):
    (tmp_path / "docs").mkdir()
    hist = [f"{tmp_path}/docs/a.md"]           # derived dir == fs completion
    rows = suggestions(f"{tmp_path}/do", hist)
    dirs = [r for r in rows if r.path == f"{tmp_path}/docs/"]
    assert len(dirs) == 1 and dirs[0].from_history


def test_suggestions_empty_query_shows_recent_history():
    hist = ["/a/one.md", "/b/two.md"]
    rows = suggestions("", hist)
    assert [r.path for r in rows[:2]] == hist
    assert all(r.from_history for r in rows)


def test_suggestions_bare_word_stays_history_only(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "myfile.md").touch()           # in cwd — must NOT surface
    rows = suggestions("my", ["/mydocs/doc.md"])
    paths = [r.path for r in rows]
    assert set(paths) == {"/mydocs/doc.md", "/mydocs/"}
    assert all(r.from_history for r in rows)


# ── Tab completion prefix ──

def test_common_prefix():
    assert common_prefix(["/a/docs/", "/a/dogs.md"]) == "/a/do"
    assert common_prefix(["/only/one.md"]) == "/only/one.md"
    assert common_prefix([]) == ""
