import json
import os
from pathlib import Path
import re
import sys
from .core import StudioError, atomic_write, run, settings

TERMINALS = ("ghostty", "kitty", "iterm2", "terminal")
BEGIN = "# BEGIN HERDR FONT STUDIO"
END = "# END HERDR FONT STUDIO"


def detect():
    """Hints only: Herdr server environment may belong to an older client."""
    override = os.environ.get("HERDR_FONT_TERMINAL")
    if override in TERMINALS:
        return override
    value = os.environ.get("TERM_PROGRAM", "").lower()
    known = {"ghostty": "ghostty", "kitty": "kitty", "iterm.app": "iterm2", "apple_terminal": "terminal"}.get(value)
    if known:
        return known
    if os.environ.get("KITTY_WINDOW_ID") or os.environ.get("TERM") == "xterm-kitty":
        return "kitty"
    if os.environ.get("TERM") == "xterm-ghostty":
        return "ghostty"
    return None


def current_terminal(options):
    # A choice saved in Terminal.app must not redirect a later Ghostty launch.
    return detect() or options.get("terminal")


def config_path(terminal, options):
    override = options.get(f"{terminal}_config")
    if override:
        return Path(override).expanduser().resolve()
    xdg = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
    if terminal == "kitty":
        return xdg / "kitty/kitty.conf"
    candidates = [xdg / "ghostty/config"]
    if sys.platform == "darwin":
        candidates.append(Path.home() / "Library/Application Support/com.mitchellh.ghostty/config")
    existing = [p for p in candidates if p.exists()]
    if len(existing) > 1:
        raise StudioError("Multiple Ghostty configs found. Set ghostty_config in plugin config.json.")
    return existing[0] if existing else candidates[0]


def managed_config(text, terminal, font, size, family=None, style=None):
    # Only replace a well-formed, unique managed block.
    if text.count(BEGIN) != text.count(END) or text.count(BEGIN) > 1:
        raise StudioError("Malformed herdr-fonts block; fix it before applying.")
    value = json.dumps(family or font, ensure_ascii=False)
    style_value = json.dumps(style or "Regular", ensure_ascii=False)
    lines = (f"font-family =\nfont-family = {value}\nfont-style = {style_value}\nfont-size = {size:g}" if terminal == "ghostty"
             else f"font_family postscript_name={json.dumps(font, ensure_ascii=False)}\nfont_size {size:g}")
    block = f"{BEGIN}\n{lines}\n{END}\n"
    if BEGIN in text:
        pattern = rf"(?m)^{re.escape(BEGIN)}\n.*?^{re.escape(END)}(?:\n|$)"
        text, count = re.subn(pattern, "", text, flags=re.S)
        if count != 1:
            raise StudioError("Malformed herdr-fonts block.")
    return text + ("\n" if text and not text.endswith("\n") else "") + block


class ConfigAdapter:
    def __init__(self, terminal, path):
        self.terminal = terminal
        # Resolve symlinks rather than silently replacing a user's symlink.
        self.path = Path(path).expanduser().resolve()
        self.scope = f"Persistent config: {self.path} (may affect all terminal windows)"
        self.message = ("Saved. Reload Ghostty: Cmd+Shift+, on macOS / Ctrl+Shift+, on Linux. "
                        "Reset manual zoom if size does not change."
                        if terminal == "ghostty" else
                        "Saved. Reload kitty: Ctrl+Shift+F5 (macOS also Cmd+Ctrl+,).")

    def read(self, change):
        path = Path(change["target"])
        return path.read_bytes().decode("utf-8") if path.exists() else None

    def plan(self, font, size):
        from .fonts import installed
        face = next((f for f in installed() if f.name == font), None)
        if face is None:
            raise StudioError("Selected font is no longer installed.")
        change = {"terminal": self.terminal, "target": str(self.path)}
        before = self.read(change)
        change.update(before=before, after=managed_config(
            before or "", self.terminal, font, size, face.family, face.style))
        return change

    def write(self, change, value):
        path = Path(change["target"])
        if value is None:
            path.unlink(missing_ok=True)
        else:
            mode = path.stat().st_mode & 0o777 if path.exists() else 0o600
            atomic_write(path, value, mode)


