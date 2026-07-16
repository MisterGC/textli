# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **TeX math in documents** — pandoc-style `$…$` inline and `$$…$$` display
  math renders as typeset formulas in the reading view (STIX Two Math via
  ziamath — pure Python, no LaTeX install), sized and inked to blend with the
  Literata prose: inline math rides the text baseline, display math stands
  centered on its own line, and a formula can be commented or suggested on
  from the reading view like any other span — its image maps back to its
  `$…$` source, the mark renders over the formula, and it prints with the
  page. The write view tints math spans as you type. Delimiter
  rules are pandoc's and deliberately strict — prose dollars ("costs $5 and
  $10"), `\$` escapes, and `$` inside code never trigger math — and a formula
  that doesn't parse falls back to its raw TeX in a code chip, so a typo
  mid-edit never breaks the page. A cheatsheet of the supported constructs
  ships as `examples/math.md`.

- **Follow source references from the reading view** (#37) — notes about code
  cite it the way everyone writes it, in inline code: `textli/editor.py:2455`,
  `view.py:80-95`, or just `editor.py`. Those are now followable. `↵` opens the
  file **in place** as a read-only code page — monospace on the code band,
  syntax-highlighted, sized and widened for code rather than prose, with the
  referenced lines lifted out of the band onto the bright page — and `gb`/`⌫`
  walks back to exactly where you were reading. So a design doc can stay lean
  and still have its evidence one keystroke away, live, instead of pasted in
  and going stale. References resolve beside the document first, then up
  through its parent folders (a doc in `mgc/groundwork/` finds
  `textli/editor.py` without spelling out `../../`); a bare `editor.py` is
  looked up in the enclosing repository and, if two files share the name,
  whispers *not found* rather than guessing. The search never leaves that
  repository, and an unreadable folder reads as "not there" instead of
  failing. Prose chips are left alone — a reference needs a file extension or
  a line anchor, so `--read`, `.md` and `QWidget` stay unfollowable. A link to
  a text file opens as source too, while a link to something meant to be
  *seen* (`page.html`, an image) still goes to the system handler. Source
  pages are peeks, not buffers: no editing, no comments or suggestions
  (`c`/`s`/`⌘R` whisper), and they never enter the open history.

- **Paper surface** — the page is material now, not a flat hex: whisper-level
  procedural grain plus a horizontal light falloff (fully bright across the
  reading column, a few percent darker in warm ink toward the window edges)
  painted under the text of both views. Both cues sit below conscious notice —
  texture felt, not seen — so the zen direction stays intact while the page
  stops feeling clinically flat. `⌘⇧P` toggles the surface off for the flat
  page (persists).

### Fixed

- Rendering a large document is no longer slow: the read view's styling passes
  ran their format merges outside an edit block, so every one settled the whole
  document layout again — about 1 ms per merge on a 4,500-line file, against
  1.5 µs batched — and the code-block pass matched each syntax span against
  every line of its fence rather than just the lines the span covers. Both
  costs grew faster than the document, so they were invisible on ordinary
  prose and crippling on anything long: together they took 15 s to render a
  4,500-line file, now 0.37 s (and well under 0.1 s for an ordinary one).

## [0.3.0] - 2026-07-12

### Added

- **A reading face for the read view** — the rendered page is now set in
  **Literata** (a warm, book-oriented serif, bundled OFL), so long-form prose
  reads like a typeset page instead of the monospace source; fenced and inline
  code stay in JetBrains Mono, and the write view keeps its monospace column.
- **Reading rhythm in the read view** — rendered prose sits on generous
  line-height with clear space between paragraphs (code stays tight), scaling
  with the font zoom, so long-form reading breathes; pairs with the reading face.
- **Undo / redo in NORMAL mode** — `u` undoes and `⌃r` redoes the last change
  in the write view (and `InlineVimEditor`), riding the editor's native undo
  stack, so a NORMAL-mode edit is reversible without dropping to INSERT for
  `⌘Z`.
- **Vim counts, VISUAL operators and yank/paste in the write view** — a leading
  count repeats the next motion or edit (`3j`, `2dd`, `5w`, `4x`); `v` starts a
  VISUAL selection that the motions extend, with `d` / `y` / `c` to delete, yank
  or change it; and `yy` / `yw` yank, `p` / `P` paste, sharing one register with
  the delete commands (so `dd` then `p` moves a line). Text objects, dot-repeat,
  macros and named registers stay out — the write view keeps to vim essentials.
- **Headings overview (`gh`) in the write view** — the reading view's outline
  jump-list now works over the source too: `gh` parses the document's headings
  (skipping fenced code), `j`/`k` preview each live, `Enter` keeps the spot and
  `Esc` restores where you were — so a long draft navigates by structure in
  either view.
- **Find & replace** — from a `/` search in the write view, `⇥` reveals a
  replace field: `↵` replaces the current match and advances, `⌃↵` replaces
  every one (a single undo step). Replace targets the *literal* occurrences of
  the query (case-insensitive), not the fuzzy hit list — replacing a fuzzy
  match would be surprising. The reading view stays find-only, since its
  rendered page is read-only.

### Fixed

- Embedded editors now render comments in the bundled Caveat handwriting face:
  the public widgets (`ZenMarkdownEditor`, `InlineVimEditor`) register the
  bundled fonts on construction (idempotently), so a host like grafli no longer
  falls back to the plain body font the way only the standalone CLI avoided.

## [0.2.0] - 2026-07-10

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
- **Live reload of external edits** — textli watches the open file and
  reflects changes made outside it (an agent applying your comments, a `git`
  checkout, another app) in place, keeping the view, caret and scroll, with a
  faint *reloaded* whisper — no restart to see them. Its own autosaves are
  never mistaken for external writes. If the buffer has unsaved local edits
  when the file changes underneath, it warns and keeps them (they win on the
  next save) instead of clobbering; two-sided conflict reconciliation is
  tracked separately.
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
- **Focus reading mode** (`f`) — an immersive read: the caret line locks to
  the centre and the page scrolls under it (typewriter-style, pinning at the
  document ends), while a spotlight centred on the reading line fades text
  by distance — brightness slides smoothly as you scroll instead of snapping
  at paragraph edges. Persists across sessions and supersedes `⌘.` while on.
- **Whisper breadcrumb while reading** — the read-view status leads with
  the section under the caret (`§ Architecture · 42% · ~7 min left`), so a
  long document always tells you where you are; empty before the first
  heading, and it follows the caret. When the caret is on a link it turns
  into `→ where Enter goes` (filename, host, or `#slug`).
- **Table styling in the read view** — Markdown tables get a bold header
  row in the code-band paper shade, thin warm gridlines, and cell padding;
  real table formatting, so it prints too.
- **Visible read-view caret** — a soft zen-blue block over the current
  glyph (vim-style) replaces Qt's near-invisible 1px line, so it's easy to
  see where you are when placing a comment; the letter still shows through.
- **Comments read like margin notes** — the inline comment editor wears the
  same tint a commented span gets in the text, set in a handwriting face
  (bundled Caveat, OFL) in dark red ink and sized to sit with the document.
  It starts small and grows with what you write — wrapping to a fixed width,
  scrolling once it reaches a max height — so a remark feels like annotating
  rather than filling a form field.
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
