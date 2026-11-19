#!/usr/bin/env python3
"""CC-1 R36 (d), T-C slices B/C - DESIRED-behaviour witnesses (RED at base 56ddea4).

Slice B (W1, W9): a replay of a close intent whose sleeve is already FLAT is a consumed sleeve. It must
produce a NAMED no-send (SEND_NOT_ATTEMPTED_STALE_OR_CONSUMED_FLAT_SLEEVE) and EXACTLY ONE durable audit
row - not zero (silent), not two (duplicate terminal), and not an unnamed generic ownership-gate block that
forces manual review for a benign replay.

Slice C (W4D): when the asset is FLAT no engine dust may remain. A close that would leave a remainder below
the venue minimum must instead close the WHOLE owned position (an exact-position close is exempt from the
sub-$10 minimum). The assertion is the END STATE - sleeve exactly zero, no unowned dust - not the branch.

GUT references:
  I05 - every refused/skipped send has exactly ONE durable, NAMED terminal row (no silent skips).
  I06 - a duplicate/replayed intent never yields two terminal rows or two sends for the same intent.
  I23 - the engine holds no position it cannot close: dust below the venue minimum is never left behind.
  CS-I4 - a close is sized to reach the target end state (sleeve exactly flat), not merely the leader size.

Test-only. Run from _archive/hl_stage2:
  HL_LIVE_ENV_FILE=/nonexistent python -u test_core_c7_slices_bc.py
"""
import csv
import os
import sys
import tempfile
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
TMP = Path(tempfile.mkdtemp(prefix="c7_bc_"))
os.environ.update({
    "HL_LIVE_AUDIT_DIR": str(TMP),
    "HL_LIVE_ENV_FILE": "/nonexistent",
    "HL_LEADER_NETWORK": "testnet",
    "HL_FOLLOWER_NETWORK": "testnet",
    "HL_LIVE_GLOBAL_LOCK_FILE": str(TMP / "engine-global.lock"),
})
import HL_Live_Copy_Service_Core as c

# C7-WO-1-R95: the sender now refuses unless the engine ALREADY owns the machine-wide
# lease, so the suite acquires it exactly as the real engine does at start - in an
# ISOLATED temp lock path, never the live machine lock.
c.acquire_global_instance_lock(TMP / "state")

# W4D's *sending* proof requires the same identified follower account.
# W1/W9 must still settle without any exchange read (tested below).
ACCOUNT = "0x" + "c" * 40
os.environ["HL_LIVE_HL_ACCOUNT_ADDRESS"] = ACCOUNT
c.USER_WALLET = ACCOUNT

R = []


def check(name, ok, detail=""):
    R.append(bool(ok))
    print("RESULT::%s_%s%s" % (name, "PASS" if ok else "FAIL", (" | " + str(detail)) if detail and not ok else ""))


def rows_for(intent_id, path):
    if not path.exists() or path.stat().st_size <= 0:
        return []
    with path.open("r", newline="", encoding="utf-8", errors="replace") as f:
        return [r for r in csv.DictReader(f) if str(r.get("intent_id") or "") == intent_id]


W = "0x" + "b" * 40
COIN = "BTC"
MIN = c.DEFAULT_MIN_NOTIONAL
NAMED = "SEND_NOT_ATTEMPTED_STALE_OR_CONSUMED_FLAT_SLEEVE"


def fresh_gateway(tag, ledger_size=0.0, exchange_net=0.0):
    c.atomic_write_json(c.LIVE_CONFIG_FILE, {
        "auto_send_enabled": True,
        "global_controls": {},
        "wallets": {W: {"enabled": True, "mode": "ON"}},
    })
    led = c.ManualLedger(path=TMP / ("led_%s.json" % tag))
    sleeve = led.sleeve(W, COIN)
    sleeve["signed_size"] = float(ledger_size)
    sleeve["direction"] = "FLAT" if abs(ledger_size) <= c.POSITION_EPSILON else ("LONG" if ledger_size > 0 else "SHORT")
    sleeve["opened_by_intent_id"] = "" if abs(ledger_size) <= c.POSITION_EPSILON else "seed"
    led._recompute_net(led.data)
    c.atomic_write_json(c.EXCHANGE_ACCOUNT_SNAPSHOT_FILE,
                        {"positions_by_coin": {COIN: {"signed_size": float(exchange_net)}}})
    return c.SenderGateway(c.ConfigManager(), c.AuditLogWriter(), led), led


def close_intent(intent_id, size, px=100.0):
    fill = c.LeaderFill("fill_" + intent_id, W, COIN, "SELL", px, size, c.utc_now_ms(), "TEST")
    return c.Intent(intent_id, fill, "SELL", size, size * px, "ON", "fixed", "EXIT_ALLOWED", "EXIT",
                    "sleeve", "", "LONG", 1.0, 1.0, True, True, c.utc_now_ms(), "lifecycle=EXIT;")


