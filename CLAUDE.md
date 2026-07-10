# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

textli is a full-window, distraction-free Markdown editor built on **PySide6 (Qt
Widgets)**. It ships as two public classes — `ZenMarkdownEditor` (the full-window
editor with a rendered reading view) and `InlineVimEditor` (an embeddable
single-field vim editor) — plus a standalone `textli` CLI. Distributed on PyPI as
`textli-editor`; the command, the import (`import textli`), and the repo are all
`textli`.

## Commands

```sh
uv venv && uv pip install -e '.[dev]'          # dev setup
QT_QPA_PLATFORM=offscreen .venv/bin/pytest -q  # run the whole suite (headless)
QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/test_vim.py -q          # one file
QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/test_vim.py::test_x -q  # one test
```

- Every test needs a Qt platform. The suite is headless — use `QT_QPA_PLATFORM=offscreen`
  (each test module also `setdefault`s it, but exporting it is the reliable path).
- There is no linter/formatter config; each test module spins up its own
  `QApplication` via a local helper. `tests/conftest.py` redirects QSettings into
  a session tmp dir — editors persist state (prefs, history, positions) even on
  widget teardown, so tests must never touch the user's real preferences.
- Docs: `uv pip install -e '.[docs]'` then `.venv/bin/mkdocs serve` (MkDocs
  Material, auto-deployed to GitHub Pages on push to `main`).
- Version is derived from git tags by `hatch-vcs` and written to the
  **generated** `textli/_version.py` — never hand-edit that file.

## Architecture

The design line is: **`comments.py` is pure text logic (no Qt); `editor.py` is a
Qt coordinator.** Keep it that way — text/format parsing that can live without Qt
belongs in `comments.py` so it stays cheap to unit-test.

- **`comments.py`** — the single source of truth for the inline annotation format,
  which is [CriticMarkup](http://criticmarkup.com/). Comments are `{==span==}{>>body<<}`;
  suggestions (track-changes) are `{++insert++}`, `{--delete--}`, `{~~old~>new~~}`.
  Parsing regexes are "tempered" (a span can't swallow the next marker). All
  annotations live inline in the `.md` file, so they travel with it and diff in git —
  no sidecar files. Pure Python, no Qt import.

- **`editor.py`** (largest module, ~2000 lines) — `ZenMarkdownEditor`, a single
  `QWidget` that hosts **both** views: the editable **write view** (`QPlainTextEdit`
  + syntax highlighting) and the rendered **reading view** (`_ReadingView`, a
  `QTextBrowser`). `⌘R` toggles between them. It owns the modal card layout, dim
  wash, autosave, file-watching, comment/suggestion navigation, and the overview
  panels (headings / changes).

- **Sentinel-based rendering** — to highlight a commented/suggested span in the
  reading view, `comments.py` wraps it in private-use code points (``/``)
  that survive Qt's `setMarkdown`; the editor locates those markers in the rendered
  `QTextDocument`, applies char formats, then deletes the markers. Rendered spans are
  tagged with custom `QTextFormat` user-properties (`_COMMENT_IDX_PROP`,
  `_SUGGEST_IDX_PROP`, `_SUGGEST_ROLE_PROP`) so a fragmented span maps back to its
  source annotation.

- **`vim.py`** — `VimKeyHandler`, a stateful NORMAL/INSERT vim handler that operates
  on any `QPlainTextEdit`. Shared by both `ZenMarkdownEditor`'s write view and
  `InlineVimEditor` — the one place vim keybindings live.

- **`suggest.py`** — `SuggestionAnimator`, the accept/reject tween. It fades the
  leaving text *before* the source `.md` is mutated (so the reflow collapses on
  already-invisible glyphs), then runs the undoable source edit via callback. Kept
  out of `editor.py` on purpose.

- **`highlight.py`** — `MarkdownHighlighter` (regex syntax highlighting) plus
  `compute_focus_range` for section-focus dimming (`⌘.`).

- **`jump.py`** — `WordJumpOverlay`, an EasyMotion-style word-jump overlay.

- **`inline_editor.py`** — `InlineVimEditor`, the embeddable editor. Knows nothing
  about what it edits: host passes text in, gets it back via `committed(str)` or
  `cancelled()`. Opens in INSERT mode.

- **`app.py`** — the standalone CLI. `TextliHost` (a `QWidget`) supplies the dark
  backdrop and window lifecycle; the editor parents into it. Parses a
  `file.md#heading-slug` location argument and a `-r/--read` flag.

- **`constants.py`** — palette, layout, and typography constants. Note `_CTRL_MOD`:
  Qt swaps Control/Meta on macOS, so this resolves the physical modifier per-platform
  — use it rather than hardcoding `ControlModifier`.

## Conventions

- Python 3.12+, `from __future__ import annotations` at the top of every module.
- Reach for the shared pieces before adding a variant: vim keys → `VimKeyHandler`;
  annotation format → `comments.py`; platform modifier → `_CTRL_MOD`.
- Keybindings are documented in three places that must stay in sync: `editor_help_html()`
  (the in-app `F1` help), `README.md`, and `docs/keybindings.md`.
