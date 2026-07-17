"""Source references in prose: the chip grammar and the bounded upward
resolver (#37). Pure logic — no Qt, no QApplication."""

from __future__ import annotations

import os

import pytest

from textli import srcref


# ── The grammar: what counts as a reference ──────────────────────────

@pytest.mark.parametrize("text, path, line, end", [
    ("textli/editor.py", "textli/editor.py", None, None),
    ("comments.py", "comments.py", None, None),
    ("README.md", "README.md", None, None),
    ("textli/editor.py:2455", "textli/editor.py", 2455, None),
    ("view.py:5089-5881", "view.py", 5089, 5881),
    ("view.py:5089–5881", "view.py", 5089, 5881),      # en dash
    ("view.py:5089—5881", "view.py", 5089, 5881),      # em dash
    ("docs/keybindings.md:12", "docs/keybindings.md", 12, None),
    ("../sibling/thing.qml", "../sibling/thing.qml", None, None),
    ("~/dev/textli/textli/paper.py", "~/dev/textli/textli/paper.py", None, None),
    ("Makefile:12", "Makefile", 12, None),             # anchor earns it
    ("a/b/c/deep_file-2.tsx:9", "a/b/c/deep_file-2.tsx", 9, None),
])
def test_parse_accepts_real_references(text, path, line, end):
    ref = srcref.parse_ref(text)
    assert ref is not None, text
    assert (ref.path, ref.line, ref.end_line) == (path, line, end)


@pytest.mark.parametrize("text", [
    "",                     # empty chip
    "   ",
    "setMarkdown",          # a plain identifier
    "_CTRL_MOD",
    "ZenMarkdownEditor",
    ".md",                  # a file *type*, not a file
    ".py",
    "-r/--read",            # a CLI flag pair — has '/', but no extension
    "a/b/",                 # a folder
    "mgc/groundwork/",
    "$E = mc^2$",           # spaces and markup
    "{==span==}",
    "c / s",
    "https://example.com/a.py",     # a URL is the link machinery's job
    "Makefile",             # extensionless and unanchored — too prose-like
    "3.14",                 # a number, not name.ext
    "..",
])
def test_parse_rejects_prose_chips(text):
    assert srcref.parse_ref(text) is None


def test_lines_normalizes_the_anchored_range():
    assert srcref.parse_ref("a.py").lines is None
    assert srcref.parse_ref("a.py:7").lines == (7, 7)
    assert srcref.parse_ref("a.py:7-9").lines == (7, 9)
    assert srcref.parse_ref("a.py:9-7").lines == (7, 9)      # read as meant


# ── The resolver: doc-relative, then up, bounded ─────────────────────

@pytest.fixture
def repo(tmp_path):
    """A repo that mirrors this project's shape: docs live two levels down
    from the root they reference."""
    (tmp_path / "repo" / ".git").mkdir(parents=True)
    (tmp_path / "repo" / "textli").mkdir()
    (tmp_path / "repo" / "textli" / "editor.py").write_text("x = 1\n")
    (tmp_path / "repo" / "mgc" / "groundwork").mkdir(parents=True)
    (tmp_path / "repo" / "mgc" / "groundwork" / "sibling.md").write_text("s\n")
    (tmp_path / "outside.py").write_text("out\n")        # above the repo root
    return tmp_path


def test_resolves_a_root_relative_ref_from_a_nested_doc(repo):
    doc_dir = str(repo / "repo" / "mgc" / "groundwork")
    got = srcref.resolve("textli/editor.py", doc_dir)
    assert got == str(repo / "repo" / "textli" / "editor.py")


def test_doc_relative_wins_over_the_ancestors(repo):
    # The same name exists beside the doc and at the root; nearest wins.
    (repo / "repo" / "editor.py").write_text("root\n")
    doc_dir = str(repo / "repo" / "mgc" / "groundwork")
    (repo / "repo" / "mgc" / "groundwork" / "editor.py").write_text("near\n")
    assert srcref.resolve("editor.py", doc_dir) == \
        str(repo / "repo" / "mgc" / "groundwork" / "editor.py")


