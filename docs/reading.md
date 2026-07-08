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
- ++enter++ with the caret on a link **follows it**: web and mail targets
  open in your default browser, `#heading` targets jump within the
  document. Links are set in the zen link blue so they read as links
  without shouting; clicking works too.
- `go` — open another file without leaving the reading view (see
  [Opening files](opening.md)).

## The whisper status

The faint line in the card's corner tracks the read: how far through the
document you are, roughly how many reading minutes remain, and what still
awaits review (`42% · ~7 min left · 3 changes · 2 comments`). The review
counts disappear as you resolve them — an empty whisper is a finished
review.

## Code blocks

Fenced code sits on a full-width band in a deeper paper shade, so the code
part of a document is visible at a glance. A language tag on the fence
(` ```python `) adds calm syntax highlighting drawn from the zen palette —
keywords in the title blue, strings in the warm red, comments in gray
italic, numbers and constants in amber; everything else stays body ink. No
tag means no colors: the band alone marks the block.

## Comments

Select a span with `v` + motions, then:

- `c` — comment the selection (or, with the caret on an existing commented
  span, reveal and edit that comment).
- `]c` / `[c` — step to the next / previous comment.
- ++enter++ — reveal-edit the active comment; `⇧D` deletes it.

Commented spans get a soft highlighter wash in the rendered text, so review
feedback is visible without shouting.

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
