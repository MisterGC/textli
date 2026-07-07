# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **`go` open-file dialog** — switch files without leaving the editor, from
  either view: opening history is fuzzy-matched over full paths, the
  filesystem completes shell-style one segment at a time; `Tab` completes,
  folders descend. Works in the reading view too (and stays there).
- **`/` in-document search** — a live, ranked hit list (exact phrases above
  word matches; fuzzy matches never cross a word boundary), preview-as-you-
  select, `Enter` jumps, `Esc` restores, `n`/`N` step through highlighted
  hits in both views.
- **Overview live preview** — `gh`/`gc` open on the current section and
  preview rows as `j`/`k` move; `Enter` keeps the spot, `Esc` returns
  exactly where you were.
- **Whisper status line** — one faint line in the card's corner: vim mode,
  word count and session delta while writing; progress, minutes left and
  open review items while reading. Hidden while any overlay card is up.
- **Position memory** — every file resumes where you left it: view mode,
  caret and read-view scroll (`-r` and `#heading-slug` still win).
- **Typewriter scrolling** (`⌘T`) — the caret line holds steady while the
  page moves; persists across sessions.
- **Follow links with `Enter`** — in either view, the caret on
  `[text](url)`, an `<autolink>` or a bare URL follows it: web and mail
  targets open in the default browser, `#heading-slug` targets jump within
  the document. Rendered links wear the zen link blue instead of Qt's
  palette default.

### Fixed

- Reading view no longer cuts off or refuses to scroll after comments or
  suggestions re-render the document (Qt's incremental layout corrupted by
  post-`setMarkdown` edits; now settled with a forced full relayout).
- Commenting a whole fenced code block no longer breaks rendering from that
  point on.
- A bare HTML-looking token in the source (e.g. `<variant>` outside code
  spans) no longer silently swallows every following paragraph in the read
  view — raw HTML now renders as the literal text that was typed.

## [0.1.0] - 2026-07-01

### Added

- **Initial extraction from grafli.** The zen Markdown editor that grew inside
  [grafli](https://github.com/MisterGC/grafli) becomes its own package:
  - Full-window, distraction-free writing surface with vim keybindings
    (NORMAL/INSERT/VISUAL), section focus (`⌘.`), word-jump overlay (`⌘J`),
    adjustable font size and content-column width (both persisted).
  - Rendered reading view (`⌘R`) with vim caret navigation, headings
    overview (`gh`), and print (`⌘P`).
  - Inline review: CriticMarkup comments (`c`, `]c`/`[c`) and track-changes
    suggestions (`s`, `a`/`x` accept/reject, `⇧A`/`⇧X` all, `gc` changes
    overview, `p` clean preview) — stored inline in the Markdown, no sidecar.
  - `textli` CLI: open any Markdown file, `#heading-slug` locations, `-r` to
    start in the reading view; autosave while editing.
  - Embeddable widgets: `ZenMarkdownEditor` (full-window) and
    `InlineVimEditor` (single-field vim editing) for PySide6 hosts.
  - Self-contained F1 help owned by the editor.
