#!/usr/bin/env python3
"""Restore the testnet live_config.json from a backup with the 10 busiest wallets LIVE and the rest OFF.

Usage: python tools/restore_live_config.py [--dir <audit dir>] [--backup <file>] [--execute]
Default is a dry run (prints what would change). Testnet audit dir only (refuses a path without 'testnet').
Keeps the clobbered file as live_config.json.CLOBBERED_<UTC ts>; writes atomically; no keys, no network.
"""
import argparse
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

LIVE = ["0x7019197d2b", "0x936cf4fb95", "0xc179e03922", "0xd4c1f7e8d8", "0xf5d81a135f",
        "0x31ca8395cf", "0x010461c14e", "0x6ba889db7f", "0x7717a7a245", "0x1b232b41b0"]
DEFAULT_BACKUP = "live_config.json.bak_before_live10_20261015_141519"


def find_dir(explicit):
    if explicit:
        return Path(explicit)
    env = os.environ.get("HL_LIVE_AUDIT_DIR")
    if env:
        return Path(env)
    for base in (Path.cwd(), Path.cwd().parent, Path.cwd().parent.parent):
        for cand in base.glob("**/hl_live_copy_audit_testnet"):
            if (cand / "live_config.json").exists():
                return cand
    raise SystemExit("audit dir not found: pass --dir")


def build(backup_path):
    cfg = json.loads(Path(backup_path).read_text(encoding="utf-8-sig"))
    wallets = cfg.get("wallets") or {}
    live, off = [], []
    for addr, wc in wallets.items():
        if not isinstance(wc, dict):
            continue
        if any(str(addr).lower().startswith(p) for p in LIVE):
            wc["enabled"], wc["mode"] = True, "LIVE"
            live.append(addr)
        else:
            wc["mode"] = "OFF"
            off.append(addr)
    if len(live) != 10:
        raise SystemExit("expected 10 LIVE wallets in the backup, matched %d: refusing" % len(live))
    cfg["auto_send_enabled"] = True
    gc = cfg.setdefault("global_controls", {})
    gc["send_mode"] = "ON"  # send_mode wins over auto_send_enabled (arm effect used by the runner)
    return cfg, live, off


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir")
    ap.add_argument("--backup")
    ap.add_argument("--execute", action="store_true")
    a = ap.parse_args()
    d = find_dir(a.dir)
    if "testnet" not in str(d).lower():
        raise SystemExit("refusing: not a testnet audit dir: %s" % d)
    backup = Path(a.backup) if a.backup else d / DEFAULT_BACKUP
    cfg, live, off = build(backup)
    print("dir=%s backup=%s LIVE=%d OFF=%d auto_send=%s" % (d, backup.name, len(live), len(off), cfg["auto_send_enabled"]))
    for w in live:
        print("  LIVE", w[:12])
    for w in off:
        print("  OFF ", w[:12])
    if not a.execute:
        print("dry run: nothing written")
        return
    target = d / "live_config.json"
    if target.exists():
        shutil.copy2(target, d / ("live_config.json.CLOBBERED_" + time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())))
    fd, tmp = tempfile.mkstemp(dir=str(d), prefix="live_config.", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, indent=2)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, target)
    print("written", target)


if __name__ == "__main__":
    main()