def test_sibling_reference_still_resolves(repo):
    doc_dir = str(repo / "repo" / "mgc" / "groundwork")
    assert srcref.resolve("sibling.md", doc_dir) == \
        str(repo / "repo" / "mgc" / "groundwork" / "sibling.md")


def test_the_walk_stops_at_the_git_root(repo):
    # 'outside.py' sits above the repo root and must stay unreachable.
    doc_dir = str(repo / "repo" / "mgc" / "groundwork")
    assert srcref.resolve("outside.py", doc_dir) is None


def test_a_worktree_dot_git_file_bounds_the_walk_too(repo, tmp_path):
    # git worktrees write '.git' as a *file*; existence is the test, not type.
    wt = tmp_path / "wt"
    (wt / "docs").mkdir(parents=True)
    (wt / ".git").write_text("gitdir: /elsewhere\n")
    assert srcref.resolve("outside.py", str(wt / "docs")) is None


def test_missing_target_resolves_to_none(repo):
    doc_dir = str(repo / "repo" / "mgc" / "groundwork")
    assert srcref.resolve("textli/nope.py", doc_dir) is None


def test_a_directory_is_not_a_resolution(repo):
    doc_dir = str(repo / "repo" / "mgc" / "groundwork")
    assert srcref.resolve("textli", doc_dir) is None


def test_absolute_and_tilde_paths_are_taken_at_face_value(repo, monkeypatch):
    target = repo / "repo" / "textli" / "editor.py"
    assert srcref.resolve(str(target), "/nowhere") == str(target)
    assert srcref.resolve(str(repo / "repo" / "nope.py"), "/nowhere") is None
    monkeypatch.setenv("HOME", str(repo / "repo"))
    monkeypatch.delenv("USERPROFILE", raising=False)
    assert srcref.resolve("~/textli/editor.py", "/nowhere") == str(target)


def test_walk_terminates_without_a_repo_or_home_on_the_chain(tmp_path,
                                                             monkeypatch):
    # No .git anywhere and HOME off the chain: the walk must still end (at the
    # filesystem root) and answer None rather than spin.
    monkeypatch.setenv("HOME", str(tmp_path / "elsewhere"))
    deep = tmp_path / "a" / "b" / "c" / "d"
    deep.mkdir(parents=True)
    assert srcref.resolve("nothing/here.py", str(deep)) is None


def test_unreadable_ancestors_fail_closed(tmp_path):
    # A permission-denied directory on the chain must read as 'not here', not
    # raise — the walk continues and simply finds nothing.
    if os.geteuid() == 0:
        pytest.skip("root ignores directory permissions")
    locked = tmp_path / "locked"
    (locked / "docs").mkdir(parents=True)
    locked.chmod(0o000)
    try:
        assert srcref.resolve("textli/editor.py", str(locked / "docs")) is None
    finally:
        locked.chmod(0o755)          # let tmp_path clean up


# ── The bare-name sweep: prose names modules without their folder ────

def test_a_bare_module_name_is_found_inside_the_repo(repo):
    # CLAUDE.md-style prose: `editor.py`, not `textli/editor.py`.
    doc_dir = str(repo / "repo")
    assert srcref.resolve("editor.py", doc_dir) == \
        str(repo / "repo" / "textli" / "editor.py")


def test_an_ambiguous_bare_name_resolves_to_nothing(repo):
    # Two files of that name — guessing one would be worse than a whisper.
    (repo / "repo" / "other").mkdir()
    (repo / "repo" / "other" / "editor.py").write_text("dupe\n")
    assert srcref.resolve("editor.py", str(repo / "repo")) is None


