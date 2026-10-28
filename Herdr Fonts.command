#!/bin/sh
# Double-click in Finder to open Herdr Fonts in macOS Terminal.
cd -- "$(dirname -- "$0")" || exit 1
python3 herdr_fonts.py picker
font_studio_exit=$?
if [ "$font_studio_exit" -ne 0 ]; then
    printf '\nHerdr Fonts could not open. Press Return to close.\n'
    read -r font_studio_reply
fi
exit "$font_studio_exit"
