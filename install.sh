#!/bin/sh
set -eu

herdr_fonts_root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
command -v python3 >/dev/null 2>&1 || { printf 'Python 3.9+ is required.\n' >&2; exit 1; }
command -v herdr >/dev/null 2>&1 || { printf 'Install Herdr first: https://herdr.dev\n' >&2; exit 1; }
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else "Python 3.9+ is required")'

herdr plugin link "$herdr_fonts_root" >/dev/null
python3 "$herdr_fonts_root/herdr_fonts.py" setup-launcher
if ! python3 "$herdr_fonts_root/herdr_fonts.py" setup-shortcut; then
    printf 'Plugin installed. The existing Herdr shortcut configuration was left unchanged.\n'
fi
printf '\nReady. Run herdr-fonts, or use prefix+f after reloading Herdr config.\n'
