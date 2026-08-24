"""textli — standalone launcher for the Zen markdown editor.

Opens the focused markdown editor on any file: a full-window host widget
supplies the dark backdrop and owns the window lifecycle, the editor does
the rest.
"""

from __future__ import annotations

import argparse
import signal
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QKeySequence, QPalette, QShortcut
from PySide6.QtWidgets import QApplication, QWidget

from textli import settings as md_settings
from textli import theme
from textli.fonts import register_bundled_fonts
from textli.editor import ZenMarkdownEditor


def split_location(file_arg: str) -> tuple[str, str]:
    """Split an ``open`` argument into ``(path, anchor)``. A ``#heading-slug``
    fragment selects a heading to scroll to (markdown-link style); anchors are
    ``[a-z0-9-]`` slugs, so the first ``#`` starts the fragment."""
    path, _, anchor = file_arg.partition("#")
    return path, anchor


class TextliHost(QWidget):
    """Full-window host for the zen editor in standalone mode.

    The editor parents into this widget and paints its translucent dim wash
    over it, so the host just supplies a solid dark backdrop and owns the
    window lifecycle (closing the editor quits the app).
    """

    def __init__(self):
        super().__init__()
        # Solid dark backdrop — the editor's dim wash composites over it
        # cleanly (no host canvas behind it as there is when embedded).
        self.setAutoFillBackground(True)
        self._apply_backdrop()
        theme.changed.connect(self._apply_backdrop)
        self._editor: ZenMarkdownEditor | None = None

    def _apply_backdrop(self):
        pal = self.palette()
        pal.setColor(QPalette.ColorRole.Window, theme.ZEN_BACKDROP)
        self.setPalette(pal)

    def open(
        self,
        path: Path,
        text: str,
        anchor: str = "",
        read: bool = True,
        stored_view_wins: bool | None = None,
    ) -> None:
        """Create the editor on the given file. Call after the host is shown
        so the editor sizes to a real window rect. ``anchor`` scrolls to a
        heading (its markdown slug); ``read`` opens the rendered read view.
        ``stored_view_wins`` makes ``read`` a fallback the file's remembered
        view may override, which is what the CLI passes when neither ``-r``
        nor ``-w`` was given (#58)."""
        self.setWindowTitle(f"textli — {path.name}")
        self._install_quit_shortcut()
        self._editor = ZenMarkdownEditor(
            parent=self, text=text, title=path.name, file_path=path,
            anchor=anchor, start_in_read=read,
            stored_view_wins=stored_view_wins,
            # Standalone, Esc is not an exit — the reader is at a document,
            # not in a modal editor a host is waiting on (#63).
            close_on_escape=False,
        )
        # File-backed editing autosaves, so closing simply ends the session.
        self._editor.cancelled.connect(self.close)
        self._editor.finished.connect(lambda *_: self.close())
        # `go` switches files in place — keep the window title honest.
        self._editor.file_opened.connect(
            lambda p: self.setWindowTitle(f"textli — {p.name}"))
        self._restore_fullscreen()

    def _restore_fullscreen(self):
        """Come back fullscreen if that's how the last session was left (#65).

        The preference is applied *here*, in the standalone host, rather than in
        the editor: an embedded editor that fullscreened its host's window on
        construction would be taking over an application it's only a widget in.
        Only ever entered from here — leaving fullscreen stays the window's own
        business, so a session started in a normal window is left alone.

        Guarded on visibility because ``--pdf`` opens the editor on a host it
        never shows: ``showFullScreen`` would put that headless export on
        screen.
        """
        if not self.isVisible():
            return
        if md_settings.app_settings().value(
                "zen_md/fullscreen", False, type=bool):
            self.showFullScreen()

    def _install_quit_shortcut(self):
        """``⌘Q`` / ``Ctrl+Q`` quits (#63).

        Explicit because ``Esc`` used to be the only keyboard exit: macOS
        hands Qt applications a ``⌘Q`` through the default application menu,
        but on Linux and Windows the window's close button would otherwise be
        the only way out.
        """
        for seq in (QKeySequence.StandardKey.Quit, QKeySequence("Ctrl+Q")):
            short = QShortcut(QKeySequence(seq), self)
            short.setContext(Qt.ShortcutContext.ApplicationShortcut)
            short.activated.connect(self.close)

    def closeEvent(self, event):
        super().closeEvent(event)
        QApplication.quit()


def main():
    # `textli skill …` is a pure-CLI path (print / install / check /
    # uninstall the bundled AI skill) — dispatch before any Qt setup.
    if len(sys.argv) > 1 and sys.argv[1] == "skill":
        from textli.skill_cli import run
        sys.exit(run(sys.argv[2:]))

    parser = argparse.ArgumentParser(
        prog="textli",
        description="Standalone Zen markdown editor.",
    )
    parser.add_argument(
        "file",
        help="Markdown file to open, optionally with a #heading-slug location "
             "(e.g. notes.md#design-decisions). Created on first save if it "
             "doesn't exist. Or: `textli skill` to print/install the bundled "
             "AI skill (see `textli skill --help`).",
    )
    view = parser.add_mutually_exclusive_group()
    view.add_argument(
        "-r", "--read",
        action="store_true",
        help="Open in the rendered read view, ignoring the file's remembered "
             "view (reading is the default for a file with none)",
    )
    view.add_argument(
        "-w", "--write",
        action="store_true",
        help="Open in the editable write view, ignoring the file's remembered "
             "view",
    )
    parser.add_argument(
        "--pdf",
        nargs="?", const="", metavar="PATH",
        help="Write the typeset page to PATH as a PDF and exit, without "
             "opening a window (default: the source name with a .pdf suffix)",
    )
    args = parser.parse_args()

    file_arg, anchor = split_location(args.file)
    path = Path(file_arg).expanduser()
    if path.is_dir():
        parser.error(f"{path} is a directory")
    if not path.exists() and not path.parent.exists():
        parser.error(f"directory does not exist: {path.parent}")
    text = path.read_text(encoding="utf-8") if path.exists() else ""

    app = QApplication(sys.argv)
    app.setApplicationName("textli")
    register_bundled_fonts()
    # The standalone app restores its own palette preference. An embedding
    # host doesn't come through here — it drives the theme via the API — so
    # this can never override a host's choice.
    theme.set_theme(
        md_settings.app_settings().value("zen_md/theme", "light", type=str))

    if args.pdf is not None:
        if not path.exists():
            parser.error(f"nothing to export: {path} does not exist")
        out = Path(args.pdf).expanduser() if args.pdf \
            else path.with_suffix(".pdf")
        if out.parent != Path("") and not out.parent.exists():
            parser.error(f"directory does not exist: {out.parent}")
        # A hidden host: the editor needs a real widget to lay the page out,
        # but the export never shows one, so this works headless.
        host = TextliHost()
        host.resize(1000, 1400)
        host.open(path, text, read=True)
        host._editor.export_pdf(out)
        print(f"wrote {out}")
        sys.exit(0)

    # Let Ctrl+C quit cleanly (a periodic no-op tick lets the signal land).
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    tick = QTimer()
    tick.start(200)
    tick.timeout.connect(lambda: None)

    host = TextliHost()
    host.showMaximized()
    # No flag: open reading, but let a file that was left writing come back
    # writing. Either flag is a demand and the remembered view steps aside.
    host.open(path, text, anchor=anchor,
              read=not args.write,
              # Either flag is a demand; with neither, reading is only the
              # fallback and a file left writing comes back writing.
              stored_view_wins=not (args.read or args.write))

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
