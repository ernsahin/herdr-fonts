"""One-time, conflict-aware installation of the Herdr herdr-fonts shortcut."""
import os
from pathlib import Path
import re
from .core import StudioError, atomic_write

BLOCK = '''# herdr-fonts: open again with your Herdr prefix, then f.
[[keys.command]]
key = "prefix+f"
type = "plugin_action"
command = "herdr.fonts.open"
description = "herdr-fonts: choose font and size"
'''


def install(path=None):
    if path is None:
        path = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "herdr/config.toml"
    path = Path(path).expanduser().resolve()
    original = path.read_bytes().decode("utf-8") if path.exists() else ""
    # Inspect complete keybinding tables, ignoring commented-out examples.
    active = "\n".join(row for row in original.splitlines() if not row.lstrip().startswith("#"))
    tables = re.split(r"(?m)^\s*\[\[keys\.command\]\]\s*$", active)[1:]
    for table in tables:
        table = re.split(r"(?m)^\s*\[", table, maxsplit=1)[0]
        if re.search(r'''(?m)^\s*command\s*=\s*["']herdr\.fonts\.open["']''', table):
            match = re.search(r'''(?m)^\s*key\s*=\s*["']([^"']+)["']''', table)
            return f"herdr-fonts shortcut already configured: {match.group(1) if match else 'see config'}."
    if re.search(r'''(?m)^\s*[^#\n]*=[^\n]*["']prefix\+f["']''', active):
        raise StudioError("prefix+f is already assigned. Choose another binding in Herdr config.toml.")
    backup = path.with_name(path.name + ".font-studio.bak")
    if path.exists():
        if backup.exists():
            raise StudioError(f"Backup already exists: {backup}. Inspect it before installing again.")
        atomic_write(backup, original)
    updated = original + ("\n" if original and not original.endswith("\n") else "") + "\n" + BLOCK
    atomic_write(path, updated, path.stat().st_mode & 0o777 if path.exists() else 0o600)
    return "Installed prefix+f. In Herdr press prefix+Shift+R to reload, then prefix+f to open herdr-fonts."
