"""Vim-style key handler for the zen markdown editor."""

from __future__ import annotations

import enum
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent, QTextCursor
from PySide6.QtWidgets import QPlainTextEdit

from textli.constants import _CTRL_MOD


class VimMode(enum.Enum):
    NORMAL = "NORMAL"
    INSERT = "INSERT"
    VISUAL = "VISUAL"


_MoveOp = QTextCursor.MoveOperation
_MoveMode = QTextCursor.MoveMode
# Qt reports line breaks in ``selectedText()`` as U+2029 (paragraph separator);
# the register keeps real newlines so paste round-trips.
_PARA_SEP = " "


class VimKeyHandler:
    """Stateful vim key handler that operates on a QPlainTextEdit."""

    def __init__(
        self,
        editor: QPlainTextEdit,
        mode_changed: Callable[[VimMode], None],
        close_save: Callable[[], None],
        close_cancel: Callable[[], None],
        initial_mode: VimMode = VimMode.NORMAL,
        open_file: Callable[[], None] | None = None,
        open_headings: Callable[[], None] | None = None,
    ):
        self._editor = editor
        self._mode_changed = mode_changed
        self._close_save = close_save
        self._close_cancel = close_cancel
        # `go` / `gh` — hosts with a document concept (the zen editor) open the
        # file dialog / headings outline; single-field hosts (InlineVimEditor)
        # leave them unset, so the sequences are harmless no-ops there.
        self._open_file = open_file
        self._open_headings = open_headings
        self._mode = initial_mode
        self._pending = ""
        # Numeric count prefix accumulated before a motion/operator (``3j``,
        # ``2dd``); ``_pending_count`` carries it across a two-key operator so
        # ``2dd`` still knows the 2 when the second ``d`` arrives.
        self._count = ""
        self._pending_count = 1
        # Single unnamed register shared by yank, delete and paste. A line-wise
        # yank/delete (``yy``/``dd``) pastes on its own line; a char-wise one
        # pastes inline.
        self._register = ""
        self._register_linewise = False
        # Block cursor everywhere but INSERT (NORMAL and VISUAL show it); the
        # caret only thins out while typing. Callers that open in INSERT (inline
        # editing) pass ``initial_mode``; the zen editor keeps the NORMAL default.
        self._editor.setOverwriteMode(initial_mode != VimMode.INSERT)

    @property
    def mode(self) -> VimMode:
        return self._mode

    @property
    def has_pending(self) -> bool:
        """True while a multi-key sequence (g…, d…, y…) awaits its second key,
        or a count prefix is building — the host must not intercept keys that
        would complete it."""
        return bool(self._pending) or bool(self._count)

    def _set_mode(self, mode: VimMode):
        if mode == self._mode:
            return
        self._mode = mode
        self._editor.setOverwriteMode(mode != VimMode.INSERT)
        self._mode_changed(mode)

    def handle_key(self, event: QKeyEvent) -> bool:
        """Process a key event. Returns True if consumed."""
        if self._mode == VimMode.INSERT:
            return self._handle_insert(event)
        if self._mode == VimMode.VISUAL:
            return self._handle_visual(event)
        return self._handle_normal(event)

    # ── Insert mode ──

    def _handle_insert(self, event: QKeyEvent) -> bool:
        if event.key() == Qt.Key.Key_Escape:
            self._set_mode(VimMode.NORMAL)
            self._move(_MoveOp.Left)
            return True
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            # Insert the newline ourselves rather than passing through. On
            # macOS the input method (enabled in insert mode) swallows a
            # bare Return so the default handler never inserts a line break
            # — only Shift+Return got through. Handling it here makes Enter
            # work everywhere and keeps behaviour identical across platforms.
            self._editor.textCursor().insertText("\n")
            return True
        return False  # pass through to editor

    # ── Normal mode ──

    def _handle_normal(self, event: QKeyEvent) -> bool:
        key = event.key()
        mods = event.modifiers()
        shift = bool(mods & Qt.KeyboardModifier.ShiftModifier)
        ctrl = bool(mods & _CTRL_MOD)

        # Handle pending multi-key sequences (they consume the count prefix).
        if self._pending:
            return self._handle_pending(event)

        # Numeric count prefix — digits accumulate (``3``, ``12``). A bare
        # ``0`` is the start-of-line motion below; ``0`` is a count digit only
        # once a count is already building.
        if event.text().isdigit() and (event.text() != "0" or self._count):
            self._count += event.text()
            return True
        has_count = bool(self._count)
        count = self._take_count()   # 1 when no prefix; resets the accumulator

        # Esc in normal mode — save and close
        if key == Qt.Key.Key_Escape:
            if shift:
                self._close_cancel()
            else:
                self._close_save()
            return True

        # ── Motion ──
        if key == Qt.Key.Key_H and not shift:
            self._move(_MoveOp.Left, count)
            return True
        if key == Qt.Key.Key_L and not shift:
            self._move(_MoveOp.Right, count)
            return True
        if key == Qt.Key.Key_J and not shift:
            self._move(_MoveOp.Down, count)
            return True
        if key == Qt.Key.Key_K and not shift:
            self._move(_MoveOp.Up, count)
            return True

        # w — next word start
        if key == Qt.Key.Key_W and not shift:
            self._move(_MoveOp.NextWord, count)
            return True
        # b — previous word start
        if key == Qt.Key.Key_B and not shift:
            self._move(_MoveOp.PreviousWord, count)
            return True
        # e — end of word
        if key == Qt.Key.Key_E and not shift:
            self._move(_MoveOp.EndOfWord, count)
            return True

        # 0 — start of line
        if key == Qt.Key.Key_0:
            self._move(_MoveOp.StartOfBlock)
            return True
        # $ — end of line
        if event.text() == "$":
            self._move(_MoveOp.EndOfBlock)
            return True

        # G — end of document, or <count>G — go to that line
        if key == Qt.Key.Key_G and shift:
            if has_count:
                self._goto_line(count)
            else:
                self._move(_MoveOp.End)
            return True
        # g — start pending for gg
        if key == Qt.Key.Key_G and not shift:
            self._pending = "g"
            self._pending_count = count
            return True

        # d — start pending for dd, dw
        if key == Qt.Key.Key_D and not shift:
            self._pending = "d"
            self._pending_count = count
            return True
        # y — start pending for yy, yw
        if key == Qt.Key.Key_Y and not shift:
            self._pending = "y"
            self._pending_count = count
            return True

        # x — delete char(s) under/after the cursor
        if key == Qt.Key.Key_X and not shift:
            self._delete_chars(count)
            return True

        # p / P — paste after / before, count copies
        if key == Qt.Key.Key_P and not shift:
            self._paste(after=True, count=count)
            return True
        if key == Qt.Key.Key_P and shift:
            self._paste(after=False, count=count)
            return True

        # v — enter VISUAL, selecting from here as the motions extend
        if key == Qt.Key.Key_V and not shift and not ctrl:
            self._set_mode(VimMode.VISUAL)
            return True

        # u / Ctrl-r — undo / redo, riding the editor's native undo stack
        # (Qt restores the caret to the change site, the way vim leaves you
        # there). So a NORMAL-mode edit is reversible without dropping to
        # INSERT for the platform ⌘Z.
        if key == Qt.Key.Key_U and not shift and not ctrl:
            for _ in range(count):
                self._editor.undo()
            return True
        if key == Qt.Key.Key_R and ctrl:
            for _ in range(count):
                self._editor.redo()
            return True

        # ── Enter insert mode ──
        if key == Qt.Key.Key_I and not shift:
            self._set_mode(VimMode.INSERT)
            return True
        if key == Qt.Key.Key_A and not shift:
            self._move(_MoveOp.Right)
            self._set_mode(VimMode.INSERT)
            return True
        if key == Qt.Key.Key_A and shift:
            self._move(_MoveOp.EndOfBlock)
            self._set_mode(VimMode.INSERT)
            return True
        if key == Qt.Key.Key_I and shift:
            self._move(_MoveOp.StartOfBlock)
            self._set_mode(VimMode.INSERT)
            return True
        if key == Qt.Key.Key_O and not shift:
            self._move(_MoveOp.EndOfBlock)
            c = self._editor.textCursor()
            c.insertText("\n")
            self._editor.setTextCursor(c)
            self._set_mode(VimMode.INSERT)
            return True
        if key == Qt.Key.Key_O and shift:
            self._move(_MoveOp.StartOfBlock)
            c = self._editor.textCursor()
            c.insertText("\n")
            c.movePosition(_MoveOp.Up)
            self._editor.setTextCursor(c)
            self._set_mode(VimMode.INSERT)
            return True

        return True  # consume unknown keys in normal mode

    def _handle_pending(self, event: QKeyEvent) -> bool:
        key = event.key()
        pending = self._pending
        self._pending = ""
        count = self._pending_count
        self._pending_count = 1

        if pending == "g":
            if key == Qt.Key.Key_G:
                # gg → first line, <count>gg → that line (1-based; no count is
                # count==1, i.e. the first line either way).
                self._goto_line(count)
                return True
            if key == Qt.Key.Key_O and self._open_file is not None:
                self._open_file()
                return True
            if key == Qt.Key.Key_H and self._open_headings is not None:
                self._open_headings()
                return True
            return True  # unknown g-sequence, consume

        if pending == "d":
            if key == Qt.Key.Key_D:
                self._delete_lines(count)
                return True
            if key == Qt.Key.Key_W:
                self._delete_word(count)
                return True
            return True  # unknown d-sequence, consume

        if pending == "y":
            if key == Qt.Key.Key_Y:
                self._yank_lines(count)
                return True
            if key == Qt.Key.Key_W:
                self._yank_word(count)
                return True
            return True  # unknown y-sequence, consume

        return True

    # ── Visual mode ──

    def _handle_visual(self, event: QKeyEvent) -> bool:
        key = event.key()
        mods = event.modifiers()
        shift = bool(mods & Qt.KeyboardModifier.ShiftModifier)
        ctrl = bool(mods & _CTRL_MOD)

        if self._pending:
            self._pending = ""
            if key == Qt.Key.Key_G:          # gg — extend to document start
                self._move(_MoveOp.Start, keep=True)
            return True

        if event.text().isdigit() and (event.text() != "0" or self._count):
            self._count += event.text()
            return True
        count = self._take_count()

        # Leave VISUAL — Esc or a second v — clearing the selection.
        if key == Qt.Key.Key_Escape or (
                key == Qt.Key.Key_V and not shift and not ctrl):
            self._clear_visual()
            return True

        # ── Motions extend the selection (anchor stays put) ──
        if key == Qt.Key.Key_H and not shift:
            self._move(_MoveOp.Left, count, keep=True)
            return True
        if key == Qt.Key.Key_L and not shift:
            self._move(_MoveOp.Right, count, keep=True)
            return True
        if key == Qt.Key.Key_J and not shift:
            self._move(_MoveOp.Down, count, keep=True)
            return True
        if key == Qt.Key.Key_K and not shift:
            self._move(_MoveOp.Up, count, keep=True)
            return True
        if key == Qt.Key.Key_W and not shift:
            self._move(_MoveOp.NextWord, count, keep=True)
            return True
        if key == Qt.Key.Key_B and not shift:
            self._move(_MoveOp.PreviousWord, count, keep=True)
            return True
        if key == Qt.Key.Key_E and not shift:
            self._move(_MoveOp.EndOfWord, count, keep=True)
            return True
        if key == Qt.Key.Key_0:
            self._move(_MoveOp.StartOfBlock, keep=True)
            return True
        if event.text() == "$":
            self._move(_MoveOp.EndOfBlock, keep=True)
            return True
        if key == Qt.Key.Key_G and shift:
            self._move(_MoveOp.End, keep=True)
            return True
        if key == Qt.Key.Key_G and not shift:
            self._pending = "g"
            return True

        # ── Operators act on the selection, then drop back ──
        if key in (Qt.Key.Key_D, Qt.Key.Key_X) and not shift:
            self._visual_op(to_insert=False)
            return True
        if key == Qt.Key.Key_C and not shift:
            self._visual_op(to_insert=True)
            return True
        if key == Qt.Key.Key_Y and not shift:
            self._visual_yank()
            return True

        return True  # consume anything else while selecting

    def _clear_visual(self):
        c = self._editor.textCursor()
        c.clearSelection()
        self._editor.setTextCursor(c)
        self._set_mode(VimMode.NORMAL)

    def _visual_op(self, *, to_insert: bool):
        """d/x delete the selection (→ NORMAL); c deletes it then enters INSERT.
        Either way the removed text lands in the register (char-wise)."""
        c = self._editor.textCursor()
        if c.hasSelection():
            self._set_register(c.selectedText().replace(_PARA_SEP, "\n"),
                               linewise=False)
            c.removeSelectedText()
            self._editor.setTextCursor(c)
        self._set_mode(VimMode.INSERT if to_insert else VimMode.NORMAL)

    def _visual_yank(self):
        """y copies the selection (char-wise) and drops back to NORMAL with the
        caret at the selection start, the way vim leaves it."""
        c = self._editor.textCursor()
        if c.hasSelection():
            self._set_register(c.selectedText().replace(_PARA_SEP, "\n"),
                               linewise=False)
            c.setPosition(c.selectionStart())
            self._editor.setTextCursor(c)
        self._set_mode(VimMode.NORMAL)

    # ── Helpers ──

    def _take_count(self) -> int:
        n = int(self._count) if self._count else 1
        self._count = ""
        return n

    def _set_register(self, text: str, linewise: bool):
        self._register = text
        self._register_linewise = linewise

    def _move(self, op: QTextCursor.MoveOperation, count: int = 1,
              *, keep: bool = False):
        mode = _MoveMode.KeepAnchor if keep else _MoveMode.MoveAnchor
        c = self._editor.textCursor()
        for _ in range(count):
            c.movePosition(op, mode)
        self._editor.setTextCursor(c)

    def _goto_line(self, n: int):
        """Move to the start of 1-based line ``n`` (clamped to the last line)."""
        c = self._editor.textCursor()
        c.movePosition(_MoveOp.Start)
        for _ in range(max(0, n - 1)):
            c.movePosition(_MoveOp.Down)
        c.movePosition(_MoveOp.StartOfBlock)
        self._editor.setTextCursor(c)

    def _delete_chars(self, count: int = 1):
        c = self._editor.textCursor()
        for _ in range(count):
            c.movePosition(_MoveOp.Right, _MoveMode.KeepAnchor)
        if c.hasSelection():
            self._set_register(c.selectedText().replace(_PARA_SEP, "\n"),
                               linewise=False)
            c.removeSelectedText()
            self._editor.setTextCursor(c)

    def _delete_word(self, count: int = 1):
        c = self._editor.textCursor()
        for _ in range(count):
            c.movePosition(_MoveOp.NextWord, _MoveMode.KeepAnchor)
        if c.hasSelection():
            self._set_register(c.selectedText().replace(_PARA_SEP, "\n"),
                               linewise=False)
            c.removeSelectedText()
            self._editor.setTextCursor(c)

    def _yank_word(self, count: int = 1):
        c = self._editor.textCursor()
        start = c.position()
        for _ in range(count):
            c.movePosition(_MoveOp.NextWord, _MoveMode.KeepAnchor)
        if c.hasSelection():
            self._set_register(c.selectedText().replace(_PARA_SEP, "\n"),
                               linewise=False)
        tc = self._editor.textCursor()
        tc.setPosition(start)
        self._editor.setTextCursor(tc)

    def _line_span(self, count: int):
        """The first block and the last block of a ``count``-line run starting
        at the caret, plus the joined text of those lines (for the register)."""
        doc = self._editor.document()
        first = doc.findBlock(self._editor.textCursor().position())
        last = first
        lines = [first.text()]
        while len(lines) < count and last.next().isValid():
            last = last.next()
            lines.append(last.text())
        return first, last, "\n".join(lines) + "\n"

    def _yank_lines(self, count: int = 1):
        first, _last, text = self._line_span(count)
        self._set_register(text, linewise=True)
        c = self._editor.textCursor()
        c.setPosition(first.position())   # yank leaves the caret on the line
        self._editor.setTextCursor(c)

    def _delete_lines(self, count: int = 1):
        first, last, text = self._line_span(count)
        self._set_register(text, linewise=True)
        c = self._editor.textCursor()
        if last.next().isValid():
            # Lines follow: take up to the next line's start, so its trailing
            # newline goes too and the following line rises to column 0.
            start, end = first.position(), last.next().position()
        elif first.previous().isValid():
            # Deleting the tail through the last line: also swallow the newline
            # before it so no blank line is left behind.
            prev = first.previous()
            start = prev.position() + len(prev.text())
            end = last.position() + len(last.text())
        else:
            # Deleting every line — the document collapses to one empty block.
            start, end = 0, last.position() + len(last.text())
        c.setPosition(start)
        c.setPosition(end, _MoveMode.KeepAnchor)
        c.removeSelectedText()
        c.movePosition(_MoveOp.StartOfBlock)
        self._editor.setTextCursor(c)

    def _paste(self, *, after: bool, count: int = 1):
        if not self._register:
            return
        c = self._editor.textCursor()
        if self._register_linewise:
            payload = self._register * count           # each copy ends in \n
            c.beginEditBlock()
            if after:
                c.movePosition(_MoveOp.EndOfBlock)
                anchor = c.position()
                c.insertText("\n" + payload.rstrip("\n"))
                c.setPosition(anchor + 1)              # first pasted line
            else:
                c.movePosition(_MoveOp.StartOfBlock)
                anchor = c.position()
                c.insertText(payload)
                c.setPosition(anchor)
            c.movePosition(_MoveOp.StartOfBlock)
            c.endEditBlock()
        else:
            payload = self._register * count
            c.beginEditBlock()
            if after and not c.atBlockEnd():
                c.movePosition(_MoveOp.Right)
            c.insertText(payload)
            c.movePosition(_MoveOp.Left)               # land on last pasted char
            c.endEditBlock()
        self._editor.setTextCursor(c)
