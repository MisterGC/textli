# macOS app bundle

`build_app.py` produces a thin `Textli.app` — a bundle that gives textli a real
macOS identity (Dock icon, Cmd+Tab name, Spotlight entry) without shipping its
own Python.

```bash
python packaging/macos/build_app.py            # → dist/Textli.app
python packaging/macos/build_app.py --install  # also copy to ~/Applications
```

## How it works

The bundle's launcher (`Contents/MacOS/Textli`) is a three-line shell script
that `exec`s the `textli` console script from the checkout's `.venv`. Because it
runs your editable install in place, there is nothing to rebuild when the code
changes — relaunch and you get the current code, exactly like starting it from a
terminal. The wrapper only needs regenerating if the checkout moves (the venv
path is baked in) or the icon changes.

The icon comes from `res/app_icon.svg`, rasterized with PySide6's QtSvg (always
present, since textli depends on PySide6) into a full `.iconset` and folded into
`Textli.icns` by the macOS built-in `iconutil`.

textli's CLI requires a file argument, but a Dock/Spotlight click passes none.
So the launcher falls back to a scratch pad — `~/textli-scratch.md`, created on
first save — whenever the app is opened with no file. Clicking the icon always
lands you somewhere writable.

## Notes

- The app carries no interpreter of its own, so it is **not** distributable to
  machines without a textli checkout.
- Double-clicking a `.md` file does not open it in this wrapper — file-association
  handoff needs a `QFileOpenEvent` handler in the app, a separate small change.
- The build output lives under `dist/` (git-ignored).
