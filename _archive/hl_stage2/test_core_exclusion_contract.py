#!/usr/bin/env python3
"""The exclusion's contract at the WRAPPER, and the adopted position it must never close out.

Test 1 pins what the wrapper guarantees when the entry exclusion refuses a fill: exactly ONE terminal
reconciliation row for that leader fill id, the id in the dedupe store and in _idem_accepted exactly once, and no
second pass through _process_leader_fill_inner for that one processing run. A refusal is a final answer, not a retry.

Test 2 pins that an adopted (OPERATOR_ADOPT_OID) position is never excluded from its close: adoption books the ledger
sleeve, and the exclusion refuses to exclude anything with a held net - even when metadata says ENTRY.

Run: python test_core_exclusion_contract.py   # RESULT:: markers, exit 0/1. No network, no orders.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
tmp = Path(tempfile.mkdtemp(prefix="excl_contract_"))
os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LEADER_NETWORK": "testnet", "HL_FOLLOWER_NETWORK": "testnet",
                   "HL_LIVE_ENV_FILE": str(tmp / "none.env"), "HL_LIVE_SCOPE_SWEEP_THREAD": "0",
                   "HL_LIVE_MOCK_SEND": "1"})
import HL_Live_Copy_Service_Core as c  # noqa: E402

RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + str(detail)[:300]) if (detail and not cond) else ""))


LEADER, FOLLOWER = "0x" + "a" * 40, "0x" + "c" * 40
c.USER_WALLET = FOLLOWER
c.MIDS_FETCHER = lambda p: [] if p.get("type") == "perpDexs" else {"MERL": 1.0, "BTC": 100.0}
c.LEADER_MIDS_FETCHER = c.MIDS_FETCHER
EXP = {"assetPositions": [], "marginSummary": {"accountValue": "1000000"}}
c.EXPOSURE_FETCHER = lambda p: [] if p.get("type") == "perpDexs" else dict(EXP)
c.LEADER_FETCHER = c.EXPOSURE_FETCHER
c.follower_volumes_24h = lambda refresh=False, cache_only=False: (True, {"MERL": 61.0}, {"MERL", "BTC"})
c.min_24h_notional_usd = lambda: 3000.0
c.atomic_write_json(c.LIVE_CONFIG_FILE, {
    "auto_send_enabled": False, "global_controls": {"min_notional": 1, "min_24h_notional_usd": 3000.0},
    "wallets": {LEADER: {"enabled": True, "mode": "LIVE", "copy_mode": "fixed", "fixed_notional": 100}}})
core = c.LiveCopyCore(source_csv=tmp / "none.csv")
core._hot_stop_event.set()
for t in core._hot_threads:
    t.join(timeout=2)

core._prewarm_with_parity = lambda *a, **k: None
core.sender.cancel_resting_entries_against = lambda fill: []
sends = []
core.sender.send_if_allowed = lambda intent, reason="": (sends.append(intent.intent_id) or True, "FILLED")
real_build = core.intent_builder.build
inner_calls = []
real_inner = core._process_leader_fill_inner


def counting_inner(fill, summary=None, entry_block_reason=""):
    inner_calls.append(fill.leader_fill_id)
    return real_inner(fill, summary, entry_block_reason)


core._process_leader_fill_inner = counting_inner


def build_as(lifecycle):
    def _b(f):
        intent = real_build(f)
        intent.notes = "lifecycle=%s" % lifecycle
        return intent
    return _b


def rows_for(fid):
    return [r for r in c.read_csv_rows(c.RECONCILIATION_CSV) if r.get("leader_fill_id") == fid]


# ------------------------------------------------ TEST 1: the wrapper contract on a refusal
now = c.utc_now_ms()
f1 = c.LeaderFill("contract-1", LEADER, "MERL", "BUY", 1.0, 1.0, now, "WS_CAPTURED", 0, {"oid": "7", "dir": "Open Long"})
core.intent_builder.build = build_as("ENTRY")
ok, status, _intent = core._process_leader_fill(f1, None, "")

check("A_REFUSED_ENTRY_IS_NOT_SENT", status == "ILLIQUID_SKIP" and not sends,
      "status=%r sends=%r" % (status, sends))
term = [r for r in rows_for("contract-1") if str(r.get("terminal_state") or "")]
check("ONE_TERMINAL_RECONCILIATION_ROW_FOR_THE_REFUSED_FILL", len(term) == 1,
      "rows=%r" % ([(r.get("event"), r.get("status"), r.get("terminal_state")) for r in rows_for("contract-1")],))
check("THE_TERMINAL_ROW_IS_THE_EXCLUSION_ITSELF",
      bool(term) and term[0].get("status") == "ILLIQUID_SKIP" and term[0].get("engine_can_send") == "False",
      "row=%r" % (term[0] if term else None,))
proc = list(core.dedupe.processed)
check("THE_FILL_ID_IS_IN_THE_DEDUPE_STORE_EXACTLY_ONCE", proc.count("contract-1") == 1,
      "count=%d" % (proc.count("contract-1"),))
idem = list(core._idem_accepted)
check("THE_FILL_ID_IS_IN_IDEM_ACCEPTED_EXACTLY_ONCE", idem.count("contract-1") == 1,
      "count=%d" % (idem.count("contract-1"),))
check("THE_INNER_RAN_ONCE_FOR_THE_REFUSED_FILL", inner_calls == ["contract-1"], "inner_calls=%r" % (inner_calls,))

inner_calls.clear()
ok2, status2, _ = core._process_leader_fill(f1, None, "")
check("A_REDELIVERED_REFUSED_FILL_IS_BLOCKED_AS_A_DUPLICATE", ok2 is False and status2 == "DUPLICATE_BLOCKED",
      "status=%r" % (status2,))
term2 = [r for r in rows_for("contract-1") if str(r.get("terminal_state") or "")]
check("A_REDELIVERY_WRITES_NO_SECOND_TERMINAL_ROW", len(term2) == 1, "rows=%r" % (len(term2),))
check("A_REDELIVERY_ADDS_NO_SECOND_IDEM_ENTRY", list(core._idem_accepted).count("contract-1") == 1,
      "count=%d" % (list(core._idem_accepted).count("contract-1"),))

# ------------------------------------------------ TEST 2: an adopted position is never excluded
adopt_wallet, size = LEADER, 10.0
adopt = c.Intent(
    intent_id="adopt-oid:555",
    fill=c.LeaderFill("adopt-oid:555", adopt_wallet, "MERL", "BUY", 1.0, size, now, "OPERATOR_ADOPT_OID"),
    copy_side="BUY", copy_size=size, copy_notional=size, wallet_mode="LIVE", copy_mode="fixed",
    decision="ENTRY_ALLOWED", reason="OPERATOR_ADOPT_OID",
    sleeve_id=c.ManualLedger.sleeve_id(adopt_wallet, "MERL"), position_id="", position_direction_before="",
    wallet_position_before=core.ledger.wallet_coin_position(adopt_wallet, "MERL"),
    coin_net_before=core.ledger.coin_net("MERL"), reduce_only_intended=False, reduce_only_sent_planned=False,
    created_at_ms=now, notes="lifecycle=ENTRY;source=OPERATOR_ADOPT_OID")
core.ledger.apply_copy_fill(adopt, {"copy_fill_id": "cf-adopt-1", "side": "BUY", "size": size, "price": 1.0})
held = core.ledger.wallet_coin_position(adopt_wallet, "MERL")
check("AN_ADOPTED_POSITION_HAS_A_LEDGER_SLEEVE_ROW", held == size, "held=%r" % (held,))
st_held, _n = c.follower_entry_exclusion("MERL", True, {"min_24h_notional_usd": 3000.0}, held_net=held)
check("A_HELD_POSITION_IS_NEVER_EXCLUDED_EVEN_IF_FLAGGED_ENTRY", st_held == "", "status=%r" % (st_held,))

sends.clear()
f2 = c.LeaderFill("contract-2", adopt_wallet, "MERL", "SELL", 1.0, size, c.utc_now_ms(), "WS_CAPTURED", 0,
                  {"oid": "8", "dir": "Close Long"})
core.intent_builder.build = build_as("EXIT")
ok3, status3, _ = core._process_leader_fill(f2, None, "")
bad = [r for r in rows_for("contract-2")
       if r.get("status") in ("ILLIQUID_SKIP", "EXCLUDED_NOT_LISTED_ON_FOLLOWER_NETWORK")]
check("AN_ADOPTED_CLOSE_ON_A_THIN_COIN_IS_NEVER_EXCLUDED", not bad,
      "excluded rows=%r" % ([(r.get("event"), r.get("status")) for r in bad],))
check("THE_ADOPTED_CLOSE_REACHES_THE_SENDER", len(sends) == 1, "sends=%r status=%r" % (sends, status3))

src = (HERE / "HL_Live_Copy_Service_Core.py").read_text(encoding="utf-8", errors="replace")
body = src[src.find("def follower_entry_exclusion"):]
body = body[:body.find("\nclass ", 10)] if "\nclass " in body[10:] else body
check("THE_GUARD_REFUSES_TO_EXCLUDE_A_HELD_NET", "if held_net != 0.0:" in body,
      "follower_entry_exclusion no longer bails out on a non-zero held net")

failed = [n for n, ok in RESULTS if not ok]
print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
if failed:
    print("FAILED: " + ", ".join(failed))
sys.exit(1 if failed else 0)
