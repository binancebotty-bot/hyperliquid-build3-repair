#!/usr/bin/env python3
"""Outage / replay classifier: gives every leader fill id exactly one outcome from the engine's audit CSVs.

    python outage_classify.py <append_only_dir> <fill_ids.txt|-> [--json]

Outcomes: SENT, MERGED_SENT (carried by another fill's order), MERGED_<state> (carried by a blocked order),
SKIPPED_FLAT (leader already flat), BLOCKED_<terminal_state>, DEFERRED_OPEN (held, retry pending), MISSING.
A test passes only if MISSING == 0 ("never silently lose a trade"). Read-only; never touches the network or keys.
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List

_SENT = {"ORDER_FILLED", "ORDER_PARTIAL", "ORDER_RESTING", "FILLED", "SENT", "REAL_IOC_FILLED"}


def _rows(path: Path) -> Iterable[Dict[str, str]]:
    files = sorted(path.parent.glob(path.stem + ".*" + path.suffix)) + ([path] if path.exists() else [])
    for f in files:
        with f.open(newline="", encoding="utf-8-sig", errors="replace") as fh:
            yield from csv.DictReader(fh)


def classify(audit_dir: Path, fill_ids: List[str]) -> Dict[str, str]:
    intents: Dict[str, Dict[str, str]] = {}      # leader_fill_id (head) -> intent row
    merged_head: Dict[str, str] = {}             # sibling id -> head fill id
    for r in _rows(audit_dir / "order_intents.csv"):
        head = r.get("leader_fill_id", "")
        intents[head] = r
        m = re.search(r"merged_leader_fills=\d+:([^;]*)", r.get("notes", "") or "")
        if m:
            for sib in (x for x in m.group(1).split(",") if x):
                merged_head[sib] = head
    sent_by_fill: Dict[str, bool] = {}
    for r in _rows(audit_dir / "send_attempts.csv"):
        if str(r.get("status", "")).upper() in _SENT or str(r.get("exchange_status", "")).upper() in _SENT:
            sent_by_fill[r.get("leader_fill_id", "")] = True
    recon: Dict[str, List[Dict[str, str]]] = {}
    for r in _rows(audit_dir / "reconciliation.csv"):
        recon.setdefault(r.get("leader_fill_id", ""), []).append(r)

    def own(fid: str) -> str:
        if sent_by_fill.get(fid):
            return "SENT"
        terms = [str(r.get("terminal_state", "")) for r in recon.get(fid, []) if r.get("terminal_state")]
        for t in reversed(terms):
            if t.startswith(("REPLAY_DEFERRED", "FILL_PENDING")):
                continue
            if t == "MISSED_ENTRY_LEADER_ALREADY_CLOSED":
                return "SKIPPED_FLAT"
            return "BLOCKED_" + t
        if terms:
            return "DEFERRED_OPEN"
        if fid in intents:
            return "BLOCKED_INTENT_NO_TERMINAL"
        return ""

    out: Dict[str, str] = {}
    for fid in fill_ids:
        res = own(fid)
        if not res and fid in merged_head:
            head = own(merged_head[fid])
            res = ("MERGED_SENT" if head == "SENT" else "MERGED_" + (head or "NO_OUTCOME")) if head else ""
            if not head:
                res = "MERGED_NO_OUTCOME"
        out[fid] = res or "MISSING"
    return out


def missing_detail(audit_dir: Path, missing: List[str], limit: int = 40) -> List[str]:
    """Where does each MISSING id appear at all? Every csv in the audit dir and its parent is scanned once.
    No file at all = the engine never ingested it (catch-up did not fetch it, wallet OFF, cursor past it);
    a file but no final row = it was ingested and then lost. Also shows wallet/coin/side/time when a row carries them."""
    if not missing:
        return []
    want = set(missing)
    seen: Dict[str, Dict[str, int]] = {}
    info: Dict[str, Dict[str, str]] = {}
    files = sorted(set(audit_dir.glob("*.csv")) | set(audit_dir.parent.glob("*.csv")))
    for f in files:
        try:
            with f.open(newline="", encoding="utf-8-sig", errors="replace") as fh:
                for r in csv.DictReader(fh):
                    for fid in {str(v) for k, v in r.items() if v and ("fill" in str(k) or k in ("hash", "tid", "id"))} & want:
                        seen.setdefault(fid, {})[f.name] = seen.get(fid, {}).get(f.name, 0) + 1
                        if fid not in info:
                            info[fid] = {k: str(r.get(k) or "") for k in ("leader_wallet", "wallet", "coin", "side", "dir", "timestamp_ms", "time", "terminal_state", "status") if r.get(k)}
        except Exception as exc:
            print(f"MISSING_DETAIL scan error {f.name}: {exc!r}")
    never = [m for m in missing if m not in seen]
    out = [f"MISSING_NEVER_IN_ANY_FILE={len(never)} (engine never ingested)  MISSING_IN_SOME_FILE={len(missing) - len(never)} (ingested, no final row)"]
    for m in missing[:limit]:
        out.append(f"MISSING_ID {m} files={seen.get(m, {})} {info.get(m, {})}")
    if len(missing) > limit:
        out.append(f"MISSING_ID ... {len(missing) - limit} more")
    return out


def block_reasons(audit_dir: Path, fill_ids: List[str], top: int = 12) -> List[str]:
    """Why were the blocked fills blocked? Counts the final row of each id by terminal_state plus the reason text in its notes
    (reason=... / block_reason=...). Q3/Q4: dozens of ENTRY_BLOCKED_RISK rows and zero copies, reason never visible."""
    want = set(fill_ids)
    last: Dict[str, Dict[str, str]] = {}
    for r in _rows(audit_dir / "reconciliation.csv"):
        fid = r.get("leader_fill_id", "")
        t = str(r.get("terminal_state", ""))
        if fid in want and t and not t.startswith(("REPLAY_DEFERRED", "FILL_PENDING")):
            last[fid] = r
    counts: Dict[str, int] = {}
    for r in last.values():
        m = re.search(r"(?:block_reason|reason)=([^;]{0,90})", r.get("notes", "") or "")
        key = f"{r.get('terminal_state', '')} | {(m.group(1).strip() if m else '')}"
        counts[key] = counts.get(key, 0) + 1
    out = ["BLOCK_REASONS (terminal_state | reason): count"]
    for k, n in sorted(counts.items(), key=lambda kv: -kv[1])[:top]:
        out.append(f"  {n:4d}  {k}")
    return out


def main(argv: List[str]) -> int:
    if len(argv) < 3:
        print(__doc__)
        return 2
    ids_src = sys.stdin.read() if argv[2] == "-" else Path(argv[2]).read_text()
    ids = [x.strip() for x in re.split(r"[\s,]+", ids_src) if x.strip()]
    res = classify(Path(argv[1]), ids)
    counts: Dict[str, int] = {}
    for v in res.values():
        counts[v] = counts.get(v, 0) + 1
    for k in sorted(counts):
        print(f"{k:45s} {counts[k]}")
    missing = [k for k, v in res.items() if v == "MISSING"]
    print(f"MISSING={len(missing)} of {len(res)}")
    for line in missing_detail(Path(argv[1]), missing):
        print(line)
    for line in block_reasons(Path(argv[1]), list(res)):
        print(line)
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
