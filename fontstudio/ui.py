import curses
import textwrap
import sys
from .adapters import TERMINALS, create, current_terminal
from .core import History, StudioError, settings, save_settings, validate_size, atomic_write, state_dir
from .fonts import installed

NAMES = {"ghostty": "Ghostty", "kitty": "kitty", "iterm2": "iTerm2", "terminal": "macOS Terminal"}
SCOPE = {
    "ghostty": "Persistent config / reload required / may affect all Ghostty windows",
    "kitty": "Persistent config / reload required / may affect all kitty windows",
    "iterm2": "Live session / captures the currently selected iTerm2 session on Apply",
    "terminal": "Live change to the current Terminal tab / no reload needed",
}


def control_label(platform=None):
    return "Control" if (platform or sys.platform) == "darwin" else "Ctrl"


def picker():
    fonts = installed()
    options = settings()
    selected_terminal = current_terminal(options)
    if selected_terminal is not None and selected_terminal not in TERMINALS:
        raise StudioError("config.json: terminal must be ghostty, kitty, iterm2, or terminal")
    initial_size = validate_size(options.get("size", 14))
    curses.wrapper(lambda screen: draw(screen, fonts, selected_terminal, initial_size, options))


def draw(screen, fonts, terminal, size, options):
    root = screen
    control = control_label()
    curses.raw()  # Receive Ctrl+S/Ctrl+U instead of terminal flow control/line editing.
    try:
        curses.curs_set(0)
    except curses.error:
        pass  # Some terminal descriptions cannot hide the cursor.
    if curses.has_colors():
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_CYAN, -1)
    accent = curses.color_pair(1) if curses.has_colors() else curses.A_BOLD
    screen.keypad(True)
    query, scroll = "", 0
    index = next((i for i, f in enumerate(fonts) if f.name == options.get("font")), 0)
    message = ("Select a font, adjust the size, then press Enter to apply." if terminal else
               f"Terminal not detected. Press {control}+T to choose it.")
    history = History()

    def line(y, text, attr=0, x=2, limit=None):
        height, width = screen.getmaxyx()
        if 0 <= y < height and width > x + 1:
            try:
                screen.addnstr(y, x, text, min(width - x - 1, limit or width), attr)
            except curses.error:
                pass

    def show_error(exc):
        detail = str(exc)
        try:
            atomic_write(state_dir() / "last-error.txt", detail)
        except OSError:
            pass
        screen.erase()
        line(1, "Font change could not be completed", curses.A_BOLD)
        height, width = screen.getmaxyx()
        for row, text in enumerate(textwrap.wrap(detail, max(20, width - 5))[:max(1, height - 6)]):
            line(3 + row, text)
        line(height - 2, "Enter: return to fonts", accent)
        screen.refresh()
        while screen.get_wch() not in ("\n", "\r", curses.KEY_ENTER, "\x1b"):
            pass

    def size_input():
        value = ""
        while True:
            row = screen.getmaxyx()[0] - 2
            screen.move(row, 0)
            screen.clrtoeol()
            line(row, f"Size (6-72 pt): {value}_   Enter save / Esc cancel", curses.A_BOLD)
            screen.refresh()
            key = screen.get_wch()
            if key == "\x1b":
                return None
            if key in ("\n", "\r", curses.KEY_ENTER):
                return validate_size(value)
            if key in (curses.KEY_BACKSPACE, "\x7f", "\b"):
                value = value[:-1]
            elif isinstance(key, str) and key in "0123456789." and len(value) < 8:
                value += key

    def terminal_input():
        choices = list(TERMINALS)
        selected = choices.index(terminal) if terminal in choices else 0
        while True:
            screen.erase()
            line(1, "Choose your terminal", accent | curses.A_BOLD)
            line(3, "Use this only if automatic detection is missing or incorrect.")
            for row, name in enumerate(choices):
                line(5 + row, ("> " if row == selected else "  ") + NAMES[name],
                     curses.A_REVERSE if row == selected else 0)
            line(11, "Arrows select | Enter confirm | Esc cancel", curses.A_DIM)
            screen.refresh()
            key = screen.get_wch()
            if key == "\x1b":
                return terminal
            if key in ("\n", "\r", curses.KEY_ENTER):
                save_settings({"terminal": choices[selected]})
                return choices[selected]
            if key == curses.KEY_UP:
                selected = (selected - 1) % len(choices)
            elif key in (curses.KEY_DOWN, "\t"):
                selected = (selected + 1) % len(choices)

    while True:
        # Keep the picker readable instead of stretching across a large terminal.
        root.erase()
        root_height, root_width = root.getmaxyx()
        panel_height, panel_width = min(root_height, 30), min(root_width, 110)
        root.noutrefresh()
        screen = root.derwin(panel_height, panel_width,
                             (root_height - panel_height) // 2, (root_width - panel_width) // 2)
        screen.keypad(True)
        screen.erase()
        height, width = screen.getmaxyx()
        if height < 16 or width < 65:
            line(0, "herdr-fonts needs at least 65 columns x 16 rows.")
            line(1, "Resize the terminal, or press Esc to close.")
            screen.refresh()
            if screen.getch() == 27:
                return
            continue
        filtered = [f for f in fonts if query.casefold() in f.label.casefold() or query.casefold() in f.name.casefold()]
        index = min(index, max(0, len(filtered) - 1))
        compact = height < 24
        split = width >= 96 and not compact
        list_width = 43 if split else width - 5
        visible = height - (13 if compact else 18)
        scroll = max(0, min(scroll, index, max(0, len(filtered) - visible)))
        if index >= scroll + visible:
            scroll = index - visible + 1
        line(0 if compact else 1, "HERDR FONTS", accent | curses.A_BOLD)
        if not compact:
            line(2, "Installed monospace fonts  /  Herdr", curses.A_DIM)
        line(2 if compact else 4, f"{NAMES.get(terminal, 'Terminal not detected')}  /  {control}+T to change", accent)
        line(3 if compact else 5, SCOPE.get(terminal, "Select your terminal before applying a font."), curses.A_DIM)
        line(5 if compact else 7, f"Search: {query or '(type to filter)'}")
        line(6 if compact else 8, f"Size: {size:g} pt   [- / +]   Enter to apply   {control}+S: edit", accent)
        for offset, font in enumerate(filtered[scroll:scroll + visible]):
            selected = scroll + offset == index
            label = (("> " if selected else "  ") + font.label)[:list_width].ljust(list_width)
            line((8 if compact else 10) + offset, label,
                 (curses.A_REVERSE | curses.A_BOLD) if selected else 0, limit=list_width)
        base = height - (5 if compact else 8)
        font = filtered[index] if filtered else None
        if split and font:
            line(10, "SELECTED FONT", accent, x=49)
            line(11, font.family, curses.A_BOLD, x=49)
            line(12, font.style, x=49)
            line(13, font.name, curses.A_DIM, x=49)
            line(15, f"Size: {size:g} pt", accent | curses.A_BOLD, x=49)
            if base > 17:
                line(16, "Left / Right: decrease / increase", x=49)
                line(17, f"{control}+S: enter an exact size", x=49)
            if base > 20:
                line(19, "Enter: apply font AND size", curses.A_BOLD, x=49)
                line(20, "Highlighting alone changes nothing.", curses.A_DIM, x=49)
        line(base, "Selected: " + (font.name if font else "No matching font"), accent)
        if compact:
            line(base + 1, "Current font sample: Aa Bb 0O 1Il {} [] =>", curses.A_DIM)
        else:
            line(base + 1, "Sample uses the current font. Enter applies the highlighted selection.", curses.A_DIM)
            line(base + 2, "const greet = (name) => `Hello, ${name}`;   0O 1Il {} [] != =>")
            line(base + 3, "The quick brown fox jumps over the lazy dog. 0123456789")
        # Wrap messages so reload instructions stay visible even in smaller popups.
        for row, text in enumerate(textwrap.wrap(message, width - 5)[:2]):
            line(height - (3 if compact else 4) + row, text, accent)
        line(height - 1, f"Enter apply | {control}+U undo | Left/Right size | Esc close", curses.A_DIM)
        screen.refresh()
        key = screen.get_wch()
        if key == "\x1b":
            return
        if key == curses.KEY_RESIZE:
            continue
        if key == "\x14":
            terminal = terminal_input()
            message = SCOPE.get(terminal, "Select your terminal before applying a font.")
        elif key == curses.KEY_UP:
            index = max(0, index - 1)
        elif key == curses.KEY_DOWN:
            index = min(len(filtered) - 1, index + 1)
        elif key == curses.KEY_NPAGE:
            index = min(len(filtered) - 1, index + visible)
        elif key == curses.KEY_PPAGE:
            index = max(0, index - visible)
        elif key in ("+", "=", curses.KEY_RIGHT):
            size = min(72, size + 1)
            message = f"Size set to {size:g} pt — not applied yet. Press Enter to apply."
        elif key in ("-", curses.KEY_LEFT):
            size = max(6, size - 1)
            message = f"Size set to {size:g} pt — not applied yet. Press Enter to apply."
        elif key == "\x13":
            try:
                value = size_input()
                if value is not None:
                    size = value
                    message = f"Size set to {size:g} pt — not applied yet. Press Enter to apply."
            except StudioError as exc:
                message = str(exc)
        elif key == "\x15":
            try:
                message = history.undo()
            except (StudioError, OSError, ValueError) as exc:
                message = str(exc)
                show_error(exc)
        elif key in ("\n", "\r", curses.KEY_ENTER) and font:
            try:
                if terminal is None:
                    terminal = terminal_input()
                    message = "Terminal selected. Press Enter to apply." if terminal else "No changes applied."
                    continue
                adapter = create(terminal, options)
                # Capture once, then use the frozen target even if focus changes.
                for row in range(height - 5, height - 1):
                    screen.move(row, 0)
                    screen.clrtoeol()
                for row, text in enumerate(textwrap.wrap(adapter.scope, width - 5)[:3]):
                    line(height - 5 + row, text, accent)
                line(height - 2, f"Applying {font.name} at {size:g} pt...", curses.A_BOLD)
                screen.refresh()
                message = history.apply(adapter, font.name, size)
                if terminal in ("terminal", "iterm2"):
                    message = f"Applied: {font.family} / {font.style}, {size:g} pt. {control}+U to undo."
                try:
                    save_settings({"font": font.name, "size": size})
                except OSError:
                    message += " Could not save picker preferences."
            except (StudioError, OSError, ValueError) as exc:
                message = str(exc)
                show_error(exc)
        elif key in (curses.KEY_BACKSPACE, "\x7f", "\b"):
            query, index, scroll = query[:-1], 0, 0
        elif isinstance(key, str) and key.isprintable():
            query += key
            index, scroll = 0, 0