# ---------------------------------------------------------------- W1
# GUT I05: a replayed close against a consumed (FLAT) sleeve is a NAMED no-send with exactly ONE durable row.
gw1, _ = fresh_gateway("w1", ledger_size=0.0, exchange_net=0.0)
gw1._fresh_exchange_net = lambda _: (_ for _ in ()).throw(AssertionError("W1 requires no exchange read"))
it1 = close_intent("w1_stale_close_replay", 0.05)
sent1 = []
gw1._send_real = lambda intent, timing=None: (sent1.append(intent.intent_id) or (True, "SHOULD_NOT_SEND", {}))
ok1, status1 = gw1.send_if_allowed(it1)
rec1 = rows_for(it1.intent_id, c.RECONCILIATION_CSV)
att1 = rows_for(it1.intent_id, c.SEND_ATTEMPTS_CSV)
check("W1_NO_SEND_AND_NAMED_FLAT_SLEEVE_TERMINAL",
      ok1 is False and status1 == NAMED and sent1 == [] and att1 == [],
      "ok=%r status=%r sends=%r send_attempt_rows=%d" % (ok1, status1, sent1, len(att1)))
check("W1_EXACTLY_ONE_DURABLE_ROW_NAMING_THE_REASON",
      len(rec1) == 1 and rec1[0].get("status") == NAMED and (rec1[0].get("terminal_state") or NAMED) == NAMED,
      "rows=%d statuses=%r" % (len(rec1), [(r.get("status"), r.get("terminal_state")) for r in rec1]))

# ---------------------------------------------------------------- W9
# GUT I06: two simultaneous replays of the SAME intent produce ONE no-send between them, never two rows.
gw9, _ = fresh_gateway("w9", ledger_size=0.0, exchange_net=0.0)
gw9._fresh_exchange_net = lambda _: (_ for _ in ()).throw(AssertionError("W9 requires no exchange read"))
it9 = close_intent("w9_duplicate_stale_replay", 0.05)
sent9 = []
gw9._send_real = lambda intent, timing=None: (sent9.append(intent.intent_id) or (True, "SHOULD_NOT_SEND", {}))
barrier = threading.Barrier(2)
results9 = []


def _replay():
    barrier.wait(timeout=30)
    results9.append(gw9.send_if_allowed(it9))


ts = [threading.Thread(target=_replay) for _ in range(2)]
for t in ts:
    t.start()
for t in ts:
    t.join(timeout=60)
rec9 = rows_for(it9.intent_id, c.RECONCILIATION_CSV)
check("W9_DUPLICATE_REPLAY_YIELDS_ONE_TERMINAL_ROW",
      len(results9) == 2 and all(r[0] is False for r in results9) and len(rec9) == 1 and sent9 == [],
      "threads=%d results=%r rows=%d sends=%d" % (len(results9), [r[1] for r in results9], len(rec9), len(sent9)))
check("W9_THE_ONE_ROW_NAMES_THE_FLAT_SLEEVE_REASON",
      len(rec9) == 1 and rec9[0].get("status") == NAMED,
      "rows=%d statuses=%r" % (len(rec9), [r.get("status") for r in rec9]))

# ---------------------------------------------------------------- W4D
# GUT I23 / CS-I4: the close reaches the target END STATE (sleeve exactly zero); no sub-minimum dust remains.
OWNED = 0.105
LEADER_CLOSE = 0.100
PX = 100.0
gw4, led4 = fresh_gateway("w4d", ledger_size=OWNED, exchange_net=OWNED)
gw4._fresh_exchange_net = lambda coin: OWNED
resolved4 = {"ok": True, "sdk_coin": COIN, "raw_coin": COIN, "min_order_value_usd": MIN}
it4 = close_intent("w4d_dust_end_state", LEADER_CLOSE, PX)
reduce_only, planned, skip = gw4._close_wire_plan(
    it4, LEADER_CLOSE, 3, lambda sz: abs(sz * PX) >= gw4._effective_symbol_min_notional(resolved4), {})
gate_ok, gate_info = (False, {})
if planned and planned > 0 and not skip:
    gate_ok, gate_info = gw4._validate_final_wire_order(it4, dict(resolved4), COIN, planned, PX, {})
sent = planned if (gate_ok and not skip) else 0.0
sleeve_after = OWNED - sent
check("W4D_CLOSE_REACHES_EXACTLY_FLAT_END_STATE",
      gate_ok is True and abs(sleeve_after) <= c.POSITION_EPSILON,
      "gate_ok=%r terminal=%r planned=%r sent=%r sleeve_after=%r"
      % (gate_ok, gate_info.get("terminal_state"), planned, sent, sleeve_after))
check("W4D_NO_UNOWNED_DUST_LEFT_IN_THE_COIN",
      abs(led4.coin_net(COIN) - sent) <= c.POSITION_EPSILON,
      "coin_net_before=%r sent=%r" % (led4.coin_net(COIN), sent))
check("W4D_CLOSE_IS_REDUCE_ONLY_SO_IT_CANNOT_FLIP", reduce_only is True, "reduce_only=%r" % (reduce_only,))

print("TOTAL=%d FAILED=%d" % (len(R), R.count(False)))
sys.exit(1 if False in R else 0)
