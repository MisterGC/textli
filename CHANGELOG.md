# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-07-01

### Added

- **Initial extraction from grafli.** The zen Markdown editor that grew inside
  [grafli](https://github.com/MisterGC/grafli) becomes its own package:
  - Full-window, iA Writer-style writing surface with vim keybindings
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
