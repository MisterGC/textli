# Working with AI agents

textli was built for review loops between humans and AI agents: the
annotations live inline in the Markdown as
[CriticMarkup](http://criticmarkup.com/), the editor
[watches the file](writing.md#files-saving) and reloads in place, so an
agent editing the document with its own tools and a human reading it in
textli share one file as their workspace — no sidecars, no export step.

The loop looks like this:

1. The agent writes a document — a design doc, a report, a paper draft —
   and hands over the path.
2. You read it in the [reading view](reading.md), leaving
   `{>>comments<<}` where you have remarks.
3. The agent collects your remarks and answers **as suggestions** —
   `{++insert++}`, `{--delete--}`, `{~~old~>new~~}` — which render as
   track changes you step through (`]s`) and accept or reject (`a`/`x`),
   live, without reopening the file.

## The bundled skill

So that agents hold up their end well, textli ships an installable
**agent skill** — instructions that teach an AI tool how to author for
the reading view (headings as navigation, pandoc math, followable
`path:line` source references), how to use the two annotation layers
without conflating them, and when to stop iterating in the document and
ask a direct question instead. Genre playbooks come along as on-demand
references: a decision doc for aligning on sizeable work, a learning doc
for teaching a codebase, and a scientific paper that keeps IMRaD but
reads easily — with `examples/paper.md` in the repository as a worked
example whose object of research is textli itself.

Install it for your AI tools:

```sh
textli skill install            # prompts per tool
textli skill install claude     # ~/.claude/skills/textli/
textli skill install codex      # ~/.agents/skills/textli/
textli skill install opencode   # ~/.config/opencode/skills/textli/
textli skill install all --force
```

`textli skill check` reports the install status per tool — `ok`, `stale`
(a newer skill ships with your textli), `modified` (local edits), or
`missing` — and `textli skill uninstall` removes it. Installed skills are
version-stamped, so after upgrading textli a `check` tells you when to
re-run `install`. OpenCode also reads the Claude and Codex locations, so
one install usually covers it.

For tools without a skill directory, `textli skill` prints the whole
skill (core + references inlined) to stdout — pipe it wherever your
setup wants it, or `textli skill --core` for just the lean core.
