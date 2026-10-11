#!/usr/bin/env python3
"""Outage test 14: the follower scope sweep (one read per perp DEX, hundreds on testnet) failed as a whole whenever ONE read
failed (a 429 or non-JSON reply), so entries stayed blocked for 2 h. The sweep now retries each DEX, keeps each DEX's last good
reading, paces its reads, retries sooner while unclean, and says so in the audit when it keeps failing.
Run (from _archive/hl_stage2): HL_LIVE_ENV_FILE=/nonexistent python -u test_core_scope_sweep_resilience.py"""
from __future__ import annotations
import os, sys, tempfile, threading, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
RESULTS = []
FOLLOWER = "0x" + "c" * 40
LEADER = "0x" + "d" * 40
DEXES = [{"name": f"dex{i:03d}"} for i in range(60)]


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


def main():
    tmp = Path(tempfile.mkdtemp(prefix="scoperes_"))
    env_file = tmp / "stage2.env"
    env_file.write_text(f"HL_LIVE_HL_ACCOUNT_ADDRESS={FOLLOWER}\nHL_FOLLOWER_DEXES=xyz\n", encoding="utf-8")
    for k in ("HL_FOLLOWER_DEXES", "HL_LIVE_HL_ACCOUNT_ADDRESS", "HL_USER_WALLET"):
        os.environ.pop(k, None)
    os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LEADER_NETWORK": "mainnet", "HL_FOLLOWER_NETWORK": "testnet",
                       "HL_LIVE_ENV_FILE": str(env_file), "HL_LIVE_SCOPE_SWEEP_THREAD": "0",
                       "HL_LIVE_SCOPE_DEX_FRESH_SEC": "0", "HL_LIVE_SCOPE_SWEEP_WEIGHT_PER_MIN": "1000000",
                       "HL_LIVE_SCOPE_BACKOFF_MULT": "0.01", "HL_LIVE_SCOPE_FAIL_ROW_AFTER": "2"})
    import requests
    import HL_Live_Copy_Service_Core as c

    def offline(*a, **k):
        raise RuntimeError("offline test: no network")
    requests.post = offline
    c.requests.post = offline
    c.USER_WALLET = FOLLOWER
    lock = threading.Lock()
    tries = {}
    book = {"flaky": set(), "dead": set(), "fail_first": 2}

    def fetch(payload):
        if payload.get("type") == "perpDexs":
            return DEXES + [{"name": "xyz"}]
        d = payload.get("dex", "")
        with lock:
            tries[d] = tries.get(d, 0) + 1
            n = tries[d]
        if d in book["dead"]:
            raise ValueError("Expecting value: line 1 column 1 (char 0)")   # a 429 body that is not JSON
        if d in book["flaky"] and n <= book["fail_first"]:
            raise ValueError("Expecting value: line 1 column 1 (char 0)")
        return {"assetPositions": [], "marginSummary": {"accountValue": "0"}}
    c.EXPOSURE_FETCHER = fetch
    c.atomic_write_json(c.LIVE_CONFIG_FILE, {"auto_send_enabled": True, "global_controls": {}, "wallets": {
        LEADER: {"enabled": True, "mode": "LIVE", "copy_mode": "fixed", "fixed_notional": 12}}})
    os.environ.pop("HL_LIVE_MOCK_SEND", None)
    core = c.LiveCopyCore(source_csv=tmp / "none.csv")
    try:
        core.cfg = c.ConfigManager()
        # (1) transient failures on 10 DEXes (two bad replies each): retried, the sweep is clean at once
        book["flaky"] = {f"dex{i:03d}" for i in range(0, 60, 6)}
        res = core.run_scope_sweep()
        check("TRANSIENT_FAILURES_ARE_RETRIED_SWEEP_CLEAN", res.get("ok") and core._scope_sweep_block() == "", str(res)[:200])
        # (2) one DEX that cannot be read at all: fails closed, names it and why
        book["dead"] = {"dex007"}
        tries.clear()
        core.__dict__["_scope_dex_cache"].pop("dex007", None)
        core._scope_sweep_ok = None
        res = core.run_scope_sweep()
        check("DEAD_DEX_FAILS_CLOSED_AND_IS_NAMED", (not res.get("ok")) and res.get("dex") == "dex007" and "Expecting value" in str(res.get("detail")),
              str(res)[:200])
        check("BLOCK_SAYS_SCOPE_UNAVAILABLE", core._scope_sweep_block().startswith("SCOPE_SWEEP_PENDING: SCOPE_UNAVAILABLE"), core._scope_sweep_block())
        # (2b) a new DEX that cannot be read closes the gate even though an earlier sweep was clean
        check("GATE_CLOSED_AFTER_FAILED_SWEEP", core._scope_sweep_ok is None, str(core._scope_sweep_ok)[:100])
        # (3) the other 59 DEXes kept their readings: only the dead one is re-read next time
        tries.clear()
        book["dead"] = set()
        os.environ["HL_LIVE_SCOPE_DEX_FRESH_SEC"] = "240"
        res = core.run_scope_sweep()
        check("RECOVERY_REREADS_ONLY_THE_FAILED_DEX", res.get("ok") and set(tries) == {"dex007"}, f"reads={sorted(tries)[:5]} res={str(res)[:120]}")
        check("CLEAN_AGAIN_ALLOWS_ENTRIES", core._scope_sweep_block() == "", core._scope_sweep_block())
        # (4) it keeps failing: the audit says so (after 2 failed sweeps here) and a state file is left
        book["dead"] = {"dex009"}
        os.environ["HL_LIVE_SCOPE_DEX_FRESH_SEC"] = "0"
        core._scope_sweep_ok = None
        core.__dict__["_scope_dex_cache"].pop("dex009", None)
        core.run_scope_sweep()
        core.run_scope_sweep()
        rows = c.read_csv_rows(c.RECONCILIATION_CSV)
        check("REPEATED_FAILURE_WRITES_A_LOUD_ROW", any(r.get("terminal_state") == "SCOPE_SWEEP_FAILING" and "dex009" in str(r.get("notes")) for r in rows),
              str([r.get("terminal_state") for r in rows][-5:]))
        st = c.load_json(Path(c.CORE_RUNTIME_STATE_FILE).parent / "scope_sweep_state.json", {})
        check("STATE_FILE_NAMES_THE_FAILURE", st.get("status") == "SCOPE_UNAVAILABLE" and st.get("dex") == "dex009" and st.get("fail_streak", 0) >= 2, str(st)[:200])
        # (5) a DEX list that shrinks to a fraction is not trusted (it would skip reads and open the gate)
        full = list(DEXES)
        DEXES[:] = DEXES[:5]
        res = core.run_scope_sweep()
        DEXES[:] = full
        check("SHRUNK_DEX_LIST_IS_NOT_TRUSTED", (not res.get("ok")) and res.get("status") == "DEX_ENUM_UNAVAILABLE", str(res)[:160])
        # (6) a restart keeps the readings that are still inside the max-age window: only the unread DEX is read again
        core.__dict__.pop("_scope_dex_cache", None)
        core._scope_cache_loaded = False
        core._scope_sweep_ok = None
        book["dead"] = set()
        os.environ["HL_LIVE_SCOPE_DEX_FRESH_SEC"] = "240"
        tries.clear()
        res = core.run_scope_sweep()
        check("RESTART_KEEPS_RECENT_READINGS", res.get("ok") and set(tries) == {"dex009"}, f"reads={sorted(tries)[:5]} res={str(res)[:120]}")
    finally:
        core.stop()
    failed = [n for n, ok in RESULTS if not ok]
    print(f"TOTAL={len(RESULTS)} FAILED={len(failed)}")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
