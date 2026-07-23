---
name: textli
description: >
  Author and review Markdown documents that a human reads, annotates, and
  navigates in textli — a distraction-free editor whose reading view renders
  the file with typeset pandoc math, followable `path:line` source
  references, and inline CriticMarkup review (comments and track-change
  suggestions). Trigger when handing a Markdown document to a human for
  reading or review (design docs, reports, papers, "write it up so I can
  review it"), when a Markdown file contains CriticMarkup marks ({>>…<<},
  {++…++}, {--…--}, {~~…~>…~~}) to process, when asked to review or
  annotate a human's draft, or when writing a document genre covered by
  references/ (decision doc, learning doc, scientific paper). Do NOT
  trigger for ordinary Markdown nobody will process in textli (READMEs,
  changelogs, code comments).
---

# textli — authoring and review collaboration

textli renders a Markdown file into a typeset reading view the human
navigates with vim motions, and stores all review annotations **inline in
the file** as [CriticMarkup](http://criticmarkup.com/) — no sidecar files.
You edit the same file with `Read` / `Write` / `Edit`; textli watches it
and reloads **in place**, keeping the human's caret and scroll. So a
document is a shared workspace: the human annotates in the editor, you
respond through the file, and the collaboration leaves its trail in the
Markdown itself (and in git).

## Writing for the reading view

- **Headings are the navigation system.** The outline popup (`gh`), the
  status breadcrumb, and `#heading-slug` anchors all key off headings —
  give every reviewable concern its own heading. Slug = heading text
  lowercased, punctuation dropped, spaces → hyphens (`## 3. Decisions` →
  `#3-decisions`). Anchors work from other documents (`notes.md#section`
  opens that heading in place) and from the CLI
  (`textli notes.md#design-decisions`).
- **Links open in place.** A relative link to another `.md` renders that
  file where you stand (`gb` returns), so a folder of linked notes reads
  like a small wiki. Web/mail links open in the browser; `#slug` jumps
  within the document.
- **Cite code as source references, never as pasted snippets.** Inline
  code like `` `textli/editor.py:2455` ``, `` `view.py:80-95` `` or a bare
  `` `editor.py` `` is followable: Enter opens the file read-only at
  that line, `gb` comes back. Resolution: beside the document, then up its
  parent folders, then bare names anywhere in the enclosing repository. A
  reference needs an extension or a line anchor (`--read` or `QWidget`
  stay prose). This keeps a doc lean and its evidence live instead of
  stale.
- **Math is pandoc math.** `$E = mc^2$` inline, `$$…$$` display — rendered
  as real typeset formulas, and the source converts to LaTeX/PDF
  untouched. Delimiters are strict: the opening `$` must hug a non-space,
  the closing `$` must not be followed by a digit, `\$` escapes a literal
  dollar. TeX subset only (fractions, integrals, sums, roots, matrices,
  Greek — no custom macros); a formula that fails to parse falls back to a
  raw-TeX code chip.
- **Fenced code, tables, images** all render typeset: tag fences with a
  language for highlighting; image paths resolve relative to the
  document's folder.
- **A value table becomes a chart** with a `<!-- chart: … -->` marker on
  the line right above a pipe table — `<!-- chart: bar x=Quarter -->` or
  `<!-- chart: line x=N table -->`. Types are `bar` and `line`; `x=<col>`
  names the axis column (default first), `y=<col,col>` picks a subset of
  series (default: every other column), a bare `table` flag keeps the grid
  below the chart. Every cell that isn't the x column must be a single
  number — pack two metrics in a cell (`113 / 6.3`) and it falls back to
  the plain table, so split them into one chart per metric. A header's
  trailing unit (`speed [m/s]`) lifts to the y-axis label. The marker is an
  ordinary HTML comment, so GitHub and pandoc still see a normal table; any
  error falls back to the grid, never a broken page. Reviewable like a
  formula — `c`/`s` on it lands the mark on the whole table source.
- **A `.grafli` diagram renders inline** when referenced as an image —
  `![](architecture.grafli)`, resolved against the document's folder.
  textli shells out to grafli's `render` CLI; the `.grafli` source stays a
  plain editable file beside the document and the Markdown stays portable
  (GitHub and pandoc see an ordinary image). Use the **image** shape
  (`![](d.grafli)`) to render; a plain link (`[text](d.grafli)`) is not a
  diagram. Degrades quietly to a normal missing-image when grafli isn't on
  `PATH`.

## The annotation layer — two kinds, never conflated

All marks are plain CriticMarkup in the file:

```text
{==span==}{>>a comment on it<<}     comment, anchored to a span
{>>a comment at this spot<<}        comment, unanchored
{++added text++}                    suggestion: insert
{--removed text--}                  suggestion: delete
{~~old~>new~~}                      suggestion: replace
```

- **Comments** (`{>>…<<}`) are the *remark channel*: the human's feedback
  on your document, or your review feedback on theirs. They ask, point,
  and judge — they never change text by themselves.
- **Suggestions** (`{++…++}` / `{--…--}` / `{~~…~>…~~}`) are *proposed
  edits* the human resolves: `]s`/`[s` step through them, `a`/`x` accept
  or reject (caret advances), `⇧A`/`⇧X` resolve all, `gc` lists every
  mark, `p` previews the text as if all were accepted. Comments step with
  `]c`/`[c`; Enter reveals one, `⇧D` deletes it.

Rules that keep the layer trustworthy:

- **Substantive revisions to a document under review are always
  suggestions, never silent rewrites.** Direct edits are for initial
  authoring, and for trivial fixes the human explicitly waved through.
- **One suggestion = one decision.** Mark the smallest span that carries
  the change (`{~~word~>better word~~}`, not a whole rewrapped paragraph),
  so each accept/reject is a meaningful act. Many small marks beat one
  monolith.
- **Never place marks inside fenced code blocks** — CriticMarkup renders
  literally there. To change code in a fence, comment on the paragraph
  before it or suggest the fence as a whole from outside.
- **Don't stack suggestions.** To revise your own still-open suggestion,
  replace it; a paragraph accumulating layered marks reads as noise.

## The collaboration loop

1. **Author** the document as plain Markdown — a first draft carries no
   marks. Hand the file path over and stop.
2. The human reads in textli and leaves `{>>remarks<<}`, usually anchored
   with `{==…==}`.
3. **Collect every remark with its location before acting** — scan the
   file for `{>>…<<}` (with any `{==…==}` anchor directly before it) so
   nothing is silently dropped.
4. **Respond in place, by kind:**
   - remark states a decision or fix → apply it as a **suggestion**, and
     strip the now-resolved `{>>…<<}` so a clean read reflects the
     settled state;
   - remark asks a question → **answer inside the comment** as a short
     thread (keep their text, append `AI: …`); the human deletes it with
     `⇧D` when satisfied;
   - remark is ambiguous, or conflicts with another remark or an earlier
     decision → **don't guess in the doc**; carry it to the convergence
     protocol below.
5. The file watcher shows your update live — no restart, no re-open.

## Convergence — when to leave the doc for chat

In-doc iteration is precise but slow-cycled; don't let rounds multiply.

- **Round one is always in-doc** and full-fidelity: every remark gets a
  suggestion or an in-place answer.
- **Two in-doc rounds are the ceiling.** Anything still unresolved after
  the second pass becomes **1–3 direct questions in chat** — get the
  answers, apply them as one final suggestion pass. A third layer of
  marks on the same issue is a smell, not diligence.
- **Escalate early for cross-cutting conflicts.** When two remarks
  contradict each other, or a remark reopens something previously
  decided, that's a conversation, not an annotation.
- **Never split one remark's resolution across doc and chat.** The human
  must be able to read the state from one channel.

## Reviewing a human's draft

The same layer runs in reverse when you are the reviewer:

- **Prefer a concrete suggestion over a comment that describes the
  edit.** "Tighten this" is a comment; the tightened sentence is a
  suggestion the author resolves with one key.
- **Use comments for judgment calls** the author must weigh — a claim
  that needs evidence, a structural doubt, a question. Anchor them:
  `{==the exact span==}{>>why it worries you<<}`.
- **Comment sparingly.** A wash of highlights reads as noise; hold to the
  load-bearing issues and let small stuff ride or be a tiny suggestion.
- **Cite checkable evidence.** A remark that points at
  `` `textli/comments.py:36` `` is verifiable in one keystroke; "I think
  the parser disagrees" is not.
- **Never rewrite the draft wholesale** — it's their text; you propose,
  they decide.

## Genre playbooks

Before writing one of these document kinds, read the matching reference:

- `references/decision-doc.md` — a design/architecture proposal for async
  review: requirement first, decisions with rationale, code references.
- `references/learning-doc.md` — teaching material: map before territory,
  dives, active-recall quiz with a separate key.
- `references/paper.md` — a scientific paper that keeps IMRaD but is easy
  to process: abstract as TL;DR, typeset math, live references.
