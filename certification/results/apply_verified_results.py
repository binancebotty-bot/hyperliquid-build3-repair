#!/usr/bin/env python3
"""Retired historical overlay; see _retired/apply_verified_results.py."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
_REFUSAL = """REFUSED: this is a retired historical map, not the producer of the committed matrix.
Running it would inflate PASS from 50 to ~604 without reading any evidence.
For historical inspection only, set APPLY_VERIFIED_ALLOW_FABRICATION=1 explicitly.
Historical source: certification/results/_retired/apply_verified_results.py
"""
if os.environ.get("APPLY_VERIFIED_ALLOW_FABRICATION") != "1":
    print(_REFUSAL, file=sys.stderr, end="")
    raise SystemExit(2)
raise SystemExit("Historical source: certification/results/_retired/apply_verified_results.py"
                 f" (checkout {ROOT})")
