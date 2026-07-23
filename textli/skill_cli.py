"""The ``textli skill`` CLI — print, install, check, uninstall the
bundled AI skill.

Orchestration only (argparse, prompts, TTY detection, exit codes); the
install/check logic lives in ``skill_install.py``. No ``QApplication``
is created on this path — ``textli skill`` works without a display.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


SKILL_DOCS = """\
Subcommands:
  install   Install the bundled textli skill for one or more AI tools.
  check     Report install status per tool (and whether a newer version
            is available).
  uninstall Remove the installed textli skill from one or more tools.

Supported targets (user-level paths follow the agentskills.io convention;
each gets the skill directory — SKILL.md plus references/):

  claude    ~/.claude/skills/textli/
            https://code.claude.com/docs/en/skills
  codex     ~/.agents/skills/textli/
            https://developers.openai.com/codex/skills
  opencode  ~/.config/opencode/skills/textli/
            https://opencode.ai/docs/skills

(OpenCode also reads from `~/.claude/skills/` and `~/.agents/skills/`, so
installing for `claude` or `codex` is automatically picked up by OpenCode.)

Without a subcommand, `textli skill` prints the full skill to stdout —
SKILL.md with every reference file inlined, for single-file consumers.
Pass --core for just the lean core SKILL.md.
"""

# Concat / inline order for the reference files; unknown names sort after.
_REFERENCE_ORDER = ("decision-doc.md", "learning-doc.md", "paper.md")


def _skill_dir() -> Path:
    """Return the path to the bundled skill directory."""
    from importlib.resources import files
    return Path(str(files("textli.skills.textli")))


def _skill_path() -> Path:
    """Return the path to the bundled SKILL.md."""
    return _skill_dir() / "SKILL.md"


def _skill_references() -> dict[str, str]:
    """Return the bundled reference files as ``{name: content}``, in
    the canonical inline order.
    """
    ref_dir = _skill_dir() / "references"
    if not ref_dir.is_dir():
        return {}
    def order(p: Path) -> tuple[int, str]:
        try:
            return (_REFERENCE_ORDER.index(p.name), p.name)
        except ValueError:
            return (len(_REFERENCE_ORDER), p.name)
    return {
        p.name: p.read_text(encoding="utf-8")
        for p in sorted(ref_dir.glob("*.md"), key=order)
    }


def _skill_concat() -> str:
    """The single-file build: SKILL.md with every reference inlined."""
    parts = [_skill_path().read_text(encoding="utf-8")]
    for name, content in _skill_references().items():
        parts.append(
            f"\n\n---\n\n<!-- inlined from references/{name} -->\n\n{content}"
        )
    return "".join(parts)


def _textli_version() -> str:
    from textli import __version__
    return __version__


def run(argv: list[str]) -> int:
    """Entry point for ``textli skill …`` — returns an exit code."""
    if argv and argv[0] in ("install", "check", "uninstall"):
        sub = argv[0]
        rest = argv[1:]
        if sub == "install":
            return _cmd_install(rest)
        if sub == "check":
            return _cmd_check(rest)
        return _cmd_uninstall(rest)

    parser = argparse.ArgumentParser(
        prog="textli skill",
        description="Print the bundled textli AI skill (SKILL.md + references).",
        epilog=SKILL_DOCS,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-o", "--output", type=Path, default=None,
        help="Write the skill to this path instead of stdout",
    )
    parser.add_argument(
        "--core", action="store_true",
        help="Emit only the lean core SKILL.md, without inlining the "
             "reference files",
    )
    parser.add_argument(
        "--where", action="store_true",
        help="Print the path of the bundled skill directory and exit",
    )
    args = parser.parse_args(argv)

    if args.where:
        print(_skill_dir())
        return 0
    text = (
        _skill_path().read_text(encoding="utf-8") if args.core
        else _skill_concat()
    )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
        print(f"Wrote {args.output}", file=sys.stderr)
        return 0
    sys.stdout.write(text)
    return 0


# ── install / check / uninstall ───────────────────────────────────


def _resolve_targets(positional: str | None) -> list[str]:
    """Map a positional ('all', 'claude', 'codex', 'opencode', or None
    when called from `check` where None means all) to a target list.
    """
    from textli.skill_install import ALL_TARGETS
    if positional is None or positional == "all":
        return list(ALL_TARGETS)
    if positional not in ALL_TARGETS:
        raise SystemExit(
            f"unknown target: {positional!r} "
            f"(valid: all, {', '.join(ALL_TARGETS)})"
        )
    return [positional]


def _prompt_yes_no(question: str, *, default_yes: bool) -> bool:
    """Tiny y/n prompt. Default is signalled with capital letter."""
    suffix = "[Y/n]" if default_yes else "[y/N]"
    while True:
        try:
            ans = input(f"{question} {suffix} ").strip().lower()
        except EOFError:
            return default_yes
        if not ans:
            return default_yes
        if ans in ("y", "yes"):
            return True
        if ans in ("n", "no"):
            return False


def _cmd_install(argv: list[str]) -> int:
    from textli.skill_install import (
        compute_status, write_skill, parent_dir_exists,
        OK, STALE, MODIFIED, MISSING,
    )

    parser = argparse.ArgumentParser(
        prog="textli skill install",
        description="Install the bundled textli skill for one or more AI tools.",
    )
    parser.add_argument(
        "target", nargs="?", default=None,
        help="Target tool (all | claude | codex | opencode). "
             "Omit to be prompted per target.",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Skip all prompts; overwrite existing installs and create "
             "missing parent directories without asking.",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show planned actions without writing any files.",
    )
    args = parser.parse_args(argv)

    if args.dry_run and args.force:
        # Harmless combo, but explicit so users don't expect writes.
        print("--dry-run set; --force has no effect on writes.", file=sys.stderr)

    interactive_per_target = args.target is None
    targets = _resolve_targets(args.target)

    if not args.force and not args.dry_run and not sys.stdin.isatty():
        print(
            "textli skill install: stdin is not a TTY; pass --force to "
            "install non-interactively, or --dry-run to preview.",
            file=sys.stderr,
        )
        return 2

    packaged = _skill_path().read_text(encoding="utf-8")
    references = _skill_references()
    version = _textli_version()

    any_drift = False

    for t in targets:
        st = compute_status(t, packaged, version, references)
        # Show context line so the user always sees the destination.
        if st.status == OK:
            print(f"[ok]      {t}: already current at {st.path} (textli {version})")
            continue
        if st.status == MISSING:
            note = f"will install to {st.path} (textli {version})"
        elif st.status == STALE:
            note = (
                f"installed {st.installed_version} -> packaged {version}; "
                f"will update {st.path}"
            )
        elif st.status == MODIFIED:
            note = (
                f"local changes detected at {st.path}; "
                f"overwriting will discard them"
            )
        else:  # UNKNOWN
            note = (
                f"existing file at {st.path} was not installed by "
                f"`textli skill install`; cannot determine source"
            )
        print(f"[{st.status}] {t}: {note}")

        if args.dry_run:
            any_drift = True
            continue

        # Decide whether to write.
        if args.force:
            do_write = True
        elif interactive_per_target or st.status != MISSING:
            default_yes = st.status in (MISSING, STALE)
            verb = "Install" if st.status == MISSING else "Overwrite"
            do_write = _prompt_yes_no(f"  {verb}?", default_yes=default_yes)
        else:
            do_write = True

        if not do_write:
            print(f"  skipped {t}")
            continue

        # Parent dir check (skip when --force).
        if not args.force and not parent_dir_exists(t):
            print(
                f"  note: parent directory {st.path.parent.parent} does "
                f"not exist (the target tool may not be installed)."
            )
            if not _prompt_yes_no("  create and install anyway?", default_yes=False):
                print(f"  skipped {t}")
                continue

        path = write_skill(t, packaged, version, references)
        print(f"  wrote {path}")
        if references:
            print(f"  wrote {path.parent / 'references'} ({len(references)} files)")

    if args.dry_run and any_drift:
        return 1
    return 0


def _cmd_check(argv: list[str]) -> int:
    import json as _json
    from textli.skill_install import (
        compute_status, DRIFT_STATES, OK, STALE, MODIFIED, UNKNOWN,
    )

    parser = argparse.ArgumentParser(
        prog="textli skill check",
        description="Report install status of the textli skill per target.",
    )
    parser.add_argument(
        "target", nargs="?", default="all",
        help="Target tool (all | claude | codex | opencode). "
             "Default: all targets.",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Emit machine-readable JSON instead of a human-readable table.",
    )
    args = parser.parse_args(argv)

    targets = _resolve_targets(args.target)
    packaged = _skill_path().read_text(encoding="utf-8")
    references = _skill_references()
    version = _textli_version()

    statuses = [compute_status(t, packaged, version, references) for t in targets]

    if args.json:
        print(_json.dumps([s.to_dict() for s in statuses], indent=2))
    else:
        for s in statuses:
            tag = f"[{s.status}]"
            if s.status == OK:
                extra = f"(textli {s.packaged_version})"
            elif s.status == STALE:
                extra = (
                    f"(installed {s.installed_version} -> "
                    f"packaged {s.packaged_version})"
                )
            elif s.status == MODIFIED:
                extra = f"(installed {s.installed_version}; locally modified)"
            elif s.status == UNKNOWN:
                extra = "(no version marker; unknown provenance)"
            else:  # MISSING
                extra = ""
            print(f"{s.target:<9} {tag:<11} {s.path} {extra}".rstrip())

    has_drift = any(s.status in DRIFT_STATES for s in statuses)
    return 1 if has_drift else 0


def _cmd_uninstall(argv: list[str]) -> int:
    from textli.skill_install import remove_skill, compute_status, MISSING

    parser = argparse.ArgumentParser(
        prog="textli skill uninstall",
        description="Remove the installed textli skill from one or more AI tools.",
    )
    parser.add_argument(
        "target", nargs="?", default=None,
        help="Target tool (all | claude | codex | opencode). "
             "Omit to be prompted per target.",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Skip all prompts.",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show planned actions without removing any files.",
    )
    args = parser.parse_args(argv)

    targets = _resolve_targets(args.target)

    if not args.force and not args.dry_run and not sys.stdin.isatty():
        print(
            "textli skill uninstall: stdin is not a TTY; pass --force to "
            "uninstall non-interactively, or --dry-run to preview.",
            file=sys.stderr,
        )
        return 2

    packaged = _skill_path().read_text(encoding="utf-8")
    references = _skill_references()
    version = _textli_version()

    for t in targets:
        st = compute_status(t, packaged, version, references)
        if st.status == MISSING:
            print(f"[missing] {t}: nothing to remove at {st.path.parent}")
            continue
        print(f"[present] {t}: {st.path.parent} (status: {st.status})")

        if args.dry_run:
            continue

        do_remove = (
            args.force
            or _prompt_yes_no("  remove?", default_yes=False)
        )
        if not do_remove:
            print(f"  skipped {t}")
            continue

        removed = remove_skill(t)
        if removed:
            print(f"  removed {st.path.parent}")
        else:
            print("  nothing was removed (already gone)")
    return 0
