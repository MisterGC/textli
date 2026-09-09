# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

textli is a full-window, distraction-free Markdown editor built on **PySide6 (Qt
Widgets)**. It ships two public classes — `ZenMarkdownEditor` (the full-window
editor with a rendered reading view) and `InlineVimEditor` (an embeddable
single-field vim editor) — a module-level theme API, and a standalone `textli`
CLI. Distributed on PyPI as `textli-editor`; the command, the import
(`import textli`), and the repo are all `textli`.

## Commands

```sh
uv venv && uv pip install -e '.[dev]'          # dev setup
QT_QPA_PLATFORM=offscreen .venv/bin/pytest -q  # run the whole suite (headless)
QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/test_vim.py -q          # one file
QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/test_vim.py::test_x -q  # one test
```

- Every test needs a Qt platform. The suite is headless — use `QT_QPA_PLATFORM=offscreen`
  (`tests/conftest.py` also `setdefault`s it, but exporting it is the reliable path).
  CI runs the same suite on Linux (under xvfb) and macOS, Python 3.12 and 3.13.
- There is no linter/formatter config; each test module spins up its own
  `QApplication` via a local helper.
- `tests/conftest.py` repoints `textli.settings.app_settings` at a throwaway INI
  for the whole session and **deliberately never restores it** — editors persist
  state on teardown (`hideEvent`), after per-test monkeypatches are undone, so
  tests must never be able to touch the user's real preferences.
- Docs: `uv pip install -e '.[docs]'` then `.venv/bin/mkdocs serve` (MkDocs
  Material, auto-deployed to GitHub Pages on push to `main`).
- Version is derived from git tags by `hatch-vcs` and written to the
  **generated** `textli/_version.py` — never hand-edit that file.

## CLI surface

`textli <file>[#heading-slug]` with `-r/--read` or `-w/--write` (mutually
exclusive, override the file's remembered view) and `--pdf [PATH]` (typeset and
exit, no window). `textli skill …` is dispatched in `app.py:main` **before any Qt
setup** — that path must keep working without a display.

## Architecture

The organizing line is: **pure text/format logic stays Qt-free; `editor.py` is
the Qt coordinator.** Anything that can be computed without Qt belongs in its own
module so it stays cheap to unit-test. Follow this when adding features — it is
why the suite is fast and why `editor.py` hasn't collapsed under its own weight.

### The coordinator

- **`editor.py`** (~5500 lines, by far the largest) — `ZenMarkdownEditor`, a
  single `QWidget` hosting **both** views: the editable **write view**
  (`_WriteView`, a `QPlainTextEdit` + syntax highlighting) and the rendered
  **reading view** (`_ReadingView`, a `QTextBrowser`). `⌘R` toggles them. It owns
  the modal card layout, dim wash, autosave, file-watching/live reload,
  comment/suggestion navigation, overview panels, and all Qt wiring for the pure
  modules below. `editor_help_html()` (the in-app `F1` help) lives here too.

### Pure logic (no Qt import — keep it that way)

