#!/usr/bin/env python3
"""Choose terminal fonts and sizes from Herdr or your shell."""
import argparse
import json
import os
import sys
from pathlib import Path

# Optional dependencies live in durable plugin config, outside managed source checkouts.
_config = Path(os.environ.get("HERDR_PLUGIN_CONFIG_DIR", str(
    Path.home() / ".config/herdr/plugins/config/herdr.fonts")))
_venv = _config / ".venv"
_python = _venv / "bin/python3"
if _python.exists() and Path(sys.prefix) != _venv:
    os.execv(str(_python), [str(_python), str(Path(__file__).resolve()), *sys.argv[1:]])

from fontstudio.adapters import TERMINALS, create, config_path
from fontstudio.core import History, StudioError, run, settings
from fontstudio.fonts import installed


def main():
    parser = argparse.ArgumentParser(prog="herdr-fonts", description=__doc__)
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("open", help="Open the herdr-fonts Herdr popup")
    sub.add_parser("picker", help="Run the interactive terminal UI")
    listing = sub.add_parser("list", help="List installed monospace faces")
    listing.add_argument("--json", action="store_true")
    doctor = sub.add_parser("doctor", help="Show paths and capabilities without changing settings")
    apply = sub.add_parser("apply", help="Apply a font by exact PostScript name")
    apply.add_argument("--terminal", choices=TERMINALS, required=True)
    apply.add_argument("--font", required=True)
    apply.add_argument("--size", type=float, required=True)
    apply.add_argument("--config", help="Override Ghostty/kitty config path")
    apply.add_argument("--dry-run", action="store_true", help="Print a plan without changing settings")
    sub.add_parser("undo", help="Undo the most recent plugin change")
    shortcut = sub.add_parser("setup-shortcut", help="Install prefix+f in Herdr config (preserves a backup)")
    shortcut.add_argument("--config", help="Explicit Herdr config.toml path")
    launcher = sub.add_parser("setup-launcher", help="Install the herdr-fonts terminal command")
    launcher.add_argument("--bin-dir", help="Override the command installation directory")
    args = parser.parse_args()
    if args.command is None:
        args.command = "picker"
    if args.command == "open":
        print(run([os.environ.get("HERDR_BIN_PATH", "herdr"), "plugin", "pane", "open",
                   "--plugin", "herdr.fonts", "--entrypoint", "picker"]))
    elif args.command == "picker":
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            raise StudioError("Open herdr-fonts in a terminal: run herdr-fonts or double-click Herdr Fonts.command.")
        from fontstudio.ui import picker
        picker()
    elif args.command == "list":
        fonts = installed()
        if args.json:
            print(json.dumps([vars(font) for font in fonts], indent=2, ensure_ascii=False))
        else:
            for font in fonts:
                print(f"{font.name}\t{font.label}")
    elif args.command == "doctor":
        options = settings()
        for terminal in ("ghostty", "kitty"):
            try:
                path = config_path(terminal, options)
                print(f"{terminal}: {path} (exists={path.exists()}); config write + manual reload")
            except StudioError as exc:
                print(f"{terminal}: {exc}")
        print("terminal: macOS AppleScript; live font and size on the captured tab")
        print("iterm2: optional iterm2 Python package + enabled Python API; live session")
        print(f"Python: {sys.executable}")
        print(f"Installed monospace faces: {len(installed())}")
        print("Local sessions only. Terminal detection uses environment hints; Ctrl+T overrides it.")
    elif args.command == "apply":
        from fontstudio.core import validate_size
        validate_size(args.size)
        if args.font not in {font.name for font in installed()}:
            raise StudioError("Font is not in the installed monospace list. Use the list command.")
        options = settings()
        if args.config:
            if args.terminal not in ("ghostty", "kitty"):
                raise StudioError("--config applies only to Ghostty and kitty")
            options[f"{args.terminal}_config"] = args.config
        adapter = create(args.terminal, options)
        if args.dry_run:
            print(json.dumps(adapter.plan(args.font, args.size), indent=2, ensure_ascii=False))
        else:
            print(History().apply(adapter, args.font, args.size))
    elif args.command == "undo":
        print(History().undo())
    elif args.command == "setup-shortcut":
        from fontstudio.shortcut import install
        print(install(args.config))
    elif args.command == "setup-launcher":
        from fontstudio.launcher import install
        print(install(args.bin_dir))


if __name__ == "__main__":
    try:
        main()
    except (StudioError, OSError, ValueError) as exc:
        print(f"herdr-fonts: {exc}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(130)
