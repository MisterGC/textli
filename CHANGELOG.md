# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **`.` repeats the last change** (#71) — NORMAL mode now has vim's repeat
  command. A change is anything that moved the document: an operator and its
  motion or text object (`dw`, `d}`, `ciw`, `daw`), a shorthand (`x`, `r`, `~`,
  `J`, `p`), or a whole insert session, so `cwword<Esc>` and `A!<Esc>` repeat
  with the text they typed. `3.` applies the repeat three times. Motions and
  undo never become the thing repeated — after `xu`, `.` deletes again rather
  than undoing again.

  The repeat replays the change's keystrokes, and the insert leg replays
  through the widget's own key handling, so Backspace and Delete inside it
  count: `iab<BS>c<Esc>` puts in `ac` on the repeat, not `abc`.

- **The reading view shows a document's frontmatter status, and `gs` changes
  it** (#69) — Qt keeps YAML frontmatter off the rendered page, so a
  document's `status:` was invisible while reading and could only be changed
  by flipping to the write view and typing a value from memory. The whisper
  now ends with `status: draft` for a document that carries one, and `gs`
  opens a card listing the values in the order the document declares them,
  on the one it currently has: `j`/`k` move, a digit picks directly, `Enter`
  writes `status:` and saves the file, `Esc` leaves it alone.

  A document opts in by listing its own legal values, so textli never invents
  a vocabulary for someone else's workflow:

  ```yaml
  ---
  status: draft
  statuses: draft, review, final
  ---
  ```

  Inline, flow (`[draft, review]`) and block-list forms all read. A document
  without a `statuses:` line is untouched — nothing new in the whisper, and
  `gs` says there is nothing to change. Only the `status:` line is rewritten
  (added above `statuses:` when the document has none yet); the rest of the
  frontmatter is left byte for byte, and the edit is one step on the write
  view's undo stack. `gs` is a reading-view gesture: in the write view the
  frontmatter is on screen already.

### Changed

- **PySide6 floor raised to 6.8** — Qt 6.8 is where the Markdown reader parks
  frontmatter in the document's metadata instead of rendering it as prose,
  which is what makes the status readable rather than a block of raw text at
  the top of the page.

## [0.8.0] - 2026-08-15

### Added

- **`↵` on an image in the reading view fills the window with it** (#59) — a
  picture is drawn at the prose column's width, which is right for reading
  around it and too small for reading *into* it; a dense `.grafli` diagram or
  a chart with a dozen labels couldn't be inspected without leaving textli.
  `Esc` (or `↵` again) puts the page back with caret and scroll untouched. It
  works for every kind of image the page can hold — ordinary Markdown images,
  charts, `.grafli` diagrams and rendered math — and `↵` keeps its existing
  jobs, so a link or source reference under the caret still wins.

  It covers the window rather than the card deliberately: charts and diagrams
  are rasterised at the *column* width and the card is only ~130px wider, so
  expanding into the card alone would have enlarged a diagram by about a
  tenth. Only ordinary Markdown images have a full-size original to enlarge
  from; the rendered kinds are scaled up from their bitmap, and that scaling
  is capped at 4x so a small formula becomes readable rather than a smear.
  Re-rendering those at the expanded size is left for later.

- **The sheet now lies on a desk** (#56) — the surround was a flat fill, which
  is most of what you look at and read as a void rather than a room. It wears
  the same two cues `paper.py` already gives the page, grain and a horizontal
  light falloff, lit from the same place: the desk's light frame is centred on
  the card but spans the window, so one ramp runs bright at the sheet and sinks
  into the corners instead of each surface having its own light. It rides the
  existing `⌘⇧P`, and where a host supplies a canvas the desk stops at its edge
  — that canvas keeps its own pixels under the gentler wash, so an embedded
  textli never paints over its host. Two things a dark ground forces and the
  sheet's own numbers could not carry: the desk's grain is a *translucent*
  overlay rather than a colour-baked tile, since an embedding host paints the
  ground and the desk cannot bake a colour it does not know (which also means
  its tiles can never go stale against a palette switch), and its falloff
  shades toward black rather than the warm body ink the sheet uses — body ink
  is *lighter* than the dimmed surround, so reusing it brightened the corners
  it was meant to sink.

### Changed

- **An image travels into and out of the full-window view instead of cutting**
  (#64) — `↵` grew the page into the expanded picture in a single frame, and
  `Esc` cut back the same way, which left the reader re-finding their place
  because nothing connected the small picture to the large one. It now grows
  out of where it sits on the page, with the backdrop fading in behind it, and
  goes back the same way; the eye follows one object rather than reconciling
  two. Same durations and curves as the editor's own fade in and out, so
  there is one motion vocabulary rather than a second. Reversing mid-flight
  picks up from wherever the picture currently is, so a quick `↵ Esc` doesn't
  snap, and keys stay swallowed for the whole of the closing tween — it is
  still on screen, so nothing should land on the document underneath.

- **A display formula is set on the left, indented, rather than centred**
  (#65) —
  it still reads as lifted out of the sentence rather than starting one, and
  it lines up with the prose the way the rest of the page does. Two body ems
  of indent, resolved through the view's font metrics so it holds at any zoom
  and on any platform. An inline `$…$` is untouched — it stays where it sits
  in its sentence. Charts and `.grafli` diagrams keep the centring they had.

- **A picture is now drawn at most three quarters of the prose column** (#62)
  — filling the measure also means being as tall as the aspect ratio makes
  it, which is a lot of page for something the reader is mostly reading
  *around*: a 4:3 image in a 692px column took 519px of height and now takes
  389px. No detail is lost, since `↵` fills the window with the original
  (#59). Charts and `.grafli` diagrams are *rasterised* at the capped width
  rather than rendered to the full column and drawn scaled down, so they stay
  crisp; the cost is slightly less room for a chart's labels. Still downscale
  only — a picture already narrower than the cap keeps its own size.

  A width cap rather than a height one on purpose. A height cap would target
  the wasted space more directly but would depend on the window, so the same
  document would lay out differently on a laptop and a monitor; the sheet's
  geometry is meant to hold still. Alignment is unchanged: plain images stay
  left with the prose, while display formulas, charts and diagrams keep the
  centring they already had.

- **`textli notes.md` now opens the reading view** (#58) — reading a document
  is the common case and writing one the exception, so reaching the page no
  longer costs a `⌘R` every time. `textli -w notes.md` (`--write`) opens the
  write view instead; `-r`/`--read` keeps working and now names the default,
  so an existing alias or script doesn't break, and asking for both at once is
  a usage error rather than one silently winning. Only the standalone CLI
  changes — `ZenMarkdownEditor(start_in_read=…)` keeps its meaning, and nothing
  an embedding host passes today behaves differently.

  Resuming a file's view had to become symmetric to survive the flip. The
  restore only ever toggled *into* the read view: a file left writing came
  back writing because writing was what the app opened in, not because
  anything carried it there. With reading the default, that half of "resumes
  where you left it" would have quietly stopped holding, so the restore now
  carries a file back in both directions. Reading is the default for a file
  with no remembered view; `-r` or `-w` overrides whatever is remembered.

### Fixed

- **`Esc` quit the standalone app outright** (#63) — it autosaved and closed,
  so one reflexive keypress ended the session and cost the reader their window
  and their place. Nothing was ever lost from the file, but nothing about
  reading a document suggests that key should end the program. `Esc` standalone
  now only steps back: leave visual mode, close an overlay, cancel the headings
  overview, put an expanded image away. With nothing left to back out of it
  flashes how to quit and does nothing else. An embedding host is untouched —
  there the editor is modal and `Esc` is how it hands back, which is what the
  new flag defaults to, and `⇧Esc` still means cancel-and-discard.

  `⌘Q` (`Ctrl+Q` elsewhere) now quits, because `Esc` was the only keyboard exit
  there was: macOS hands Qt applications a `⌘Q` through the default application
  menu, but on Linux and Windows the window's close button would otherwise have
  been the only way out.

- **The caret and the selection flattened an image instead of marking it**
  (#61) — a wash reads well over text, where it tints the paper between the
  letters, but over a picture it covers the content and dulls the thing you
  are trying to look at. Measured against a `#cc4422` test image, the caret
  took it to `#92443a` and a selection to `#c28c85`. Two mechanisms were
  doing it: textli's own block caret fills the glyph cell under it, and an
  image *is* one glyph, so the cell was the entire picture; and Qt paints the
  selection inside the document layout with no hook to exempt an image. An
  image under the caret or inside the selection is now redrawn from its own
  resource over whatever wash landed on it, and marked with four 4px corner
  brackets in the caret's colour at full strength (the wash's alpha is low
  because it covers a whole cell, and at that alpha a thin stroke barely
  registers) or the selection colour. Text is untouched.

  The brackets sit *inside* the picture rather than around it, their outer
  face flush with its edge. An outline hung on the outside has to line up with
  the drawn edge exactly — and it didn't, because the laid-out rectangle
  needed the block's left margin added back and was taking the line's descent
  as part of the image's height — so it read as broken. Both are fixed, and
  drawing inside means nothing claims layout room the image never reserved;
  the cost is a few pixels of content at each corner.

  A **rendered formula keeps the wash**. It is typeset text that happens to
  arrive as a bitmap: it sits in a sentence, it is small, and a tint reads
  over it exactly as it reads over the letters around it. Charts and `.grafli`
  diagrams go the other way and get the brackets — they are pictures with
  detail to inspect, and a wash flattens them the same way it flattens a
  screenshot.

- **An image wider than the prose column broke the page sideways instead of
  scaling down** (#60) — Qt draws an image at its natural pixel size, so a
  2400px screenshot in a 700px column pushed the document's ideal width to
  2408px and grew a horizontal scrollbar. Charts, `.grafli` diagrams and math
  never did this, since they're rasterised at the column width and carry an
  explicit size; a plain `![](shot.png)` carried none. Wide images are now
  scaled down to the column with their aspect ratio kept, and the document
  resource is left at full resolution so `↵` (#59) still enlarges the
  original. Downscale only — an icon keeps its own size rather than being
  stretched to fill the measure. This also fixes `@2x` assets, which rendered
  at twice their intended size because Qt reads natural pixel size as logical
  size.

  The real damage was second-order: authors and agents worked around the
  overflow by shipping pre-shrunk files, and once `↵` could expand an image
  that downscaled copy was all the detail there was. The bundled AI skill now
  says to ship images at full resolution and why.

- **Nothing re-rendered when the reading column changed** (#60) — a width
  step or
  the full-width toggle resized the card, but charts and diagrams kept the
  bitmap they were rasterised at, so widening the column left them small and
  soft. The read view now re-renders when the column moves, coalesced so a
  burst of width steps settles into one render, and carries the reader's
  position across as a fraction of the document rather than a pixel offset —
  a narrower column makes the same document taller. The threshold that
  triggers it sits above the scrollbar's width on purpose: fitting an image
  changes the document's height, which can bring the scrollbar in or out,
  which moves the column again, and chasing it exactly never settles.

- **Read-view prose sat too far apart to cohere, and list items had no
  grouping gap** (#54) — the reading leading was set with Qt's
  `ProportionalHeight`, which is a percentage of the font's *natural line
  box* rather than of the em. Against Literata's 1.485em box the configured
  145% rendered at roughly 2.2em, well past the point where consecutive
  lines still read as one block: the eye lost the line on the return sweep
  and paragraphs came apart into evenly-spaced stripes. It also scaled each
  line by the tallest fragment on it, so a line carrying inline code was led
  differently than a plain one and the leading wobbled inside a single
  paragraph. Leading is now an absolute line box of 1.55em, resolved through
  the view's own font metrics so it means the same thing at every zoom and
  on every platform — the old gaps multiplied the point size as though a
  point were a pixel, which holds only at 72 dpi. List items now get an
  explicit gap of their own, smaller than a paragraph's, so the three breaks
  finally rank: line, then item, then paragraph. Headings and any block
  holding an image keep their natural height, which a fixed box would crop.
  That exemption also stopped the leading inflating an image's own line: a
  picture *is* the line's tallest fragment, so 145% of it left 45% of the
  image's height as blank space underneath — a measured 78px gap below a
  173px picture, before the paragraph gap.

- **CriticMarkup marks were dropped after an inline code span that wrapped
  across lines** (#52) — CommonMark lets a code span cross a line, and
  hard-wrapped prose wraps long spans routinely, but the inline-code pattern
  refused newlines. The closing backtick of a wrapped span was then left over
  as an *opener*: it paired with the next backtick anywhere later in the
  document and everything between was masked as code, so any `{++`, `{--`,
  `{~~` or `{==` in that stretch was read as documentation and silently
  skipped. The mark fell through to GFM strikethrough, which made the
  *document* look broken rather than the parser. Spans may now cross lines but
  stop at a blank one, so a genuinely unpaired backtick still can't swallow
  the rest of the file.

## [0.7.1] - 2026-07-29

### Fixed

- **The paper sheet kept the previous palette when the theme switched with no
  editor open** (#49) — the grain tile bakes the page colour into its colour
  table, but the cache was keyed by device-pixel-ratio alone, from back when
  that colour was a constant. A host switching palettes between editors (start
  dark, close the note, go light, reopen) got the old theme's grain under the
  new theme's ink. The cache is now keyed by page colour too, so a tile can
  never outlive its palette — and both palettes stay cached, so switching back
  and forth reuses tiles instead of rebuilding them.

## [0.7.0] - 2026-07-27

### Added

- **PDF export from the CLI** (#47) — `textli notes.md --pdf` writes
  `notes.pdf` beside the source and exits without opening a window, so a
  draft becomes a shareable paper from a script or a Makefile; an explicit
  path (`--pdf out/paper.pdf`) wins over the default. What lands on the page
  is the reading view's typeset page — the same document `⌘P` prints, code
  band baked in — so charts, `.grafli` diagrams, math, tables and the
  annotation layer all come along as what they already are. Page size follows
  the system default, matching what the print dialog would have produced.
  `ZenMarkdownEditor.export_pdf(path)` is the same thing for embedders, and
  it leaves the reader in whichever view they were in.

### Fixed

- **Printing on the dark theme baked a dark code band into the page** (#46) —
  body ink comes from the view's stylesheet, which a printed document never
  carries, so on the dark palette a page came out as black prose on white
  with a near-black `#272421` fence behind light-blue keywords. Printing and
  PDF export now always render on the light palette and restore the screen
  afterwards, scroll position included — paper isn't themed. A regression
  from #44, which is where the second palette first reached the print path.

- **Long code lines lost their tail on paper** — Qt's Markdown import marks
  fences non-breakable, which the wide reading column hides; on a page the
  overflow was *cut off* rather than wrapped, silently dropping the end of
  any line that didn't fit. Fences now wrap when printed.

## [0.6.0] - 2026-07-26

### Added

- **Dark theme, as the counterpart to the warm palette** (#44) — a second
  palette in the same warm hue family: a low-key ground (`#1E1C19`, shared
  with [grafli](https://github.com/MisterGC/grafli) so an embedded editor
  sits on its host's board instead of glowing against it) carrying the light
  theme's paper colour as its ink. `⌘⇧D` switches and persists it. Two
  counterpart palettes, not a theme engine: no third theme, no settings
  surface.

  Colours moved out of `constants.py` into a new `textli/theme.py` — a frozen
  `Palette` with `LIGHT`/`DARK` counterparts whose module globals are rebound
  on switch, so every consumer reads the active value with no re-import.
  Dark values are *derived* from the light theme's measured relationships
  rather than carried across the inversion: roles readable by luminance
  reproduce their contrast ratio against the ground they are actually drawn
  on (syntax tokens against the code band, not the page), while roles
  readable by hue — the amber number token measures only 1.74:1 on the light
  band — keep their hue and clear a readability floor instead. Anything drawn
  on a fill takes its ink from that fill through a single `ink_on()`, so a
  pinned light ink can't survive the ground changing under it. Tests assert
  those rules rather than the colours, including a guard that fails if any
  module re-freezes the palette with a `from theme import …`.

  Along the way the scrollbar stopped being the platform's near-white column
  — invisible on paper, the brightest thing on the page once the ground goes
  dark — and became a thin muted handle on a transparent track in both
  palettes.

- **Theme API for embedding hosts** (#44) — `textli.set_theme("dark")`,
  `toggle_theme()` and `is_dark()` on the package root, plus a
  `textli.theme_changed` signal. Open `ZenMarkdownEditor` and
  `InlineVimEditor` instances listen to it and restyle themselves in place —
  re-running their stylesheets, syntax highlighting and the read view's
  render (math and chart images bake their ink) — so a host only makes the
  one call. `ZenMarkdownEditor(..., theme_name="dark")` opens straight onto
  the dark ground for a host that is already dark, and `apply_theme()` is
  there for hosts that change colours without going through `set_theme`.
  Theme persistence belongs to the standalone app alone, so it can never
  override a host's choice.

## [0.5.0] - 2026-07-23

### Added

- **`.grafli` diagrams in the reading view** (#42) — a Markdown image reference
  to a `.grafli` file (`![](architecture.grafli)`, resolved against the
  document's folder like any relative image) renders inline as the diagram
  [grafli](https://github.com/MisterGC/grafli) draws. textli shells out to
  grafli's `render` CLI — the one stable contract between the tools, no import
  and no Python coupling — and shows the produced image, rendered at the reading
  column's width and the display's pixel ratio so it stays crisp. Renders are
  cached by source path, mtime and target metrics, so re-renders (zoom, view
  toggles, file-watch reloads) don't re-invoke the CLI unless the diagram or the
  metrics actually changed. It degrades quietly: without grafli on `PATH`, or on
  a failed or timed-out render, the reference falls back to ordinary
  image-reference behavior — no error, no page break. Image refs only; a plain
  `[link](d.grafli)` keeps its stay-tuned notice.

- **Charts in the reading view** (#41) — a `<!-- chart: … -->` marker on the
  line above a pipe table renders it as a typeset chart instead of a grid, the
  way `$…$` renders as a formula: the chart replaces the table on the page, the
  table stays one `⌘R` away in the write view. Two types — `bar` (grouped bars,
  one per series column) and `line` (a polyline per series column) — drawn with
  a hand-rolled painter in the page's own palette and Literata labels, no chart
  library and no new dependency. The marker takes three keys at most: `type`,
  `x=<column>` (the x-axis labels, default the first column), and `y=<col,col>`
  (a subset of series columns, default all but the x one); series names come
  from the headers and a header's trailing unit (`speed [m/s]`) lifts to the
  y-axis. A bare `table` flag keeps the data on the page — chart first, table
  under it — for when the reader needs the exact values and not just the
  shape. Because the marker is a plain HTML comment the source stays portable
  pandoc Markdown — GitHub renders the table, pandoc converts it, the comment
  vanishes. Anything malformed — unknown type, an `x=`/`y=` that names no
  column, a non-numeric cell, a marker with no table — falls back to the plain
  table and the marker stays invisible, so a chart never breaks the page. A
  chart reviews like a formula: caret on it, `c` comments or `s` suggests, and
  the annotation lands on the whole table source; it prints with the page. See
  `examples/charts.md`.

- **Installable AI skill** (#39) — `textli skill install` puts a bundled agent
  skill into your AI tools' skill directories (`claude`, `codex`, `opencode`,
  or `all`), teaching them to author Markdown for the reading view (headings
  as navigation, pandoc math, followable `path:line` source references) and to
  collaborate through the annotation layer: the human's `{>>comments<<}` come
  back as track-change suggestions, never silent rewrites, with a convergence
  protocol for when to leave the doc and ask directly. Genre playbooks ship as
  on-demand references — decision doc, learning doc, and a scientific paper
  guide with a worked example, `examples/paper.md`, whose object of research
  is textli itself. `textli skill check` reports per-tool status (`ok` /
  `stale` / `modified` / `missing`) against the version stamped at install
  time, `textli skill uninstall` removes, and bare `textli skill` prints the
  whole skill to stdout for tools without a skill directory.

## [0.4.0] - 2026-07-17

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
