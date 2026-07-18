# Scientific paper — rigorous structure, easy to process

The job: a paper that keeps the skeleton of scientific work — a reader
can locate the claim, the method, and the evidence where they expect
them — while being genuinely pleasant to process: the contribution lands
in the abstract, the argument shows in the outline, and the evidence is
one keystroke away instead of buried in an appendix.

## Structure — IMRaD, kept honest

1. **Title** — the claim, not the topic ("X improves Y under Z", not
   "A study of X").
2. **Abstract** — the honest TL;DR, no suspense: one sentence of
   context, the gap, what was done, the **headline result with its
   numbers**, and the implication. A reader who stops here should leave
   with the finding, not a teaser.
3. **Introduction** — the problem, why it resists the obvious approach,
   and an explicit **contribution list** ("This paper contributes: …")
   at the end. Each contribution maps to a section.
4. **Related work** — positioned, not enumerated: for each cluster, one
   line on what it does and one on **how this work differs**.
5. **Method / design** — what was built or done, in enough detail to
   re-do it. Notation defined at first use.
6. **Results / evaluation** — measurements against a stated baseline,
   units always, setup reproducible.
7. **Discussion & limitations** — what the results mean, and an honest,
   own-section account of where they don't hold. Never bury limitations
   in a closing clause.
8. **Conclusion** — the finding restated in the light of the evidence,
   one paragraph.
9. **References** — a numbered list; cite inline as `[1]`. Where the
   venue is the open web, markdown links are the better citation — they
   are followable in the reading view.

## Processing-friendly rules

- **One claim per paragraph, topic sentence first** — the paper should
  survive being read as first-sentences-only.
- **Numbers carry units and a comparison** ("15 s → milliseconds on a
  4,500-line file", never "significantly faster").
- **Display math (`$$…$$`) only for load-bearing equations** the text
  refers back to; everything else stays inline (`$O(s \log n)$`). Since
  textli renders the TeX subset without custom macros, notation stays
  portable — the same source converts to LaTeX or PDF untouched when
  the draft grows into a submission.
- **Figures and tables interpretable from the caption alone.** Markdown
  tables render typeset; images resolve relative to the paper's folder.
- **Cite the artifact, not a snapshot of it.** When the object of study
  is code or data, reference it live — `` `textli/comments.py:36` `` —
  so a reviewer verifies the claim at the real line instead of trusting
  a pasted excerpt. This is reproducibility at reading speed: keep the
  paper beside the repository it studies (resolution walks up parent
  folders, so `paper/` next to `src/` just works).
- **Headings give every section a stable slug** — reviewer discussion
  can point at `paper.md#4-evaluation` precisely.

## The revision loop

Co-author and advisor rounds are the core collaboration loop:

1. Hand the draft over; reviewers annotate inline —
   `{==this claim==}{>>needs a baseline<<}`.
2. Revise **as suggestions**, never silent rewrites — each accepted
   `{~~old~>new~~}` is a conscious editorial act, and the accept/reject
   trail *is* the revision history between git commits.
3. The convergence protocol applies: two in-doc rounds, then the
   remaining disagreements move to direct discussion. Methodological
   disputes (baseline choice, what to measure) are chat material from
   the start — annotation is for the text, not for the study design.

A worked example ships with textli: `examples/paper.md` — a short paper
whose object of research is textli itself, following this playbook.
