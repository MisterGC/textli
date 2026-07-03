# Reading & review

`⌘R` renders the Markdown into a typeset reading view. It's not a static
preview: a caret moves through the rendered text with vim motions, and the
whole review workflow — comments and suggested changes — lives here.
`⌘R` again returns to the source, caret kept in place.

## Navigating

- `h j k l`, `w / b / e`, `0 / $` — move the caret through the prose.
- `gg / G` — document start / end; `⌃d / ⌃u`, `⌃f / ⌃b`, ++space++ —
  half-page and full-page scrolling.
- `gh` — **headings overview**: an outline jump-list of the document
  (`j`/`k` to move, ++enter++ or a digit to jump, ++esc++ to close).
- `/` — **search** with a live fuzzy hit list (same as the
  [write view](writing.md)); `n` / `N` step through the hits.
- `go` — open another file without leaving the reading view (see
  [Opening files](opening.md)).

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
- `gc` — **changes overview**: a jump-list of every suggestion and comment.
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
