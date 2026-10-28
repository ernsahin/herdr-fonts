import contextlib
import fcntl
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile


class StudioError(Exception):
    pass


def run(argv, **kwargs):
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=20, **kwargs)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise StudioError(str(exc)) from exc
    if result.returncode:
        raise StudioError(result.stderr.strip() or result.stdout.strip() or "Command failed")
    return result.stdout.strip()


def atomic_write(path, data, mode=0o600):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=".font-studio-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(name, mode)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def state_dir():
    return Path(os.environ.get("HERDR_PLUGIN_STATE_DIR", str(
        Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state")))
        / "herdr/plugins/herdr.fonts")))


def config_dir():
    return Path(os.environ.get("HERDR_PLUGIN_CONFIG_DIR", str(
        Path.home() / ".config/herdr/plugins/config/herdr.fonts")))


def settings():
    path = config_dir() / "config.json"
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text())
        if not isinstance(value, dict):
            raise ValueError("expected JSON object")
        return value
    except (ValueError, OSError) as exc:
        raise StudioError(f"Invalid {path}: {exc}") from exc


def save_settings(values):
    current = settings()
    current.update(values)
    atomic_write(config_dir() / "config.json", json.dumps(current, indent=2))


def validate_size(value):
    try:
        size = float(value)
    except (TypeError, ValueError):
        raise StudioError("Size must be a number between 6 and 72 pt")
    if not math.isfinite(size) or not 6 <= size <= 72:
        raise StudioError("Size must be between 6 and 72 pt")
    return size


def validate_font(value):
    if not value or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise StudioError("Invalid font name")
    return value


class History:
    """Write-ahead undo journal, shared by popup and CLI processes."""
    def __init__(self, root=None):
        self.root = Path(root) if root else state_dir()
        self.path = self.root / "history.json"

    @contextlib.contextmanager
    def locked(self):
        self.root.mkdir(parents=True, exist_ok=True)
        with (self.root / "history.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def read(self):
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text())
            if not isinstance(data, list):
                raise ValueError("expected a list")
            return data
        except (OSError, ValueError) as exc:
            raise StudioError(f"Cannot read undo history: {exc}") from exc

    def save(self, entries):
        atomic_write(self.path, json.dumps(entries, indent=2))

    def apply(self, adapter, font, size):
        validate_font(font)
        size = validate_size(size)
        with self.locked():
            entries = self.read()
            if entries and entries[-1].get("pending"):
                raise StudioError("An interrupted change needs recovery. Run undo first.")
            change = adapter.plan(font, size)
            if change["before"] == change["after"]:
                return "Font settings already match."
            change["pending"] = True
            entries.append(change)
            self.save(entries)
            # Keep the journal even if mutation fails: undo can recover partial changes.
            adapter.write(change, change["after"])
            if adapter.read(change) != change["after"]:
                raise StudioError("The terminal did not confirm the selected font settings. "
                                  "Run undo to recover before trying again.")
            change["pending"] = False
            self.save(entries)
            return adapter.message

    def undo(self):
        from .adapters import adapter_for_change
        with self.locked():
            entries = self.read()
            if not entries:
                raise StudioError("No font change to undo.")
            change = entries[-1]
            adapter = adapter_for_change(change)
            current = adapter.read(change)
            partial = (change.get("pending") and isinstance(current, dict)
                       and all(current.get(k) in (change["before"].get(k), change["after"].get(k))
                               for k in current))
            if current not in (change["before"], change["after"]) and not partial:
                raise StudioError("Settings changed outside herdr-fonts. Undo stopped to preserve them. "
                                  f"Backup: {self.path}")
            if current != change["before"]:
                adapter.write(change, change["before"])
            entries.pop()
            self.save(entries)
            return "Previous font settings restored. " + adapter.message
