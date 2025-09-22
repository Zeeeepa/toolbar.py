#!/usr/bin/env python3
"""
Deprecated entrypoint. Please use the new translate CLI instead.

Usage examples:
  python -m translate map <project>
  python -m translate translate <project> --engine zai
  python -m translate export <project>
  python -m translate validate <project>
  python -m translate apply <project> --out <output_dir>
"""
from __future__ import annotations

import sys
from translate.cli import main as translate_main

if __name__ == "__main__":
    print("[DEPRECATION] translate-full.py is deprecated. Redirecting to 'python -m translate' ...")
    raise SystemExit(translate_main(sys.argv[1:]))

