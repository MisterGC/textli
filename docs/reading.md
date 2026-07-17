# Reading & review

`⌘R` renders the Markdown into a typeset reading view. It's not a static
preview: a caret moves through the rendered text with vim motions, and the
whole review workflow — comments and suggested changes — lives here.
`⌘R` again returns to the source, caret kept in place.

Leave a file while reading and it remembers: reopening it resumes the
reading view at the very spot you left, so a long review survives any
number of sessions.

## Navigating

- `h j k l`, `w / b / e`, `0 / $` — move the caret through the prose.
- `gg / G` — document start / end; `⌃d / ⌃u`, `⌃f / ⌃b`, ++space++ —
  half-page and full-page scrolling.
- `gh` — **headings overview**: an outline jump-list of the document,
  opened on the section you're in. `j`/`k` move the selection *and preview
  it live* — the view follows; ++enter++ stays at the previewed spot, a
  digit jumps directly, ++esc++ returns you exactly where you were.
- `/` — **search** with a live fuzzy hit list (same as the
  [write view](writing.md)); `n` / `N` step through the hits.
- ++enter++ with the caret on a link **follows it**, routed by target: a
  `.md` file opens in place (so a folder of linked notes reads like a small
  wiki, and `other.md#section` lands on that heading), web and mail open in
  your default browser, `#heading` jumps within the document, and anything
  else (`.html`, images, PDFs…) opens with the system handler. A `.grafli`
  link says it's not supported yet; a link to a missing file whispers
  *not found* rather than creating one. Links are set in the zen link blue
  so they read as links without shouting; clicking works too.
- ++enter++ on a `` `path:line` `` reference in inline code opens that
  **source file** read-only at that line — see
  [Source references](#source-references).
- `gb` or ++backspace++ — **back** to the document (or source file) you
  followed the last link or reference from, exactly where you left it.
- `gl` — **links overview**: the same jump-list popup as `gh`, listing every
  link with where it points; `j`/`k` preview, ++enter++ follows the
  selection.
- `go` — open another file without leaving the reading view (see
  [Opening files](opening.md)).

## The whisper status

The faint line in the card's corner tracks the read: the section you're in,
how far through the document you are, roughly how many reading minutes
remain, and what still awaits review
(`§ Architecture · 42% · ~7 min left · 3 changes · 2 comments`). The
section breadcrumb follows the caret — so a long document always tells you
where you are without opening the headings overview — and is absent before
the first heading. When the caret is on a link the breadcrumb turns into
`→ where ++enter++ goes` (a filename, host, or `#slug`), so you see the
destination before committing. The review counts disappear as you resolve
them: an empty whisper is a finished review.

## Typography

The rendered page is set in **Literata**, a warm serif made for long-form
reading, so the read view reads like a typeset page rather than the monospace
source — while fenced and inline code keep the monospace face. (The write view
stays in its monospace column.) Prose sits on generous leading with clear space
between paragraphs, tuned for sustained reading and scaling with the font zoom;
code stays tight.

Headings breathe asymmetrically — more space above (closing the previous
section) than below (starting their own) — and `h1`/`h2` carry a thin
rule, GitHub-style, so section breaks are visible from across the room.
Inline code wears a soft chip wash so `identifiers` pop while scanning,
and blockquotes get hint-gray ink with a thin bar at the left — a
different voice for somebody else's words.

Tables get the paper palette too: a bold header row in the code-band shade,
thin warm gridlines, and cell padding for air — real table formatting, so
it prints with the rest of the page.

The caret is a soft blue block over the current glyph — vim-style, easy to
find on the warm page when you're placing a comment, without pulling the
eye the way a hard cursor would.

`⌘.` turns on **section focus**: everything outside the section under the
caret rests behind a translucent paper wash and follows the caret as you
move — the rendered twin of the write view's paragraph focus.

`f` turns on **focus reading mode** — a deeper, immersive read. The caret
line holds at the centre of the view and the page scrolls under it
(typewriter-style; at the very start or end of the document the caret
travels to the top/bottom instead), while a **spotlight** centred on the
reading line fades the text away by distance. Because the fade keys off the
caret's position rather than paragraph edges, brightness slides smoothly as
you scroll — a heading or a short line never makes it jump. It persists
across sessions and supersedes `⌘.` while it's on (only one focus at a
time). Comments, marks and search stay live beneath the wash.

## Code blocks

