# Optional setup

## Run from source

For local development, use `herdr plugin link "$PWD"` from the repository root. Herdr's GitHub installer and local links use the same manifest.

The optional `./install.sh` helper also creates a standalone `herdr-fonts` shell command and sets up the shortcut. It is a convenience for source checkouts, not a replacement for `herdr plugin install`. Keep that checkout in place while using its shell command. On macOS, `Herdr Fonts.command` opens the standalone picker in Terminal.

Switching an existing local link to a GitHub install requires `herdr plugin unlink herdr.fonts` before `herdr plugin install ernsahin/herdr-fonts`. Config and undo history are kept. Local links are removed with `plugin unlink`; GitHub installs use `plugin uninstall`.

## iTerm2

Enable **Settings → General → Magic → Enable Python API**, then run:

```sh
fonts_config="$(herdr plugin config-dir herdr.fonts)"
python3 -m venv "$fonts_config/.venv"
"$fonts_config/.venv/bin/python3" -m pip install iterm2
```

The plugin uses this environment automatically.

## Custom config paths

Run `herdr plugin config-dir herdr.fonts` and create `config.json` in that directory:

```json
{
  "ghostty_config": "/absolute/path/to/ghostty/config",
  "kitty_config": "/absolute/path/to/kitty.conf"
}
```

Use **Control+T** in the picker if terminal detection is incorrect. Linux font discovery requires Fontconfig (`fc-list`). Local sessions only; SSH and WSL-to-Windows font management are not supported.

## Development

```sh
python3 -m unittest discover -s tests -v
```

Undo history is kept in `HERDR_PLUGIN_STATE_DIR/history.json`. Undo stops if settings changed outside the plugin. The latest picker error is saved as `last-error.txt` in the same directory.
