#!/usr/bin/env python3
"""Compatibility entrypoint; use herdr_fonts.py or herdr-fonts."""
from herdr_fonts import main
from fontstudio.core import StudioError
import sys

if __name__ == "__main__":
    try:
        main()
    except (StudioError, OSError, ValueError) as exc:
        print(f"herdr-fonts: {exc}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(130)
