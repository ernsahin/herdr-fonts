import shlex
from pathlib import Path
from .core import StudioError, atomic_write

MARKER = "# Herdr Font Studio launcher"


def install(bin_dir=None):
    path = Path(bin_dir).expanduser() if bin_dir else Path.home() / ".local/bin"
    path = path / "herdr-fonts"
    if path.exists() and MARKER not in path.read_text():
        raise StudioError(f"Refusing to replace an unrelated command: {path}")
    entrypoint = Path(__file__).resolve().parents[1] / "herdr_fonts.py"
    content = f'#!/bin/sh\n{MARKER}\nexec python3 {shlex.quote(str(entrypoint))} "$@"\n'
    atomic_write(path, content, 0o755)
    return f"Installed {path}. Run herdr-fonts to open in your current terminal (no Herdr shortcut required)."
