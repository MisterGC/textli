# Decision doc — align on sizeable work before building it

The job: one **self-contained, decision-first** document that makes your
complete picture of a piece of work legible *before* it happens, so the
reader corrects the framing and owns the expensive calls — async, at
reading pace, without drowning in detail. The reader's go is the
approval; you don't build until it comes.

## The spine (in this order)

1. **The requirement, as understood (+ motivation)** — the first and most
   important section. What is wanted, in your words; *why* it matters;
   what's **in scope** and explicitly **out of scope**; the
   **assumptions** you're making (invite correction). A wrong framing
   here poisons every decision below it and is invisible to a reader who
   only scans decisions — make this substantial.
2. **Decisions** — only forks that are **expensive to reverse or
   constrain future work**, grouped:
   - **Structural** — module boundaries, where responsibility lives,
     data-model shape.
   - **External commitment** — a new dependency, pattern, or API
     contract; for anything new, one line on *what it is and why chosen*.
   - **Cross-cutting** — auth, persistence, migration, public interfaces.
   Each decision: a one-line statement plus its **rationale**. Local,
   reversible-in-an-afternoon choices (naming, helper structure) stay
   out. Close with a **"Resolved silently"** appendix — a one-line list
   of the choices you made without elaborating, so the reader can
   spot-check whether you mis-filed a load-bearing call as trivial.
3. **Phasing** — an ordered plan in phases; note which phases can reorder
   and which block on the reader. Phases double as checkpoints.
4. **Key code references** — where each change lands, as followable
   `path:line` references, so the blast radius is visible before it
   happens. Name files that deliberately stay **untouched**.

Tone: a decision log for the reader's review, not a polished team spec.

## Authoring it for textli

- **Promote every individually-reviewable decision to its own heading**
  so it has a slug — the reader (and other documents) can deep-link to
  `#d3-storage-layout` instead of "the third bullet".
- **Reference code live** (`textli/editor.py:2455`), don't paste
  snippets: Enter shows the evidence at the real line, `gb` returns, and
  the doc never goes stale.
- **Self-contained** means a reader with paper could reconstruct the
  whole picture from the prose alone — link out for depth, never for
  necessity.

## The review loop

1. Write the doc, hand the path over, and **stop — no implementation
   until the go.** Without the hard stop the document is narration, not
   alignment. Mention that remarks go inline as `{>>comments<<}`.
2. The reader annotates in textli; you collect every remark, then apply
   the core protocol: agreed changes as **suggestions**, questions
   answered in the comment thread, ambiguities escalated to chat after
   at most two in-doc rounds.
3. During implementation, append any deviation from an approved decision
   as one line ("D3 changed: X because Y") so the doc reflects what was
   built, not what was planned.
