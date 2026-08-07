#!/usr/bin/env python3
"""Build a thin macOS ``Textli.app`` bundle around the local install.

The bundle carries no interpreter of its own — its launcher simply ``exec``s
the ``textli`` console script from the checkout's virtualenv. That gives textli
a real Cmd+Tab / Dock identity (name + icon) while keeping the editable dev
install live: relaunch and you run whatever code is on disk, exactly as when
starting it from a terminal.

    python packaging/macos/build_app.py            # → dist/Textli.app
    python packaging/macos/build_app.py --install  # also copy to ~/Applications

Rasterization uses PySide6's QtSvg (always present, since textli depends on
PySide6), so the only extra tool is ``iconutil`` — a macOS built-in.
"""

from __future__ import annotations

import argparse
import os
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ICON_SVG = REPO_ROOT / "res" / "app_icon.svg"
VENV_TEXTLI = REPO_ROOT / ".venv" / "bin" / "textli"

BUNDLE_ID = "dev.mistergc.textli"
# textli's CLI requires a file argument, but a Dock/Spotlight launch passes
# none — so the launcher falls back to this scratch pad, opened (and created on
# first save) in the home dir, whenever the app is clicked with no file.
SCRATCH_DEFAULT = "$HOME/textli-scratch.md"
# The iconset sizes Apple expects, as (base, scale) → pixel dimension.
ICON_VARIANTS = [
    (16, 1), (16, 2), (32, 1), (32, 2), (128, 1),
    (128, 2), (256, 1), (256, 2), (512, 1), (512, 2),
]


def _textli_version() -> str:
    """Best-effort package version for the Info.plist (falls back to 0.0.0)."""
    try:
        sys.path.insert(0, str(REPO_ROOT))
        from textli import __version__
        return __version__
    except Exception:
        return "0.0.0"


def _render_png(svg: Path, out: Path, px: int) -> None:
    """Rasterize ``svg`` into a ``px``×``px`` transparent square, aspect-fit."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import QGuiApplication, QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer

    QGuiApplication.instance() or QGuiApplication([])
    renderer = QSvgRenderer(str(svg))
    img = QImage(px, px, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    painter = QPainter(img)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    ds = renderer.defaultSize()
    aspect = (ds.width() / ds.height()) if ds.height() else 1.0
    if aspect >= 1.0:
        w, h = px, px / aspect
    else:
        w, h = px * aspect, px
    renderer.render(painter, QRectF((px - w) / 2, (px - h) / 2, w, h))
    painter.end()
    if not img.save(str(out), "PNG"):
        raise RuntimeError(f"failed to write {out}")


def build_icns(svg: Path, dest: Path) -> None:
    """Render every iconset variant and fold them into ``dest`` via iconutil."""
    iconset = dest.parent / "Textli.iconset"
    if iconset.exists():
        shutil.rmtree(iconset)
    iconset.mkdir(parents=True)
    for base, scale in ICON_VARIANTS:
        px = base * scale
        suffix = "" if scale == 1 else "@2x"
        _render_png(svg, iconset / f"icon_{base}x{base}{suffix}.png", px)
    subprocess.run(
        ["iconutil", "-c", "icns", str(iconset), "-o", str(dest)],
        check=True,
    )
    shutil.rmtree(iconset)


def build_app(dest_dir: Path) -> Path:
    """Assemble ``Textli.app`` under ``dest_dir`` and return its path."""
    app = dest_dir / "Textli.app"
    if app.exists():
        shutil.rmtree(app)
    macos = app / "Contents" / "MacOS"
    resources = app / "Contents" / "Resources"
    macos.mkdir(parents=True)
    resources.mkdir(parents=True)

    build_icns(ICON_SVG, resources / "Textli.icns")

    version = _textli_version()
    info = {
        "CFBundleName": "Textli",
        "CFBundleDisplayName": "Textli",
        "CFBundleIdentifier": BUNDLE_ID,
        "CFBundleExecutable": "Textli",
        "CFBundleIconFile": "Textli",
        "CFBundlePackageType": "APPL",
        "CFBundleShortVersionString": version,
        "CFBundleVersion": version,
        "LSMinimumSystemVersion": "11.0",
        "NSHighResolutionCapable": True,
        # A GUI app, not a background agent — show in Dock and Cmd+Tab.
        "LSUIElement": False,
    }
    with (app / "Contents" / "Info.plist").open("wb") as fh:
        plistlib.dump(info, fh)

    # The launcher execs the venv's textli. An app started from Finder inherits
    # a bare PATH, so prepend the usual tool locations for git/editor lookups.
    # With no file argument (a bare Dock/Spotlight click) fall back to the
    # scratch pad, so textli's required positional never aborts the launch.
    launcher = macos / "Textli"
    launcher.write_text(
        "#!/bin/sh\n"
        'export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:'
        '/usr/sbin:/sbin:$PATH"\n'
        f'exec "{VENV_TEXTLI}" "${{@:-{SCRATCH_DEFAULT}}}"\n'
    )
    launcher.chmod(0o755)
    return app


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the macOS Textli.app wrapper.")
    parser.add_argument(
        "--install", action="store_true",
        help="Also copy the bundle to ~/Applications (Spotlight-indexed).",
    )
    parser.add_argument(
        "--dest", type=Path, default=REPO_ROOT / "dist",
        help="Output directory for the bundle (default: dist/).",
    )
    args = parser.parse_args()

    if not ICON_SVG.exists():
        print(f"error: icon not found at {ICON_SVG}", file=sys.stderr)
        return 1
    if not VENV_TEXTLI.exists():
        print(f"error: venv launcher not found at {VENV_TEXTLI}\n"
              "       run `uv sync` / install textli into .venv first.",
              file=sys.stderr)
        return 1

    args.dest.mkdir(parents=True, exist_ok=True)
    app = build_app(args.dest)
    print(f"built {app}")

    if args.install:
        target = Path.home() / "Applications" / "Textli.app"
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(app, target)
        # Nudge Launch Services so the new icon/name are picked up promptly.
        subprocess.run(["touch", str(target)], check=False)
        print(f"installed {target}")
    else:
        print("tip: pass --install to copy it to ~/Applications, or drag it "
              "from dist/ into /Applications yourself.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