Fenced code sits on a full-width band in a deeper paper shade, so the code
part of a document is visible at a glance. A language tag on the fence
(` ```python `) adds calm syntax highlighting drawn from the zen palette —
keywords in the title blue, strings in the warm red, comments in gray
italic, numbers and constants in amber; everything else stays body ink. No
tag means no colors: the band alone marks the block.

Printing (`⌘P`) from the reading view prints the typeset page, not the raw
source, and carries the code band onto paper. Images referenced by a
relative path (`![](diagram.png)`) render against the document's own
folder, so they show wherever you launched textli from.

## Mathematics

Write math the way pandoc reads it — `$E = mc^2$` inline, `$$…$$` for a
display formula — and the reading view sets it as real typeset
mathematics: STIX Two Math glyphs in the page's ink, sized to the prose,
inline math riding the text baseline, display math centered on its own
line. Because the source is plain pandoc math, the same file converts to
LaTeX or PDF untouched when a draft grows into a paper. In the write view,
math spans are tinted so a formula reads as a formula while you type it.

The delimiter rules are pandoc's, deliberately strict so prose never turns
into math by accident: the opening `$` must hug a non-space, the closing
`$` must not be followed by a digit — so "costs $5 and $10" stays prose —
`\$` escapes a literal dollar, and a `$` inside inline code or a fenced
block is always code. Rendering covers the TeX math subset (fractions,
integrals, sums, roots, matrices, Greek — no custom macros); a formula
that doesn't parse falls back to its raw TeX in a code chip, so a typo
mid-edit never breaks the page. See
[`examples/math.md`](https://github.com/MisterGC/textli/blob/main/examples/math.md)
for a tour.

A formula reviews like any other span: select it and `c` comments it, `s`
suggests a replacement — or just put the caret on it and press `c`. The
mark renders over the formula itself, and the annotation lands on the
`$…$` source, so what you're reviewing is the maths, not a picture of it.

## Source references

Notes *about code* cite it the way everyone writes it, in inline code:
`` `textli/editor.py:2455` ``, `` `view.py:80-95` ``, or just
`` `editor.py` ``. In the reading view those are followable — ++enter++ on
one opens the file **in place**, read-only, at that line, and `gb` (or
++backspace++) brings you back exactly where you were. A design doc can
stay lean and still have its evidence one keystroke away, live rather than
pasted in and going stale.

The page you land on is unmistakably code: monospace on the code band,
syntax-highlighted, sized and widened for code instead of prose, with the
referenced lines lifted out of the band onto the bright page. `⌘+`/`⌘-`
zoom it, `/` searches it, vim motions move through it — it simply isn't
editable. `c`, `s` and `⌘R` whisper instead of acting: textli annotates
Markdown documents, and a file you're peeking at isn't one. A source page
is transient, too — it never enters your opening history.

Where it looks:

- **Beside the document first**, then up through its parent folders — so a
  doc in `mgc/groundwork/` finds `textli/editor.py` without spelling out
  `../../`.
- **A bare name** (`editor.py` — the way prose actually names a module) is
  then looked up in the enclosing repository. If two files share the name,
  textli whispers *not found* rather than guessing.
- **Never past that repository** (or your home folder). An unreadable
  folder reads as "not there" instead of failing.

A reference needs a file extension or a line anchor, so prose chips like
`--read`, `.md` or `QWidget` are left alone. Links work too:
`[the module](../textli/editor.py)` opens as source, while a link to
something meant to be *seen* — `page.html`, an image, a PDF — still goes to
the system handler.

## Comments

Select a span with `v` + motions, then:

- `c` — comment the selection (or, with the caret on an existing commented
  span, reveal and edit that comment). With the caret on a bare
  [formula](#mathematics), `c` comments that formula — the image is one
  character, tedious to visual-select.
- `]c` / `[c` — step to the next / previous comment.
- ++enter++ — reveal-edit the active comment; `⇧D` deletes it.

Commented spans get a soft highlighter wash in the rendered text, so review
feedback is visible without shouting. The comment editor opens as a small
note tinted like the mark it leaves, in a handwriting face and dark red ink;
it grows as you write — wrapping to width, scrolling once it's tall enough —
so leaving a remark feels like annotating the margin rather than filling in
a form.

## Suggestions (track changes)

- `s` — suggest a change: with a selection, propose replacement text
  (leave it empty to propose deletion); without one, propose an insertion
  at the caret.
- `]s` / `[s` — step to the next / previous suggestion.
- `a` / `x` — accept / reject the suggestion under the caret and advance
  to the next open one.
- `⇧A` / `⇧X` — accept / reject **all** suggestions at once.
- `gc` — **changes overview**: a jump-list of every suggestion and comment,
  with the same live preview as `gh` (`j`/`k` follow, ++enter++ keeps,
  ++esc++ restores).
- `p` — **clean preview**: read the prose as if every suggestion were
  accepted; the source stays untouched until you actually accept.

Removed text is struck through, added text is set in a calm red — accepting
or rejecting animates the change into (or out of) the document, and every
resolution is undoable in the source.

## The format: CriticMarkup

Everything above is plain text in your file, using
[CriticMarkup](http://criticmarkup.com/):

```text
{==span==}{>>a comment on it<<}
{++added text++}
{--removed text--}
{~~old~>new~~}
```

Because the marks live inline, review round-trips need nothing but the
Markdown file itself: hand it to a colleague, an AI agent, or a git branch,
and the annotations arrive with it.