def test_the_sweep_skips_vendored_and_cache_trees(repo):
    # The copy in .venv must neither be found nor make the real file ambiguous.
    vendored = repo / "repo" / ".venv" / "lib" / "textli"
    vendored.mkdir(parents=True)
    (vendored / "editor.py").write_text("vendored\n")
    (repo / "repo" / "node_modules").mkdir()
    (repo / "repo" / "node_modules" / "editor.py").write_text("vendored\n")
    assert srcref.resolve("editor.py", str(repo / "repo")) == \
        str(repo / "repo" / "textli" / "editor.py")


def test_a_spelled_out_path_never_triggers_the_sweep(repo):
    # 'textli/editor.py' exists, but 'wrong/editor.py' must stay not-found —
    # the sweep is for bare names only, it must not second-guess a real path.
    assert srcref.resolve("wrong/editor.py", str(repo / "repo")) is None


def test_no_repository_means_no_sweep(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "elsewhere"))
    (tmp_path / "loose" / "src").mkdir(parents=True)
    (tmp_path / "loose" / "src" / "editor.py").write_text("x\n")
    (tmp_path / "loose" / "docs").mkdir()
    assert srcref.resolve("editor.py", str(tmp_path / "loose" / "docs")) is None


def test_home_is_never_a_scan_root_even_as_a_repo(tmp_path, monkeypatch):
    # A dotfiles clone at ~ must not turn a keypress into a sweep of $HOME.
    home = tmp_path / "home"
    (home / ".git").mkdir(parents=True)
    (home / "notes").mkdir()
    (home / "deep").mkdir()
    (home / "deep" / "editor.py").write_text("x\n")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("USERPROFILE", raising=False)
    assert srcref._scan_root(str(home / "notes")) is None
    assert srcref.resolve("editor.py", str(home / "notes")) is None


def test_the_sweep_gives_up_on_its_directory_budget(repo, monkeypatch):
    monkeypatch.setattr(srcref, "_SCAN_DIR_BUDGET", 1)
    assert srcref.resolve("editor.py", str(repo / "repo")) is None


# ── Routing: what opens as source ────────────────────────────────────

def test_is_texty_knows_source_and_refuses_binaries(tmp_path):
    py = tmp_path / "a.py"
    py.write_text("print('hi')\n")
    png = tmp_path / "b.png"
    png.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00")
    assert srcref.is_texty(str(py))
    assert not srcref.is_texty(str(png))


def test_is_texty_sniffs_when_the_extension_says_nothing(tmp_path):
    makefile = tmp_path / "Makefile"
    makefile.write_text("all:\n\techo hi\n")
    blob = tmp_path / "mystery.xyz"
    blob.write_bytes(b"\x01\x02\x00\x03binary\x00")
    assert srcref.is_texty(str(makefile))
    assert not srcref.is_texty(str(blob))


def test_is_texty_tolerates_a_multibyte_char_cut_by_the_sniff(tmp_path):
    f = tmp_path / "unicode.xyz"
    # Fill past the sniff window so the read boundary slices a '…' (3 bytes).
    f.write_bytes(b"a" * (srcref._SNIFF_BYTES - 1) + "…".encode() * 4)
    assert srcref.is_texty(str(f))


def test_is_texty_on_a_missing_file_is_false(tmp_path):
    assert not srcref.is_texty(str(tmp_path / "ghost.py"))


# ── The synthesized fence ────────────────────────────────────────────

def test_fence_wraps_code_with_its_language():
    out = srcref.fence("x = 1\n", "python")
    assert out.startswith("```python\n")
    assert out.rstrip().endswith("```")
    assert "x = 1" in out


def test_fence_outgrows_backticks_inside_the_file():
    # A Markdown file full of ``` fences must not close the wrapper early.
    code = "text\n```python\nx = 1\n```\nmore\n"
    out = srcref.fence(code, "markdown")
    assert out.startswith("````markdown\n")
    assert out.rstrip().endswith("````")
    assert "```python" in out
