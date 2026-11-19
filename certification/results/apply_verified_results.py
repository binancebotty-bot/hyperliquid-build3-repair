"""Retired historical overlay; see _retired/apply_verified_results.py."""
import os
import sys

_REFUSAL = """REFUSED: this is a retired historical map, not the producer of the committed matrix.
Running it would inflate PASS from 59 to ~579 without reading any evidence.
For historical inspection only, set APPLY_VERIFIED_ALLOW_FABRICATION=1 explicitly.
Historical source: certification/results/_retired/apply_verified_results.py
"""
if os.environ.get("APPLY_VERIFIED_ALLOW_FABRICATION") != "1":
    print(_REFUSAL, file=sys.stderr, end="")
    raise SystemExit(2)
raise SystemExit("Historical source: certification/results/_retired/apply_verified_results.py")