- **`comments.py`** — the single source of truth for the inline annotation
  format, [CriticMarkup](http://criticmarkup.com/). Comments are
  `{==span==}{>>body<<}`; suggestions (track-changes) are `{++insert++}`,
  `{--delete--}`, `{~~old~>new~~}`. Parsing regexes are "tempered" (a span can't
  swallow the next marker). Annotations live inline in the `.md`, so they travel
  with the file and diff in git — no sidecar files.
- **`formulas.py`** — pandoc-style `$…$` / `$$…$$` TeX math. Delimiter rules are
  pandoc's, deliberately strict so prose dollars ("costs $5 and $10") stay prose;
  `$` inside code spans/fences is always code (via `comments.code_ranges`).
- **`charts.py`** — a `<!-- chart: bar x=Quarter -->` marker comment opts the
  following pipe table into a rendered chart. The marker is an ordinary HTML
  comment so the source stays portable pandoc Markdown.
- **`callouts.py`** — the `> [!NOTE]` / `> [!WARNING]` marker at the head of a
  blockquote's first line (GitHub/Obsidian admonitions). Only the five kinds
  GitHub defines count; an unknown `[!X]` stays a plain blockquote. The
  kind → palette-role mapping lives in `theme.py`, the label block and the tint
  in `editor.py`.
- **`srcref.py`** — source references in prose (`` `textli/editor.py:2455` ``).
  Deliberately conservative: a chip counts only with a file extension or an
  explicit line anchor, so prose chips like `` `.md` `` aren't followable.
- **`vimmotion.py`** — where a vim motion lands and what a text object covers,
  over a plain string. The word-boundary rules (vim's blank/word/punctuation
  classes) are the part that has to *feel* like vim, so they're unit-tested
  without a widget; `vim.py` stays the Qt half that turns an answer into a
  cursor move or an edit.
- **`links.py`** — which Markdown link covers a caret column (inline links win
  over the bare URL inside their own parens).
- **`search.py`** — fuzzy in-document matching; phrase hits outrank word hits,
  and fuzzy never crosses a word boundary.
- **`openfile.py`** — the `go` dialog's two deliberately different matching
  modes: history matched fuzzily over the full path, filesystem completed only
  per segment (shell-style).
- **`positions.py`** — per-file position memory records (mode/caret/top/path,
  path last so the fixed fields survive any path).
- **`status.py`** — the whisper status-line strings.
- **`codeblocks.py`** — Pygments tokens reduced to four colored classes, reported
  as offset spans into the *unmodified* code string.
- **`highlight.py`** — `MarkdownHighlighter` plus `compute_focus_range` for
  section-focus dimming (`⌘.`). (Imports Qt for `QSyntaxHighlighter`, but the
  focus math is plain.)
- **`skill_install.py`** — install/check/uninstall the bundled AI skill
  (`textli/skills/textli/`) into per-tool user dirs; `skill_cli.py` adds only
  argparse, prompts, TTY detection, and exit codes.

### Rendering to pixels

Three sibling renderers, all kept out of `editor.py` on purpose, all with a
render cache (documents repeat their figures across file-watch reloads, zoom, and
view toggles) and all **degrading silently to `None`** rather than breaking the
page. The Qt wiring — rewriting the ref, attaching the resource — stays in the
editor.

- **`mathrender.py`** — ziamath sets the TeX and emits SVG; Qt rasterizes at the
  view's DPR. Unparseable formula → `None` → caller falls back to raw TeX.
- **`chartrender.py`** — hand-rolled `QPainter` renderer (no chart library, no new
  dependency), drawn in textli's own visual language on a transparent background.
- **`graflirender.py`** — `![](x.grafli)` shells out to the
  [grafli](https://github.com/MisterGC/grafli) `render` CLI. The CLI is the
  *entire* contract — no import, no Python-level coupling. Absent CLI, non-zero
  exit, timeout, or blank output all yield `None`.

### Sentinel-based rendering

To highlight a commented/suggested span in the reading view, `comments.py` wraps
it in private-use code points (`comments.SENTINEL_START` = U+E000,
`SENTINEL_END` = U+E001) that survive Qt's `setMarkdown`; the editor locates
those markers in the rendered `QTextDocument`, applies char formats, then
deletes the markers.
Rendered spans are tagged with custom `QTextFormat` user-properties
(`_COMMENT_IDX_PROP`, `_SUGGEST_IDX_PROP`, `_SUGGEST_ROLE_PROP`) so a fragmented
span maps back to its source annotation.

### Interaction surfaces

- **`vim.py`** — `VimKeyHandler`, a stateful NORMAL/INSERT/VISUAL handler that
  operates on any `QPlainTextEdit`. Shared by `ZenMarkdownEditor`'s write view
  and `InlineVimEditor` — the one place vim keybindings live. Built on vim's
  grammar (count + operator + motion/text object) rather than a table of key
  pairs, so a motion added to `_motion_for` is immediately available to `d`,
  `c`, `y` and VISUAL at once. `.` repeats a change by replaying its buffered
  keystrokes, which is why an INSERT leg (`cwword<Esc>`) repeats too.
- **`inline_editor.py`** — `InlineVimEditor`, the embeddable editor. Knows nothing
  about what it edits: host passes text in, gets it back via `committed(str)` or
  `cancelled()`. Opens in INSERT mode.
- **`suggest.py`** — `SuggestionAnimator`, the accept/reject tween. Fades the
  leaving text *before* the source `.md` is mutated (so the reflow collapses on
  already-invisible glyphs), then runs the undoable source edit via callback.
- **Overlays** — `jump.py` (EasyMotion-style word jump), `open_overlay.py` (`go`),
  `search_overlay.py` (`/`), `imageview.py` (full-window image inspector). Each is
  self-contained: the host passes data in and receives a pick via signals; the
  overlay never touches the document or the file itself.
- **`paper.py`** — the procedural paper surface (grain + horizontal light
  falloff). Both cues are deliberately below conscious notice, and the light is
  horizontal-only so vertical scroll blits can never smear it.

### Cross-cutting

- **`theme.py`** — every color the editor paints. Two **counterpart** palettes
  (warm paper / low-key dark), not inversions; dark is *derived* from the light
  theme's measured relationships. Swappable at runtime, `⌘⇧D` or
  `textli.set_theme("dark")`; open editors listen to `theme.changed`.
- **`settings.py`** — the one place `QSettings("textli", "textli")` is
  constructed, so tests can redirect it (see Commands).
- **`constants.py`** — layout and typography only (colors live in `theme.py`).
  Note `_CTRL_MOD`: Qt swaps Control/Meta on macOS, so this resolves the physical
  modifier per-platform.
- **`app.py`** — the standalone CLI. `TextliHost` (a `QWidget`) supplies the dark
  backdrop and window lifecycle; the editor parents into it.
- **`fonts.py`** — registers the bundled faces (JetBrains Mono Nerd Font, Caveat
  for handwritten comments, Literata for reading) so rendering is identical
  standalone or embedded.

## Conventions

- Python 3.12+, `from __future__ import annotations` at the top of every module.
- **Always `from textli import theme` and read `theme.X` as an attribute.** A
  `from textli.theme import X` freezes the palette at import time — the module
  globals are rebound on a theme switch. Guarded by
  `test_theme.py::test_no_module_level_bindings_freeze_the_palette`.
- Never construct `QSettings` directly — go through `settings.app_settings()`.
- Reach for the shared pieces before adding a variant: vim keys →
  `VimKeyHandler`; annotation format → `comments.py`; platform modifier →
  `_CTRL_MOD`; colors → `theme.py`.
- New optional/external capability? Follow the `graflirender.py` shape: a narrow
  contract, a cache, and silent degradation — never a dialog, never a blocked page.
- Keybindings are documented in three places that must stay in sync:
  `editor_help_html()` (the in-app `F1` help), `README.md`, and
  `docs/keybindings.md`. The prose pages (`docs/writing.md`, `docs/reading.md`)
  also quote keys — grep for the binding when changing one.
- Module docstrings in this repo carry the *why* (design rationale, rejected
  alternatives). Read the docstring before changing a module, and keep that
  standard when adding one.
