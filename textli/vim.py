"""Vim-style key handler for the zen markdown editor.

Built around vim's own grammar rather than a table of key pairs: a **count**, an
optional **operator** (``d`` / ``c`` / ``y``), and a **motion** or **text
object** that says what the operator acts on. So ``d`` composes with every
motion the handler knows — ``de``, ``d$``, ``dG``, ``d}``, ``dfx``, ``diw`` —
instead of each pair having to be written out, and a motion added once is
immediately available to all three operators and to VISUAL mode.

Where a motion *lands* is pure text logic and lives in :mod:`textli.vimmotion`;
this module is the Qt half — it reads the caret, asks for a position or a span,
and turns the answer into a cursor move or an undoable edit.

``.`` repeats the last change by replaying its keystrokes. A command's keys are
buffered as they arrive and kept if the document's revision moved by the time
the handler is back in NORMAL mode with nothing pending — which is what makes
``cwword<Esc>`` repeatable without the handler having to model what ``c`` did.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent, QTextCursor
from PySide6.QtWidgets import QPlainTextEdit

from textli import vimmotion as vm
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

# The bracket text objects, keyed by every character vim accepts for each pair.
_BRACKETS = {
    "(": ("(", ")"), ")": ("(", ")"), "b": ("(", ")"),
    "[": ("[", "]"), "]": ("[", "]"),
    "{": ("{", "}"), "}": ("{", "}"), "B": ("{", "}"),
    "<": ("<", ">"), ">": ("<", ">"),
}
_QUOTES = ("\"", "'", "`")


@dataclass(frozen=True)
class Motion:
    """Where a motion lands, and how an operator should read the span.

    ``inclusive`` covers the landing character (``e``, ``f``, ``%``);
    ``linewise`` widens the span to whole lines (``j``, ``G``, ``}``… ), which
    is also what makes ``dj`` take two lines rather than a column run.
    """

    pos: int
    linewise: bool = False
    inclusive: bool = False


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
        # Numeric count prefix accumulated before an operator or motion (``3j``,
        # ``2dd``). ``_op_count`` carries the operator's own count across to the
        # motion, so ``2d3w`` deletes six words the way vim multiplies them.
        self._count = ""
        self._op: str | None = None
        self._op_count = 1
        # Multi-key sequences still awaiting their next key.
        self._pending_g = False
        self._pending_find: str | None = None     # "f" / "F" / "t" / "T"
        self._pending_object: str | None = None   # "i" / "a"
        self._pending_replace = False
        self._last_find: tuple[str, str] | None = None   # (cmd, char) for ; and ,
        # Single unnamed register shared by yank, delete and paste. A line-wise
        # yank/delete (``yy``/``dd``) pastes on its own line; a char-wise one
        # pastes inline.
        self._register = ""
        self._register_linewise = False
        # `.` — the keystrokes of the last change, and the buffer collecting the
        # command in flight (see _record_* below).
        self._last_change: list[tuple] = []
        self._buffer: list[tuple] = []
        self._revision = 0
        self._repeatable = True
        self._replaying = False
        # Block cursor everywhere but INSERT (NORMAL and VISUAL show it); the
        # caret only thins out while typing. Callers that open in INSERT (inline
        # editing) pass ``initial_mode``; the zen editor keeps the NORMAL default.
        self._editor.setOverwriteMode(initial_mode != VimMode.INSERT)

    @property
    def mode(self) -> VimMode:
        return self._mode

    @property
    def has_pending(self) -> bool:
        """True while a multi-key sequence awaits its next key, or a count is
        building — the host must not intercept keys that would complete one.
        ``f/`` has to reach the handler rather than opening search, and ``dn``
        must not step to the next search hit."""
        return bool(
            self._count or self._op or self._pending_g or self._pending_find
            or self._pending_object or self._pending_replace)

    def _set_mode(self, mode: VimMode):
        if mode == self._mode:
            return
        self._mode = mode
        self._editor.setOverwriteMode(mode != VimMode.INSERT)
        self._mode_changed(mode)

    # ── Entry point & change recording ──

    def handle_key(self, event: QKeyEvent) -> bool:
        """Process a key event. Returns True if consumed."""
        if self._replaying:
            return self._dispatch(event)
        if not self._in_command():
            # A fresh command starts here: remember where the document stood so
            # its keys are kept for `.` only if they actually changed something.
            self._buffer = []
            self._revision = self._editor.document().revision()
            self._repeatable = True
        self._buffer.append(
            (event.key(), event.text(), event.modifiers()))
        consumed = self._dispatch(event)
        if not self._in_command():
            if (self._repeatable
                    and self._editor.document().revision() != self._revision):
                self._last_change = list(self._buffer)
            self._buffer = []
        return consumed

    def _in_command(self) -> bool:
        """True while a command is still being typed — mid-sequence, mid-count,
        or inside the INSERT/VISUAL leg of one."""
        return self._mode != VimMode.NORMAL or self.has_pending

    def _dispatch(self, event: QKeyEvent) -> bool:
        if self._mode == VimMode.INSERT:
            return self._handle_insert(event)
        if self._mode == VimMode.VISUAL:
            return self._handle_visual(event)
        return self._handle_normal(event)

    def _repeat_last_change(self, count: int):
        """``.`` — replay the last change's keystrokes.

        Replaying rather than re-running a recorded edit is what makes an insert
        leg repeat too (``cwfoo<Esc>`` puts ``foo`` in again). INSERT keys are
        normally passed back to the widget, which isn't listening during a
        replay, so printable text is inserted here instead.
        """
        if not self._last_change:
            return
        self._replaying = True
        try:
            for _ in range(count):
                for key, text, mods in self._last_change:
                    ev = QKeyEvent(QKeyEvent.Type.KeyPress, key, mods, text)
                    if not self._dispatch(ev) and self._mode == VimMode.INSERT \
                            and text and text.isprintable():
                        self._editor.textCursor().insertText(text)
        finally:
            self._replaying = False
            self._set_mode(VimMode.NORMAL)

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
        txt = event.text()
        mods = event.modifiers()
        shift = bool(mods & Qt.KeyboardModifier.ShiftModifier)
        ctrl = bool(mods & _CTRL_MOD)

        # ── Sequences awaiting their next key ──
        if self._pending_replace:
            self._pending_replace = False
            count, self._op_count = self._op_count, 1
            if txt and txt.isprintable():
                self._replace_chars(txt, count)
            return True
        if self._pending_find:
            cmd, self._pending_find = self._pending_find, None
            if txt and txt.isprintable():
                self._last_find = (cmd, txt)
                self._run_find(cmd, txt, self._op_count)
            else:
                self._abort_operator()
            return True
        if self._pending_object:
            kind, self._pending_object = self._pending_object, None
            self._run_object(kind, txt, self._op_count)
            return True
        if self._pending_g:
            self._pending_g = False
            return self._complete_g(event)

        # ── Count prefix ──
        # Digits accumulate (``3``, ``12``). A bare ``0`` is the start-of-line
        # motion; ``0`` is a count digit only once a count is already building.
        if txt.isdigit() and (txt != "0" or self._count):
            self._count += txt
            return True
        has_count = bool(self._count)
        count = self._take_count()
        if self._op:
            # ``2d3w`` — the operator's count multiplies the motion's.
            count *= self._op_count

        # Esc — abandon a pending operator, else save and close.
        if key == Qt.Key.Key_Escape:
            if self._op:
                self._abort_operator()
                return True
            if shift:
                self._close_cancel()
            else:
                self._close_save()
            return True

        # ── Operators ──
        if not ctrl and txt in ("d", "c", "y") and not shift:
            if self._op == txt:
                # dd / cc / yy — the doubled operator is the line-wise form.
                op = self._op
                self._op = None
                self._operate_lines(op, count)
                return True
            if self._op:
                self._abort_operator()
                return True
            self._op = txt
            self._op_count = count
            return True

        # ── Text objects (only meaningful with an operator pending) ──
        if self._op and not ctrl and txt in ("i", "a"):
            self._pending_object = txt
            self._op_count = count
            return True

        # ── Multi-key motions ──
        if not ctrl and txt in ("f", "F", "t", "T"):
            self._pending_find = txt
            self._op_count = count
            return True
        if key == Qt.Key.Key_G and not shift and not ctrl:
            self._pending_g = True
            self._op_count = count
            return True

        # ── Single-key motions ──
        motion = self._motion_for(key, txt, shift, ctrl, count, has_count)
        if motion is not None:
            if self._op:
                op, self._op = self._op, None
                self._apply(op, motion)
            else:
                self._move_to(motion, key, count)
            return True

        # A pending operator only composes with motions and objects; anything
        # else abandons it rather than acting on a span nobody asked for.
        if self._op:
            self._abort_operator()
            return True

        return self._normal_command(event, key, txt, shift, ctrl, count)

    def _motion_for(self, key, txt, shift, ctrl, count,
                    has_count=False) -> Motion | None:
        """Resolve a single-key motion to where it lands, or None if this key
        isn't one. Shared by NORMAL, operator-pending and VISUAL, so a motion
        added here works in all three at once."""
        text = self._editor.toPlainText()
        pos = self._editor.textCursor().position()
        if ctrl:
            return None

        if key == Qt.Key.Key_H and not shift:
            return Motion(max(vm.line_start(text, pos), pos - count))
        if key == Qt.Key.Key_L and not shift:
            return Motion(min(vm.line_end(text, pos), pos + count))
        if key == Qt.Key.Key_J and not shift:
            return Motion(self._line_offset(text, pos, count), linewise=True)
        if key == Qt.Key.Key_K and not shift:
            return Motion(self._line_offset(text, pos, -count), linewise=True)

        # w / b / e and their WORD forms. `cw` is vim's one deliberate
        # irregularity: on a non-blank it behaves like `ce`, so changing a word
        # doesn't swallow the space after it.
        if key == Qt.Key.Key_W:
            if self._op == "c" and pos < len(text) \
                    and vm.char_class(text[pos]) != vm.BLANK:
                return Motion(vm.word_end(text, pos, count, shift),
                              inclusive=True)
            target = vm.word_forward(text, pos, count, shift)
            if self._op:
                # vim's other `w` special case: when the last word moved over
                # ends a line, the operator stops there rather than reaching
                # into the next line — `dw` on a line's last word doesn't join
                # it to the one below.
                seg = text[pos:target]
                nl = seg.find("\n")
                if nl != -1 and not seg[nl:].strip():
                    target = pos + nl
            return Motion(target)
        if key == Qt.Key.Key_B:
            return Motion(vm.word_backward(text, pos, count, shift))
        if key == Qt.Key.Key_E:
            return Motion(vm.word_end(text, pos, count, shift), inclusive=True)

        if key == Qt.Key.Key_0 and not shift:
            return Motion(vm.line_start(text, pos))
        if txt == "^":
            return Motion(vm.first_non_blank(text, pos))
        if txt == "$":
            return Motion(vm.line_end(text, pos))
        if txt == "}":
            # Exclusive, not line-wise: `d}` from the top of a paragraph takes
            # the paragraph and leaves the blank line, which falls out of the
            # exclusive-motion rules applied in _apply.
            return Motion(vm.paragraph_forward(text, pos, count))
        if txt == "{":
            return Motion(vm.paragraph_backward(text, pos, count))
        if txt == "%":
            target = vm.matching_bracket(text, pos)
            return None if target is None else Motion(target, inclusive=True)
        if txt in (";", ","):
            if not self._last_find:
                return None
            cmd, ch = self._last_find
            if txt == ",":
                cmd = {"f": "F", "F": "f", "t": "T", "T": "t"}[cmd]
            return self._find_motion(cmd, ch, count)
        if key == Qt.Key.Key_G and shift:
            # G — the last line, or <count>G — that line. Line-wise, so `dG`
            # takes whole lines.
            target = vm.goto_line(text, count) if has_count \
                else vm.goto_line(text, text.count("\n") + 1)
            return Motion(target, linewise=True)
        return None

    def _line_offset(self, text: str, pos: int, delta: int) -> int:
        """A position on the line ``delta`` lines from ``pos`` (clamped)."""
        return vm.goto_line(text, vm.line_number(text, pos) + delta)

    def _find_motion(self, cmd: str, ch: str, count: int) -> Motion | None:
        target = vm.find_char(
            self._editor.toPlainText(), self._editor.textCursor().position(),
            ch, count, forward=cmd in ("f", "t"), till=cmd in ("t", "T"))
        if target is None:
            return None
        # Forward f/t include the landing character; backward F/T never do.
        return Motion(target, inclusive=cmd in ("f", "t"))

    def _run_find(self, cmd: str, ch: str, count: int):
        motion = self._find_motion(cmd, ch, count)
        if motion is None:
            # A character that isn't on this line is a failed motion: vim moves
            # nothing and drops the operator.
            self._abort_operator()
            return
        if self._op:
            op, self._op = self._op, None
            self._apply(op, motion)
        else:
            self._set_position(motion.pos)

    def _run_object(self, kind: str, ch: str, count: int):
        """``iw`` / ``aw`` / ``i(`` / ``a"`` / ``ip`` … — operate on a span
        around the caret rather than on a run from it."""
        op, self._op = self._op, None
        if not op:
            return
        text = self._editor.toPlainText()
        pos = self._editor.textCursor().position()
        inner = kind == "i"
        span = None
        linewise = False
        if ch in ("w", "W"):
            span = vm.word_object(text, pos, count, inner=inner, big=ch == "W")
        elif ch in _BRACKETS:
            open_, close = _BRACKETS[ch]
            span = vm.bracket_object(text, pos, open_, close, inner=inner)
        elif ch in _QUOTES:
            span = vm.quote_object(text, pos, ch, inner=inner)
        elif ch == "p":
            span = vm.paragraph_object(text, pos, inner=inner)
            linewise = True
        if span is None:
            return
        self._operate_span(op, span[0], span[1], linewise=linewise)

    def _complete_g(self, event: QKeyEvent) -> bool:
        key = event.key()
        count = self._op_count
        self._op_count = 1
        if key == Qt.Key.Key_G:
            # gg → first line, <count>gg → that line. Line-wise, so `dgg` takes
            # whole lines.
            motion = Motion(vm.goto_line(self._editor.toPlainText(), count),
                            linewise=True)
            if self._op:
                op, self._op = self._op, None
                self._apply(op, motion)
            else:
                self._set_position(motion.pos)
            return True
        if key == Qt.Key.Key_E:
            text = self._editor.toPlainText()
            pos = self._editor.textCursor().position()
            # ge — the end of the previous word: step back over this word, then
            # take the end of the one before it.
            target = vm.word_end(text, vm.word_backward(text, pos, count) - 1, 1)
            motion = Motion(max(0, target), inclusive=True)
            if self._op:
                op, self._op = self._op, None
                self._apply(op, motion)
            else:
                self._set_position(motion.pos)
            return True
        if self._op:
            self._abort_operator()
            return True
        if key == Qt.Key.Key_O and self._open_file is not None:
            self._open_file()
            return True
        if key == Qt.Key.Key_H and self._open_headings is not None:
            self._open_headings()
            return True
        return True  # unknown g-sequence, consume

    def _normal_command(self, event, key, txt, shift, ctrl, count) -> bool:
        """Everything that isn't a motion: edits, mode changes, paste, repeat."""
        # x / X — delete forward / backward characters (charwise `dl` / `dh`).
        if key == Qt.Key.Key_X and not shift and not ctrl:
            self._delete_chars(count)
            return True
        if key == Qt.Key.Key_X and shift and not ctrl:
            self._delete_chars_back(count)
            return True

        # D / C / Y / S / s — vim's one-key shorthands for an operator with a
        # motion already attached.
        text = self._editor.toPlainText()
        pos = self._editor.textCursor().position()
        if key == Qt.Key.Key_D and shift and not ctrl:
            self._apply("d", Motion(vm.line_end(text, pos)))
            return True
        if key == Qt.Key.Key_C and shift and not ctrl:
            self._apply("c", Motion(vm.line_end(text, pos)))
            return True
        if key == Qt.Key.Key_Y and shift and not ctrl:
            self._operate_lines("y", count)      # vim's Y is yy
            return True
        if key == Qt.Key.Key_S and shift and not ctrl:
            self._operate_lines("c", count)      # S is cc
            return True
        if key == Qt.Key.Key_S and not shift and not ctrl:
            self._set_register_text(text[pos:min(len(text), pos + count)], False)
            self._remove(pos, min(vm.line_end(text, pos), pos + count))
            self._set_mode(VimMode.INSERT)       # s is cl
            return True

        # r — replace the character(s) under the caret, staying in NORMAL.
        if key == Qt.Key.Key_R and not shift and not ctrl:
            self._pending_replace = True
            self._op_count = count
            return True

        # ~ — toggle the case of the character(s) under the caret.
        if txt == "~":
            self._toggle_case(count)
            return True

        # J — join this line with the next (count lines).
        if key == Qt.Key.Key_J and shift and not ctrl:
            self._join_lines(count)
            return True

        # . — repeat the last change.
        if txt == "." and not ctrl:
            self._repeatable = False   # `.` never becomes the change it repeats
            self._repeat_last_change(count)
            return True

        # p / P — paste after / before, count copies
        if key == Qt.Key.Key_P and not ctrl:
            self._paste(after=not shift, count=count)
            return True

        # v — enter VISUAL, selecting from here as the motions extend
        if key == Qt.Key.Key_V and not shift and not ctrl:
            self._set_mode(VimMode.VISUAL)
            return True

        # u / Ctrl-r — undo / redo, riding the editor's native undo stack
        # (Qt restores the caret to the change site, the way vim leaves you
        # there). So a NORMAL-mode edit is reversible without dropping to
        # INSERT for the platform ⌘Z. Never repeatable: `.` after an undo
        # repeats the change that was undone, not the undo.
        if key == Qt.Key.Key_U and not shift and not ctrl:
            self._repeatable = False
            for _ in range(count):
                self._editor.undo()
            return True
        if key == Qt.Key.Key_R and ctrl:
            self._repeatable = False
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
            self._set_position(vm.first_non_blank(text, pos))
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

    # ── Applying an operator ──

    def _abort_operator(self):
        self._op = None
        self._op_count = 1
        self._pending_object = None
        self._pending_find = None

    def _move_to(self, motion: Motion, key, count: int):
        """Move the caret for a bare motion. j/k go through Qt so the desired
        column survives a short line, the way vim remembers it."""
        if key == Qt.Key.Key_J and not motion.inclusive:
            self._move(_MoveOp.Down, count)
            return
        if key == Qt.Key.Key_K and not motion.inclusive:
            self._move(_MoveOp.Up, count)
            return
        self._set_position(motion.pos)

    def _apply(self, op: str, motion: Motion):
        """Run ``op`` over the span between the caret and where ``motion`` lands.

        Exclusive motions get vim's two adjustments, which are what stop `d}`
        from swallowing the blank line that ended the paragraph: an exclusive
        motion ending in column 0 backs up to the end of the previous line, and
        if it also *started* at or before its line's first non-blank, the whole
        thing becomes line-wise.
        """
        text = self._editor.toPlainText()
        pos = self._editor.textCursor().position()
        start, end = min(pos, motion.pos), max(pos, motion.pos)
        linewise = motion.linewise
        if not linewise:
            if motion.inclusive:
                end = min(len(text), end + 1)
            elif end > start and end > 0 and end == vm.line_start(text, end):
                end -= 1
                if start <= vm.first_non_blank(text, start):
                    linewise = True
        if linewise:
            self._operate_span(
                op, vm.line_start(text, start), vm.line_end(text, end),
                linewise=True)
            return
        self._operate_span(op, start, end, linewise=False)

    def _operate_lines(self, op: str, count: int):
        """``dd`` / ``cc`` / ``yy`` — the line-wise form of each operator."""
        text = self._editor.toPlainText()
        pos = self._editor.textCursor().position()
        start = vm.line_start(text, pos)
        end = vm.line_end(text, self._line_offset(text, pos, count - 1))
        self._operate_span(op, start, end, linewise=True)

    def _operate_span(self, op: str, start: int, end: int, *, linewise: bool):
        text = self._editor.toPlainText()
        start = max(0, min(start, len(text)))
        end = max(start, min(end, len(text)))
        payload = text[start:end]
        if linewise:
            payload += "\n"
        self._set_register_text(payload, linewise)
        if op == "y":
            # Yank leaves the caret at the start of what it took.
            self._set_position(vm.line_start(text, start) if linewise else start)
            return
        if op == "c":
            # Never _remove_lines: a line-wise change empties the line and
            # leaves you on it, so the newline itself has to stay.
            self._remove(start, end)
            self._set_mode(VimMode.INSERT)
            return
        if linewise:
            self._remove_lines(start, end)
        else:
            self._remove(start, end)

    def _remove(self, start: int, end: int):
        c = self._editor.textCursor()
        c.setPosition(start)
        c.setPosition(end, _MoveMode.KeepAnchor)
        c.removeSelectedText()
        self._editor.setTextCursor(c)

    def _remove_lines(self, start: int, end: int):
        """Delete whole lines, taking a newline with them so no blank line is
        left behind: the one after when there are lines below, otherwise the one
        before."""
        text = self._editor.toPlainText()
        if end < len(text):          # a newline follows — take it
            end += 1
        elif start > 0:              # deleting the tail — take the one before
            start -= 1
        self._remove(start, end)
        c = self._editor.textCursor()
        c.movePosition(_MoveOp.StartOfBlock)
        self._editor.setTextCursor(c)

    # ── Visual mode ──

    def _handle_visual(self, event: QKeyEvent) -> bool:
        key = event.key()
        txt = event.text()
        mods = event.modifiers()
        shift = bool(mods & Qt.KeyboardModifier.ShiftModifier)
        ctrl = bool(mods & _CTRL_MOD)

        if self._pending_find:
            cmd, self._pending_find = self._pending_find, None
            if txt and txt.isprintable():
                self._last_find = (cmd, txt)
                motion = self._find_motion(cmd, txt, self._op_count)
                if motion is not None:
                    self._extend_to(motion)
            return True
        if self._pending_object:
            kind, self._pending_object = self._pending_object, None
            self._select_object(kind, txt, self._op_count)
            return True
        if self._pending_g:
            self._pending_g = False
            if key == Qt.Key.Key_G:
                self._extend_to(Motion(
                    vm.goto_line(self._editor.toPlainText(), self._op_count)))
            self._op_count = 1
            return True

        if txt.isdigit() and (txt != "0" or self._count):
            self._count += txt
            return True
        has_count = bool(self._count)
        count = self._take_count()

        # Leave VISUAL — Esc or a second v — clearing the selection.
        if key == Qt.Key.Key_Escape or (
                key == Qt.Key.Key_V and not shift and not ctrl):
            self._clear_visual()
            return True

        # Multi-key motions and text objects extend the selection too.
        if not ctrl and txt in ("f", "F", "t", "T"):
            self._pending_find = txt
            self._op_count = count
            return True
        if not ctrl and txt in ("i", "a"):
            self._pending_object = txt
            self._op_count = count
            return True
        if key == Qt.Key.Key_G and not shift and not ctrl:
            self._pending_g = True
            self._op_count = count
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
        if key == Qt.Key.Key_P and not ctrl:
            self._visual_paste()
            return True

        # ── Everything else that resolves is a motion, extending the anchor ──
        motion = self._motion_for(key, txt, shift, ctrl, count, has_count)
        if motion is not None:
            if key == Qt.Key.Key_J and not shift:
                self._move(_MoveOp.Down, count, keep=True)
            elif key == Qt.Key.Key_K and not shift:
                self._move(_MoveOp.Up, count, keep=True)
            else:
                self._extend_to(motion)
            return True

        return True  # consume anything else while selecting

    def _extend_to(self, motion: Motion):
        c = self._editor.textCursor()
        target = motion.pos + 1 if motion.inclusive else motion.pos
        c.setPosition(max(0, min(target, len(self._editor.toPlainText()))),
                      _MoveMode.KeepAnchor)
        self._editor.setTextCursor(c)

    def _select_object(self, kind: str, ch: str, count: int):
        """``viw`` and friends — the object replaces the selection outright."""
        text = self._editor.toPlainText()
        pos = self._editor.textCursor().position()
        inner = kind == "i"
        span = None
        if ch in ("w", "W"):
            span = vm.word_object(text, pos, count, inner=inner, big=ch == "W")
        elif ch in _BRACKETS:
            open_, close = _BRACKETS[ch]
            span = vm.bracket_object(text, pos, open_, close, inner=inner)
        elif ch in _QUOTES:
            span = vm.quote_object(text, pos, ch, inner=inner)
        elif ch == "p":
            span = vm.paragraph_object(text, pos, inner=inner)
        if span is None:
            return
        c = self._editor.textCursor()
        c.setPosition(span[0])
        c.setPosition(span[1], _MoveMode.KeepAnchor)
        self._editor.setTextCursor(c)

    def _visual_paste(self):
        """``p`` over a selection — the register replaces what was selected.

        A line-wise register (from ``yy``/``dd``) keeps its own lines rather
        than being spliced into the middle of one, so ``vip`` then ``p`` swaps
        one paragraph for another cleanly.
        """
        c = self._editor.textCursor()
        if not c.hasSelection() or not self._register:
            self._set_mode(VimMode.NORMAL)
            return
        payload = self._register
        start = c.selectionStart()
        c.beginEditBlock()
        c.removeSelectedText()
        if self._register_linewise:
            c.insertText(payload.rstrip("\n"))
        else:
            c.insertText(payload)
        c.setPosition(max(start, c.position() - 1))
        c.endEditBlock()
        self._editor.setTextCursor(c)
        self._set_mode(VimMode.NORMAL)

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
            self._set_register_text(
                c.selectedText().replace(_PARA_SEP, "\n"), False)
            c.removeSelectedText()
            self._editor.setTextCursor(c)
        self._set_mode(VimMode.INSERT if to_insert else VimMode.NORMAL)

    def _visual_yank(self):
        """y copies the selection (char-wise) and drops back to NORMAL with the
        caret at the selection start, the way vim leaves it."""
        c = self._editor.textCursor()
        if c.hasSelection():
            self._set_register_text(
                c.selectedText().replace(_PARA_SEP, "\n"), False)
            c.setPosition(c.selectionStart())
            self._editor.setTextCursor(c)
        self._set_mode(VimMode.NORMAL)

    # ── Helpers ──

    def _take_count(self) -> int:
        n = int(self._count) if self._count else 1
        self._count = ""
        return n

    def _set_register_text(self, text: str, linewise: bool):
        self._register = text
        self._register_linewise = linewise

    def _set_position(self, pos: int):
        c = self._editor.textCursor()
        c.setPosition(max(0, min(pos, len(self._editor.toPlainText()))))
        self._editor.setTextCursor(c)

    def _move(self, op: QTextCursor.MoveOperation, count: int = 1,
              *, keep: bool = False):
        mode = _MoveMode.KeepAnchor if keep else _MoveMode.MoveAnchor
        c = self._editor.textCursor()
        for _ in range(count):
            c.movePosition(op, mode)
        self._editor.setTextCursor(c)

    def _delete_chars(self, count: int = 1):
        text = self._editor.toPlainText()
        pos = self._editor.textCursor().position()
        end = min(vm.line_end(text, pos), pos + count)
        if end <= pos:
            return
        self._set_register_text(text[pos:end], False)
        self._remove(pos, end)

    def _delete_chars_back(self, count: int = 1):
        text = self._editor.toPlainText()
        pos = self._editor.textCursor().position()
        start = max(vm.line_start(text, pos), pos - count)
        if start >= pos:
            return
        self._set_register_text(text[start:pos], False)
        self._remove(start, pos)

    def _replace_chars(self, ch: str, count: int = 1):
        """``r`` — overwrite ``count`` characters with ``ch``, staying in NORMAL
        and leaving the caret on the last one."""
        text = self._editor.toPlainText()
        pos = self._editor.textCursor().position()
        end = min(vm.line_end(text, pos), pos + count)
        if end <= pos:
            return
        c = self._editor.textCursor()
        c.setPosition(pos)
        c.setPosition(end, _MoveMode.KeepAnchor)
        c.insertText(ch * (end - pos))
        c.setPosition(end - 1)
        self._editor.setTextCursor(c)

    def _toggle_case(self, count: int = 1):
        text = self._editor.toPlainText()
        pos = self._editor.textCursor().position()
        end = min(vm.line_end(text, pos), pos + count)
        if end <= pos:
            return
        c = self._editor.textCursor()
        c.setPosition(pos)
        c.setPosition(end, _MoveMode.KeepAnchor)
        c.insertText(text[pos:end].swapcase())
        self._editor.setTextCursor(c)

    def _join_lines(self, count: int = 1):
        """``J`` — pull the next line onto this one, collapsing the indent to a
        single space the way vim does. ``3J`` joins three lines."""
        c = self._editor.textCursor()
        c.beginEditBlock()
        for _ in range(max(1, count - 1)):
            text = self._editor.toPlainText()
            pos = c.position()
            end = vm.line_end(text, pos)
            if end >= len(text):
                break
            nxt = end + 1
            while nxt < len(text) and text[nxt] in " \t":
                nxt += 1
            c.setPosition(end)
            c.setPosition(nxt, _MoveMode.KeepAnchor)
            c.insertText(" ")
            c.setPosition(end)
        c.endEditBlock()
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
