# herdr-fonts

Pick a monospace font, adjust its size, and undo changes without leaving [Herdr](https://herdr.dev).

Requires **Herdr 0.9.5+** and **Python 3.9+**. Experimental; macOS and Linux. Windows is not supported yet.

## Install

```sh
herdr plugin install ernsahin/herdr-fonts
```

This uses [Herdr's plugin installer](https://herdr.dev/docs/plugins/). No build step or mandatory Python packages. Linux needs Fontconfig (`fc-list`); iTerm2 needs the [optional Python API setup](docs/setup.md).

## Open

With Herdr open, run this in one of its shell panes:

```sh
herdr plugin action invoke herdr.fonts.open
```

The picker opens as a popup in Herdr. Use the same command to reopen it after closing.

For a keyboard shortcut, add this to `~/.config/herdr/config.toml`:

```toml
[[keys.command]]
key = "prefix+f"
type = "plugin_action"
command = "herdr.fonts.open"
description = "Choose font and size"
```

Reload Herdr's config with **Control+B**, release, then **Shift+R**. Open the picker with **Control+B**, release, then **f**. These use Herdr's default prefix; use your own prefix if you changed it. Control is not Command on macOS.

## Use

- Type to search; **↑ / ↓** to select a font.
- **← / →** or **+ / −** to choose a size.
- **Enter** to apply both font and size. Highlighting or changing the number alone does not apply it.
- **Control+S** for an exact size; **Control+U** to undo; **Escape** to close.

On Linux, shortcuts are labeled Ctrl. The sample uses your current font; it is not a preview of the highlighted face.

## Terminals

| Terminal | Applying a change |
| --- | --- |
| macOS Terminal | Updates the current tab and preserves the window size. |
| iTerm2 | Updates the current session; Python API setup required. |
| Ghostty | Saves config; reload with Command+Shift+, on macOS or Ctrl+Shift+, on Linux. |
| kitty | Saves config; reload with Ctrl+Shift+F5. |

Support is experimental and live behavior still needs validation across terminal versions. Local sessions only. See [setup notes](docs/setup.md) for custom paths and terminal detection.

## Update or remove

```sh
herdr plugin update herdr.fonts
herdr plugin uninstall herdr.fonts
```

Undo any font changes you want to revert before uninstalling, and remove the optional keybinding afterward. Uninstalling does not reset terminal settings.

## Contribute

Want another terminal supported or a better picker? Open an [issue](https://github.com/ernsahin/herdr-fonts/issues) or send a PR. Bug reports and small improvements are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) to get started.

## License

[MIT](LICENSE).
