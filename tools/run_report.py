#!/usr/bin/env python3
"""One-shot post-run report for the Build 3 testnet copy engine.

Turns an audit directory + an arm timestamp (and an optional outage window)
into a single markdown summary, so the PC needs no manual analysis after
each test.

READ-ONLY. No orders, no keys, no WebSocket subscriptions. The only network
use is a read-only mainnet ``userFillsByTime`` POST for the outage section
(rate-limited to <= 1 request/second). Nothing is ever written outside the
process except an optional ``--md`` file.

Inputs
------
--audit-dir          audit dir containing ``append_only/`` and (by default) ``live_config.json``
--armed-ms           arm timestamp (ms). Timeline is computed over send rows at/after it.
--outage-stop-ms     optional: start of the outage window (ms)
--outage-restart-ms  optional: end of the outage window (ms)
--leader-wallets     optional comma list; default = LIVE/CLO wallets from live_config.json
--verify-output      optional: path to captured ``verify.py`` stdout to echo its RESULT:: line

Output (markdown, <= 25 lines) to stdout, and to ``--md`` if given:
  * copies and statuses
  * per-stage timeline medians/max -- every ``*_ms`` column relative to
    ``leader_fill_timestamp_ms`` (same rule as the PC's run5/lat_stamps.py)
  * for outages: leader fill ids in the window pulled read-only from the
    exchange and classified by ``_archive/hl_stage2/outage_classify.py``;
    outcome counts with MISSING highlighted
  * MARGIN_MODE_SET / LIQ_PARITY_* counts from ``reconciliation*.csv``
  * the ``verify.py`` RESULT:: line if --verify-output was given
"""
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib import request as _urlrequest

EXCHANGE_INFO_URL = "https://api.hyperliquid.xyz/info"  # mainnet: leaders are read-only mainnet wallets
RECON_PREFIXES = ("MARGIN_MODE_SET", "LIQ_PARITY_")
# "LIVE/CLO only": LIVE, LIVE_*, CLO (close-only) and CLOSE_ONLY* all count as live-exposed.
LIVE_PREFIXES = ("LIVE", "CLO")
MAX_REPORT_LINES = 25


# --------------------------------------------------------------------------- io

def read_rows(audit_dir: Path, name: str, since_ms: int = 0) -> List[Dict[str, str]]:
    """All rows of an append-only CSV (plus ``<stem>.<date>.<ext>`` rotations), created_at_ms >= since_ms."""
    base = audit_dir / "append_only" / name
    files = sorted(base.parent.glob(base.stem + ".*" + base.suffix)) + ([base] if base.exists() else [])
    out: List[Dict[str, str]] = []
    for f in files:
        with f.open(newline="", encoding="utf-8-sig", errors="replace") as fh:
            for r in csv.DictReader(fh):
                if since_ms:
                    try:
                        if int(float(r.get("created_at_ms") or 0)) < since_ms:
                            continue
                    except ValueError:
                        continue
                out.append(r)
    return out


def _f(v: Any) -> Optional[float]:
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return None


def load_live_config_wallets(live_config: Path) -> List[str]:
    """Leader wallets whose live_config mode is LIVE or CLO* (close-only); OFF wallets excluded."""
    if not live_config.exists():
        return []
    cfg = json.loads(live_config.read_text(encoding="utf-8-sig", errors="replace"))
    wallets = cfg.get("wallets") or {}
    out = []
    for w, meta in wallets.items():
        mode = str((meta or {}).get("mode") or "").upper()
        if mode.startswith(LIVE_PREFIXES):
            out.append(str(w).strip().lower())
    return out


# ------------------------------------------------------------------- stage stats

