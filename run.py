#!/usr/bin/env python3
"""Run MakerStl application."""

import sys
from pathlib import Path

# add src to path
src_dir = Path(__file__).parent / "src"
sys.path.insert(0, str(src_dir))

from makerstl.app import main

if __name__ == "__main__":
    sys.exit(main())
