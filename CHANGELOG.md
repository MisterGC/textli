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
- **Code blocks stand out in the read view** — fenced code sits on a
  full-width band in a deeper paper shade, with em-scaled breathing room
  around the code; a language tag brings calm zen-palette syntax
  highlighting (via Pygments, now a dependency): keywords blue, strings
  warm red, comments gray italic, numbers amber.
- **Heading rhythm in the read view** — clearly more air above a heading
  (closing the previous section) than below it, per level and scaled with
  the font zoom; `h1`/`h2` carry a thin GitHub-style rule.
- **Inline-code chips & blockquote voice** — inline code in prose wears a
  soft wash chip; blockquotes get hint-gray ink and a thin left bar.
- **Section focus while reading** — `⌘.` now also works in the read view:
  everything outside the section under the caret rests behind a
  translucent paper wash, following the caret; comments and search stay
  intact beneath it.
- **Whisper breadcrumb while reading** — the read-view status leads with
  the section under the caret (`§ Architecture · 42% · ~7 min left`), so a
  long document always tells you where you are; empty before the first
  heading, and it follows the caret. When the caret is on a link it turns
  into `→ where Enter goes` (filename, host, or `#slug`).
- **Table styling in the read view** — Markdown tables get a bold header
  row in the code-band paper shade, thin warm gridlines, and cell padding;
  real table formatting, so it prints too.
- **Follow links to files** — in the reading view `Enter` on a link is
  routed by target: a `.md` opens in place (with `other.md#section` landing
  on the heading), a `.grafli` shows a "not yet supported, stay tuned"
  notice, and anything else opens with the system handler. `gb` (or
  `Backspace`) walks back through the documents you followed, and a brief
  toast names where you land. `gl` opens a links overview — the same
  jump-list as `gh`/`gc` — whose `Enter` follows the picked link. A link to
  a missing file whispers *not found* instead of creating one.

### Fixed

- Reading view no longer cuts off or refuses to scroll after comments or
  suggestions re-render the document (Qt's incremental layout corrupted by
  post-`setMarkdown` edits; now settled with a forced full relayout).
- Commenting a whole fenced code block no longer breaks rendering from that
  point on.
- A bare HTML-looking token in the source (e.g. `<variant>` outside code
  spans) no longer silently swallows every following paragraph in the read
  view — raw HTML now renders as the literal text that was typed.
- Font zoom (`⌘+`/`⌘-`/`⌘0`) now works in the reading view too; a size
  change re-renders the document and keeps the caret in place.
- Print (`⌘P`) in the reading view now prints the typeset page instead of
  the raw CriticMarkup source, with the code band baked in as a real
  background so fenced code stands out on paper.
- Relative image links (`![](diagram.png)`) now render in the reading view
  no matter where textli was launched from — resources resolve against the
  document's own folder, not the process working directory.

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
