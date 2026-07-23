# Learning doc — teach a system so the reader genuinely learns it

The job: a **self-contained learning package** the reader works through
at their own pace — map before territory, depth where it's load-bearing,
active recall at the end. Teach, don't just report.

## The package

A folder of linked Markdown, sized to the scope:

```text
<topic>/
  overview.md      the map + index into the dives
  <area>.md        one dive per major area
  quiz.md          tiered questions with blanks to fill in
  key.md           answer key — written for a fresh grader
```

- **overview.md** — the 5–7 **big ideas**; what the system *is* and why
  it exists; architecture at a glance; **what's special or unusual**
  (call it out explicitly — that's what an experienced reader wants
  first); an index of relative links into the dives.
- **Dives** — one per major area, ordered high→low: architecture → key
  concepts and patterns → dependencies → the algorithms or twists that
  matter to the big picture. Cap the set (5–7 for a whole system, 2–3
  for a focused topic); appropriate depth beats completeness. Gloss each
  dependency in a line or two — what it is, what it's for — not a
  tutorial.
- **quiz.md** — 6–10 questions laddered high→low, a clearly-marked blank
  under each, ending in one **boss question** that needs 2–3 big ideas
  combined — the one that proves the map formed.
- **key.md** — expected answer per question, what "good" vs "shallow"
  looks like, and a pointer to the dive that justifies it — written so a
  grader with **no memory of writing the package** can grade reliably.

## Authoring it for textli

- **Relative links make the package a wiki**: `overview.md` links each
  dive, dives cross-link each other and back — the reader follows with
  Enter, returns with `gb`, and never leaves the reading view.
- **Deep-link with heading slugs** (`overview.md#big-ideas`) to point a
  concept at one section rather than a whole file.
- **Source references are the teaching evidence**: a dive that claims
  "rendering batches its passes" cites `editor.py:173` and the reader
  verifies it in one keystroke. Prefer references over pasted code
  except when the code itself is the lesson.
- **Math where the domain needs it** — pandoc `$…$` renders typeset, so
  a complexity argument or a formula can be real notation.
- **Ladder the headings** — the `gh` outline is the course syllabus;
  make it read like one.

## The learning loop

1. Generate the package, name the folder, stop — the reader studies and
   fills the quiz on their own time. Mention that confusion goes inline
   as `{>>don't get this<<}` comments while they read.
2. The remarks mark exactly where understanding is thin — address each,
   substantive refinements as **suggestions** per the core protocol.
3. Grade the filled quiz against `key.md`: a compact score line first,
   then per answer a short verdict, the fuller correct answer, and the
   dive worth re-reading.
4. Go Socratic *after* grading, targeting the gaps — not before, or it
   degrades into a generic question drip.