TERMINAL_SCRIPT = '''on run argv
    tell application "Terminal"
        if item 1 of argv is "capture" then
            if (count windows) is 0 then error "No Terminal window is open"
            set activeTab to selected tab of front window
            return (name of current settings of activeTab) & linefeed & (font name of activeTab) & linefeed & (font size of activeTab as text) & linefeed & (tty of activeTab)
        end if
        if item 2 of argv is "tty" then
            set activeTab to missing value
            set targetWindow to missing value
            repeat with terminalWindow in windows
                repeat with candidate in tabs of terminalWindow
                    if (tty of candidate) is (item 3 of argv) then
                        set activeTab to contents of candidate
                        set targetWindow to contents of terminalWindow
                        exit repeat
                    end if
                end repeat
                if activeTab is not missing value then exit repeat
            end repeat
            if activeTab is missing value then error "The original Terminal tab is closed"
            if item 1 of argv is "write" then
                -- Terminal normally preserves cell counts and resizes its window.
                -- Preserve the visible window rectangle instead; cell counts may reflow.
                set originalBounds to bounds of targetWindow
                -- Tab setters update the visible surface, not only a saved profile.
                set font name of activeTab to item 4 of argv
                set font size of activeTab to (item 5 of argv as integer)
                if (bounds of targetWindow) is not originalBounds then
                    set bounds of targetWindow to originalBounds
                end if
            end if
            return (font name of activeTab) & linefeed & (font size of activeTab as text)
        end if
        if item 2 of argv is "name" then
            set p to settings set (item 3 of argv)
        else
            -- Legacy journal recovery: enumerate instead of using Terminal's broken whose-id selector.
            set p to missing value
            repeat with candidate in settings sets
                if (id of candidate as text) is (item 3 of argv) then
                    set p to contents of candidate
                    exit repeat
                end if
            end repeat
            if p is missing value then error "The original Terminal profile no longer exists"
        end if
        if item 1 of argv is "write" then
            set font name of p to item 4 of argv
            set font size of p to (item 5 of argv as integer)
        end if
        return (font name of p) & linefeed & (font size of p as text)
    end tell
end run'''


class TerminalAdapter:
    terminal = "terminal"
    message = "Applied to the captured Terminal tab. Window dimensions preserved."

    def __init__(self, target=None):
        if sys.platform != "darwin":
            raise StudioError("macOS Terminal requires macOS.")
        if target is None:
            values = self.script("capture").splitlines()
            if len(values) != 4:
                raise StudioError("Terminal returned an unexpected profile description")
            self.target = {"tty": values[3], "profile_name": values[0]}
            self.scope = f"Current Terminal tab: {values[3]} ({values[0]})"
        else:
            self.target = target
            self.scope = f"Shared Terminal profile: {target.get('profile_name')}" if isinstance(target, dict) else f"Shared Terminal profile id: {target}"

    @staticmethod
    def script(*args):
        return run(["osascript", "-", *args], input=TERMINAL_SCRIPT)

    def read(self, change):
        font, size = self.script("read", *self.address(change["target"])).splitlines()
        return {"font": font, "size": int(size)}

    @staticmethod
    def address(target):
        if isinstance(target, dict):
            if "tty" in target:
                return "tty", target["tty"]
            return "name", target["profile_name"]
        return "id", str(target)

    def plan(self, font, size):
        if size != int(size):
            raise StudioError("macOS Terminal supports whole-point sizes. Choose an integer.")
        change = {"terminal": self.terminal, "target": self.target}
        change.update(before=self.read(change), after={"font": font, "size": int(size)})
        return change

    def write(self, change, value):
        self.script("write", *self.address(change["target"]), value["font"], str(value["size"]))


class ITermAdapter:
    terminal = "iterm2"
    message = "Applied live to the captured iTerm2 session; the shared profile is unchanged."

    def __init__(self, target=None):
        if sys.platform != "darwin":
            raise StudioError("iTerm2 requires macOS.")
        self.target = target or self.call("capture")["target"]
        self.scope = f"Live iTerm2 session: {self.target}"

    @staticmethod
    def call(*args):
        helper = Path(__file__).with_name("iterm_bridge.py")
        return json.loads(run([sys.executable, str(helper), *args]))

    def read(self, change):
        return self.call("read", change["target"])["font"]

    def plan(self, font, size):
        change = {"terminal": self.terminal, "target": self.target}
        change.update(before=self.read(change), after=f"{font} {size:g}")
        return change

    def write(self, change, value):
        self.call("write", change["target"], value)


def create(terminal, options=None):
    if os.environ.get("SSH_CONNECTION") or os.environ.get("SSH_TTY"):
        raise StudioError("herdr-fonts supports local sessions only. Run on the terminal's own computer.")
    if terminal in ("ghostty", "kitty"):
        return ConfigAdapter(terminal, config_path(terminal, options if options is not None else settings()))
    if terminal == "terminal":
        return TerminalAdapter()
    if terminal == "iterm2":
        return ITermAdapter()
    raise StudioError(f"Unsupported terminal: {terminal}")


def adapter_for_change(change):
    terminal = change["terminal"]
    if terminal in ("ghostty", "kitty"):
        return ConfigAdapter(terminal, change["target"])
    if terminal == "terminal":
        return TerminalAdapter(change["target"])
    if terminal == "iterm2":
        return ITermAdapter(change["target"])
    raise StudioError("Unknown terminal in undo history")
