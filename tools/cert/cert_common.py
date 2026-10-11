"""Shared helpers for the J4 offline certification scripts (Build-3, task K2).

Every script under tools/cert/ is OFFLINE. It reads COPIES of audit CSVs and
exchange/projection JSON snapshots supplied on the command line. Nothing here
touches the running engine, its ports (8012/8014/8031), the Wallet Finder, keys,
.env, the live checkout at hl-build3-testnet-cert, or the exchange.

Result convention (same as the J4 run specs in process/PC_RUN_SCRIPTS_2026-10-11.md):

    <TAG>:: PASS <detail>          -> exit 0
    <TAG>:: FAIL <detail>          -> exit 1
    <TAG>:: INCONCLUSIVE <reason>  -> exit 3

Detail lines may be printed before it, but the verdict line is the LAST line on
stdout and it carries the tag the J4 spec names (GAP1_RESULT, GAP2_RESULT, ...).
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

PASS = 0
FAIL = 1
INCONCLUSIVE = 3

_LABELS = {PASS: 'PASS', FAIL: 'FAIL', INCONCLUSIVE: 'INCONCLUSIVE'}


def load_rows(path):
    """Rows of an audit CSV copy. Missing/empty file -> []."""
    p = Path(path)
    if not p.is_file() or p.stat().st_size <= 0:
        return []
    with p.open('r', encoding='utf-8-sig', newline='') as fh:
        return list(csv.DictReader(fh))


def load_json(path, default=None):
    p = Path(path)
    if not p.is_file():
        return default
    with p.open('r', encoding='utf-8-sig') as fh:
        return json.load(fh)


def as_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def as_int_ms(value, default=0):
    return int(as_float(value, default))


def audit_files(audit_dir, names=('send_attempts.csv', 'reconciliation.csv', 'order_intents.csv')):
    """The named audit CSVs plus their rotated copies (reconciliation.20261010.1.csv),
    oldest first -- the same set the engine's audit_history_paths() walks."""
    out = []
    d = Path(audit_dir)
    for name in names:
        stem, suffix = name[:-4], name[-4:]
        out.extend(sorted(p for p in d.glob('%s.*%s' % (stem, suffix)) if p.is_file()))
        p = d / name
        if p.is_file():
            out.append(p)
    return out


def emit(tag, code, detail=''):
    """Print the single verdict line and return the process exit code."""
    print('%s:: %s%s' % (tag, _LABELS[code], (' ' + detail) if detail else ''))
    return code


def core_import(core_dir):
    """Import the engine module from a checkout (read-only) with the audit dir
    pointed at the caller's env. Returns the imported module."""
    import importlib
    import os
    import sys

    core_dir = str(Path(core_dir).resolve())
    if core_dir not in sys.path:
        sys.path.insert(0, core_dir)
    os.environ.setdefault('HL_LIVE_ENV_FILE', '/nonexistent')
    return importlib.import_module('HL_Live_Copy_Service_Core')