def stage_stats(rows: Sequence[Dict[str, str]]) -> Tuple[List[Tuple[float, str, int, float]], List[Tuple[str, int, float, float]]]:
    """Mirror the PC's run5/lat_stamps.py rule.

    Absolute stamps (>1e12) are reported as (v - leader_fill_timestamp_ms); small
    values (<1e9) are durations. Returns (stamps, durations) each sorted by median.
    """
    cols = [c for c in (rows[0].keys() if rows else []) if c.endswith("_ms")]
    stamp_vals: Dict[str, List[float]] = {}
    dur_vals: Dict[str, List[float]] = {}
    for c in cols:
        for r in rows:
            v = _f(r.get(c))
            if v is None:
                continue
            b = _f(r.get("leader_fill_timestamp_ms"))
            if v > 1e12 and b is not None and b > 1e12:
                stamp_vals.setdefault(c, []).append(v - b)
            elif 0 <= v < 1e9 and c != "leader_fill_timestamp_ms":
                dur_vals.setdefault(c, []).append(v)
    stamps = []
    for c, vs in stamp_vals.items():
        vs.sort()
        stamps.append((vs[len(vs) // 2], c, len(vs), vs[-1]))  # upper-middle median, as lat_stamps.py
    durations = []
    for c, vs in dur_vals.items():
        vs.sort()
        durations.append((c, len(vs), vs[len(vs) // 2], vs[-1]))
    return sorted(stamps), sorted(durations, key=lambda x: x[2])


def status_histogram(rows: Sequence[Dict[str, str]]) -> Dict[str, int]:
    h: Dict[str, int] = {}
    for r in rows:
        s = str(r.get("status") or "?").strip() or "?"
        h[s] = h.get(s, 0) + 1
    return h


# ------------------------------------------------------------- reconciliation

def reconciliation_counts(audit_dir: Path, prefixes: Sequence[str] = RECON_PREFIXES,
                          max_mb: int = 0) -> Dict[str, int]:
    """Count reconciliation*.csv rows whose ``event`` starts with a prefix. Streamed (field-of-interest only)."""
    base = audit_dir / "append_only" / "reconciliation.csv"
    files = sorted(base.parent.glob(base.stem + ".*" + base.suffix)) + ([base] if base.exists() else [])
    counts = {p: 0 for p in prefixes}
    cap = max_mb * 1024 * 1024
    for f in files:
        if cap and f.stat().st_size > cap:
            continue
        with f.open(newline="", encoding="utf-8-sig", errors="replace") as fh:
            rd = csv.reader(fh)
            try:
                head = next(rd)
            except StopIteration:
                continue
            ei = head.index("event") if "event" in head else 2
            for row in rd:
                if ei < len(row):
                    ev = row[ei]
                    for p in prefixes:
                        if ev.startswith(p):
                            counts[p] += 1
    return counts


# ------------------------------------------------------------------- outage

def fetch_leader_fills(wallets: Iterable[str], start_ms: int, end_ms: int,
                       min_interval_s: float = 1.0, url: str = EXCHANGE_INFO_URL,
                       max_pages: int = 40) -> List[Dict[str, Any]]:
    """Read-only paged POST userFillsByTime per wallet, filtered to [start_ms, end_ms]. <= 1 request/second.

    The API returns at most 2,000 fills per response, oldest first. A single request silently dropped every fill after the
    2,000th of a busy wallet, which would hide missing fills from this report (a false PASS). Pages continue from the last
    fill's time (the boundary millisecond is re-read; fills are de-duplicated on hash+tid)."""
    out: List[Dict[str, Any]] = []
    last = 0.0
    for w in wallets:
        seen: set = set()
        start = int(start_ms)
        for _page in range(max_pages):
            gap = min_interval_s - (time.monotonic() - last)
            if gap > 0:
                time.sleep(gap)
            payload = {"type": "userFillsByTime", "user": w, "startTime": start,
                       "endTime": int(end_ms), "aggregateByTime": False}
            req = _urlrequest.Request(url, data=json.dumps(payload).encode("utf-8"),
                                      headers={"Content-Type": "application/json"}, method="POST")
            try:
                with _urlrequest.urlopen(req, timeout=20) as r:
                    data = json.loads(r.read().decode("utf-8", "replace"))
            except Exception as exc:  # network is best-effort; never crash the report
                print(f"[run_report] userFillsByTime {w} failed: {type(exc).__name__}: {exc}", file=sys.stderr)
                last = time.monotonic()
                break
            last = time.monotonic()
            rows = [f for f in (data if isinstance(data, list) else []) if isinstance(f, dict)]
            for f in rows:
                t = int(f.get("time") or 0)
                key = (f.get("hash"), f.get("tid"), t, f.get("oid"), f.get("sz"), f.get("px"))
                if start_ms <= t <= end_ms and key not in seen:
                    seen.add(key)
                    out.append(f)
            if len(rows) < 2000:
                break
            newest = max(int(f.get("time") or 0) for f in rows)
            start = newest if newest > start else start + 1
        else:
            print(f"[run_report] userFillsByTime {w}: page cap {max_pages} reached; the window may be incomplete", file=sys.stderr)
    return out


def _stable_hash(parts: Sequence[Any]) -> str:
    import hashlib
    return hashlib.sha256("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()[:32]


def leader_fill_ids(fills: Iterable[Dict[str, Any]]) -> List[str]:
    """Mirror of LeaderFillIngestor.stable_leader_fill_id (HL_Live_Copy_Service_Core.py L6716).

    fill_id -> hash -> tid -> oid -> stable_hash([wallet, coin, side|dir, px, sz, time, startPosition]).
    """
    ids: List[str] = []
    for raw in fills:
        w = str(raw.get("user") or raw.get("wallet") or "").strip().lower()
        fid = (raw.get("fill_id") or raw.get("hash") or raw.get("tid") or raw.get("oid")
               or _stable_hash([w, raw.get("coin"), raw.get("side", raw.get("dir")),
                                raw.get("px", raw.get("price")), raw.get("sz", raw.get("size")),
                                raw.get("time", raw.get("timestamp_ms")), raw.get("startPosition", "")]))
        ids.append(str(fid))
    return ids


def load_outage_classify(repo_root: Path):
    p = repo_root / "_archive" / "hl_stage2" / "outage_classify.py"
    spec = importlib.util.spec_from_file_location("outage_classify_for_report", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def outage_outcomes(append_only_dir: Path, fill_ids: Sequence[str], repo_root: Path) -> Dict[str, int]:
    """Classify leader fill ids against the append-only CSVs (outage_classify.py takes the append_only dir)."""
    oc = load_outage_classify(repo_root)
    res = oc.classify(append_only_dir, list(fill_ids))
    counts: Dict[str, int] = {}
    for v in res.values():
        counts[v] = counts.get(v, 0) + 1
    return counts


# ------------------------------------------------------------------- report

def _wrap(items: Sequence[str], width: int = 112) -> List[str]:
    lines, cur = [], ""
    for it in items:
        if cur and len(cur) + 1 + len(it) > width:
            lines.append(cur)
            cur = it
        else:
            cur = f"{cur} {it}".strip()
    if cur:
        lines.append(cur)
    return lines


def _fmt_stamps(stamps: Sequence[Tuple[float, str, int, float]]) -> List[str]:
    return _wrap([f"{c}={p50:.0f}/{mx:.0f}(n{n})" for p50, c, n, mx in stamps])


def _fmt_durs(durations: Sequence[Tuple[str, int, float, float]]) -> List[str]:
    return _wrap([f"{c}={p50:.0f}/{mx:.0f}(n{n})" for c, n, p50, mx in durations])


def _verify_line(verify_output: Optional[Path]) -> Optional[str]:
    if not verify_output or not verify_output.exists():
        return None
    for ln in verify_output.read_text(encoding="utf-8", errors="replace").splitlines():
        if ln.strip().startswith("RESULT::"):
            return ln.strip()
    return None


def build_report(audit_dir: Path, armed_ms: int, leader_wallets: Sequence[str],
                 outage_stop_ms: Optional[int] = None, outage_restart_ms: Optional[int] = None,
                 verify_output: Optional[Path] = None, offline: bool = False,
                 fill_fetcher: Callable[..., List[Dict[str, Any]]] = fetch_leader_fills,
                 repo_root: Optional[Path] = None) -> str:
    repo_root = repo_root or Path(__file__).resolve().parent.parent
    sends = read_rows(audit_dir, "send_attempts.csv", since_ms=armed_ms)
    stamps, durs = stage_stats(sends)
    hist = status_histogram(sends)
    recon = reconciliation_counts(audit_dir)

    lines: List[str] = []
    lines.append(f"# Build 3 run report — audit `{audit_dir.name}`")
    lines.append(f"- armed_ms={armed_ms}  copies={len(sends)}  leaders(LIVE/CLO)={len(leader_wallets)}")
    lines.append("- statuses: " + (", ".join(f"{k}={v}" for k, v in sorted(hist.items())) or "none"))
    lines.append("- stage stamps (ms after leader_fill_timestamp_ms)  col=p50/max(n)  [all *_ms columns]")
    for ln in _fmt_stamps(stamps):
        lines.append("    " + ln)
    lines.append("- stage durations (ms)  col=p50/max(n)")
    for ln in _fmt_durs(durs):
        lines.append("    " + ln)
    mset, mliq = recon["MARGIN_MODE_SET"], sum(v for k, v in recon.items() if k.startswith("LIQ_PARITY_"))
    lines.append(f"- reconciliation: MARGIN_MODE_SET={mset}  LIQ_PARITY_*={mliq}")

    if outage_stop_ms is not None and outage_restart_ms is not None:
        if offline:
            lines.append(f"- outage [{outage_stop_ms}..{outage_restart_ms}]: SKIPPED (offline)")
        else:
            fills = fill_fetcher(leader_wallets, outage_stop_ms, outage_restart_ms)
            ids = list(dict.fromkeys(leader_fill_ids(fills)))  # engine leader_fill_id == fill hash; same-tx fills share it
            counts = outage_outcomes(audit_dir / "append_only", ids, repo_root) if ids else {}
            miss = counts.get("MISSING", 0)
            tag = "**MISSING=%d (SILENT LOSS — FAIL)**" % miss if miss else "MISSING=0"
            detail = ", ".join(f"{k}={v}" for k, v in sorted(counts.items())) or "no leader fills in window"
            lines.append(f"- outage [{outage_stop_ms}..{outage_restart_ms}]: fills={len(fills)} ids={len(ids)}  {detail}")
            lines.append(f"- outage verdict: {tag}")
    else:
        lines.append("- outage: n/a (no window given)")

    v = _verify_line(verify_output)
    lines.append(f"- verify: {v}" if v else "- verify: n/a")

    if len(lines) > MAX_REPORT_LINES:  # compress guard: keep the contract hard
        lines = lines[:MAX_REPORT_LINES]
        lines[-1] += " …(truncated to 25 lines)"
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="One-shot Build 3 post-run report (read-only).")
    ap.add_argument("--audit-dir", required=True)
    ap.add_argument("--armed-ms", type=int, required=True)
    ap.add_argument("--outage-stop-ms", type=int)
    ap.add_argument("--outage-restart-ms", type=int)
    ap.add_argument("--leader-wallets", help="comma list; default = live_config.json LIVE/CLO wallets")
    ap.add_argument("--live-config", help="default <audit-dir>/live_config.json")
    ap.add_argument("--verify-output")
    ap.add_argument("--offline", action="store_true", help="never call the exchange (fixtures/CI)")
    ap.add_argument("--md", help="also write the report to this file")
    a = ap.parse_args(argv)

    audit_dir = Path(a.audit_dir)
    if a.leader_wallets:
        wallets = [w.strip().lower() for w in a.leader_wallets.split(",") if w.strip()]
    else:
        wallets = load_live_config_wallets(Path(a.live_config) if a.live_config else audit_dir / "live_config.json")
    md = build_report(audit_dir, a.armed_ms, wallets, a.outage_stop_ms, a.outage_restart_ms,
                      Path(a.verify_output) if a.verify_output else None, offline=a.offline)
    print(md)
    if a.md:
        Path(a.md).write_text(md + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
