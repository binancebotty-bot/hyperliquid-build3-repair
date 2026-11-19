#!/usr/bin/env python3
"""DOOR_3: a fill claimed by a run that died before its live_fills row must not strand the position.

claim_copy_fill_process_marker (Core L4272) creates AUDIT_DIR/copy_fill_claims/<id>.claim and nothing ever
releases it. A crash between that claim and the live_fills append leaves the fill with a claim and no ledger row,
so the retry of that SAME fill is refused as a duplicate (COPY_FILL_XPROC_DEDUPE_WINAGENT) forever: no
live_fills row -> _proven_owned_for_sleeve proves 0 -> every close HOLDs CLOSE_PROOF_HOLD_NO_OWNED_SLEEVE while
the sleeve still holds 2.0. The position is stranded. The startup sweep releases exactly those claims.

FAILING FIRST on d369a9d3: no release exists, so the claim survives the restart and the close is refused.

Real marker writer, real ManualLedger.save, real AuditLogWriter.append_live_fill, real
SenderGateway._proven_owned_for_sleeve and real SenderGateway._close_wire_plan. Only the exchange net read is
faked. Own temp state dir, testnet, offline.
Run (from _archive/hl_stage2): HL_LIVE_ENV_FILE=/nonexistent python -u test_door3_orphan_claim_sweep.py
"""
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
TMP = Path(tempfile.mkdtemp(prefix="door3_claim_sweep_"))
WALLET_A = "0x" + "a" * 40   # the leader whose fill crashed between the claim and the live_fills append
WALLET_B = "0x" + "b" * 40   # another sleeve on the coin: nets the account UNDER A's owned size
os.environ.update({
    "HL_LIVE_AUDIT_DIR": str(TMP), "HL_LIVE_ENV_FILE": str(TMP / "missing.env"),
    "HL_LEADER_NETWORK": "testnet", "HL_FOLLOWER_NETWORK": "testnet",
    "HL_USER_WALLET": WALLET_A, "HL_LIVE_SCOPE_SWEEP_THREAD": "0",
})
for _k in ("HL_LIVE_HL_PRIVATE_KEY", "HL_LIVE_HL_ACCOUNT_ADDRESS"):
    os.environ.pop(_k, None)
sys.path.insert(0, str(HERE))
import HL_Live_Copy_Service_Core as c  # noqa: E402

FID = "0xdoor3c0ffee:9001"
COIN = "RESOLV"
R = []


def check(name, ok, detail=""):
    R.append((name, bool(ok)))
    print(("PASS " if ok else "FAIL ") + name + ((" | " + str(detail)[:220]) if not ok else ""))
    print("RESULT::%s_%s" % (name, "PASS" if ok else "FAIL"))


def claim_file(fid):
    return c.AUDIT_DIR / "copy_fill_claims" / (c._safe_marker_name(fid) + ".claim")


def close_plan(size=2.0):
    """Real proof and real plan: only the exchange net (1.5, netted by the other sleeve) is faked."""
    esc = []
    me = SimpleNamespace(ledger=c.ManualLedger(),
                         cfg=SimpleNamespace(wallet_mode=lambda w: "ON", send_mode_now=lambda: "ON"))
    me.FILL_PROOF_REPAIR_SOURCES = c.SenderGateway.FILL_PROOF_REPAIR_SOURCES
    me._fill_proof_for_sleeve = lambda w, k: c.SenderGateway._fill_proof_for_sleeve(me, w, k)
    me._proven_owned_for_sleeve = lambda w, k: c.SenderGateway._proven_owned_for_sleeve(me, w, k)
    me._close_proof_account_ok = lambda: True
    me._follower_order_account_for_proof = lambda *a, **k: c.USER_WALLET
    me._reduce_only_for_intent = lambda i: True
    me._fresh_exchange_net = lambda coin: 1.5
    me._floor_wire_size = c.SenderGateway._floor_wire_size
    me._open_close_escalation = lambda intent, reason: esc.append(reason)
    intent = SimpleNamespace(fill=SimpleNamespace(leader_wallet=WALLET_A, coin=COIN, leader_fill_id="lf-door3"),
                             copy_side="SELL", copy_size=size, intent_id="i-door3")
    timing = {}
    return c.SenderGateway._close_wire_plan(me, intent, size, 2, lambda s: True, timing, False), timing, esc


# --- the crash left a persisted 2.0 sleeve and a claim, with ZERO live_fills rows -------------------------
led = c.ManualLedger()
led.sleeve(WALLET_A, COIN).update(signed_size=2.0, direction="LONG", avg_entry_px=10.0,
                                  opened_by_intent_id="i-door3", last_copy_fill_id="")
led.sleeve(WALLET_B, COIN).update(signed_size=-0.5, direction="SHORT", avg_entry_px=10.0,
                                  opened_by_intent_id="i-b")
led._recompute_net(led.data)
led.save()
claimed = c.claim_copy_fill_process_marker(FID)
check("SETUP_SLEEVE_PERSISTED_WITH_ZERO_LIVE_FILL_ROWS",
      abs(c.ManualLedger().wallet_coin_position(WALLET_A, COIN) - 2.0) < 1e-12 and claimed
      and claim_file(FID).exists() and not c.LIVE_FILLS_CSV.exists(), str(c.LIVE_FILLS_CSV.exists()))

core = c.LiveCopyCore(source_csv=TMP / "none.csv")

# --- the startup sweep -----------------------------------------------------------------------------------
core._release_orphan_fill_claims()   # RED: comment this line out - the claim survives the restart
check("SWEEP_RELEASES_A_CLAIM_WITH_NO_LIVE_FILLS_ROW", not claim_file(FID).exists(),
      claim_file(FID).read_text(encoding="utf-8") if claim_file(FID).exists() else "")

# --- the retry the claim used to block forever -----------------------------------------------------------
retry_claimed = c.claim_copy_fill_process_marker(FID)
row = {k: "" for k in c.LIVE_FILL_FIELDS}
row.update(created_at=c.utc_now_iso(), created_at_ms=c.utc_now_ms(), copy_fill_id=FID, intent_id="i-door3",
           leader_fill_id="lf-door3", leader_wallet=WALLET_A,
           sleeve_id=c.ManualLedger.sleeve_id(WALLET_A, COIN), coin=COIN, side="BUY",
           fill_price="9.9", fill_size="2.0", fill_notional="19.8", source="COPY_FILL",
           exchange_hash="0xdoor3c0ffee", exchange_order_id="4711", ledger_action="ENTRY")
if retry_claimed:
    c.AuditLogWriter().append_live_fill(row)
check("RETRY_CLAIMS_THE_FILL_ONCE_THE_ORPHAN_CLAIM_IS_GONE", retry_claimed)
rows = [r for r in c.read_csv_rows(c.LIVE_FILLS_CSV) if r.get("copy_fill_id") == FID]
check("RETRY_WRITES_THE_LIVE_FILLS_ROW", len(rows) == 1, str(len(rows)))

plan, timing, esc = close_plan()
check("CLOSE_SUCCEEDS_AT_OWNED_SIZE_REDUCE_ONLY_FALSE",
      plan == (False, 2.0, "") and timing.get("close_proven_from") == "fills"
      and abs(float(timing.get("close_proven_owned") or 0.0) - 2.0) < 1e-9, str((plan, timing, esc)))

# --- a claim whose fill IS in the ledger is kept: the sweep only releases orphans -------------------------
kept_had_row = claim_file(FID).exists()
n1, n2 = core._release_orphan_fill_claims(), core._release_orphan_fill_claims()
check("SWEEP_IS_IDEMPOTENT_AND_KEEPS_A_CLAIM_THAT_HAS_A_LIVE_FILLS_ROW",
      kept_had_row and n1 == 0 and n2 == 0 and claim_file(FID).exists(),
      str((kept_had_row, n1, n2, claim_file(FID).exists())))

# --- an unreadable live_fills read keeps every claim and never raises --------------------------------------
FID2 = "0xdoor3dead:9002"
c.claim_copy_fill_process_marker(FID2)
_real_read = c.read_csv_rows
c.read_csv_rows = lambda path: (_ for _ in ()).throw(OSError("live_fills unreadable"))
try:
    kept, raised = core._release_orphan_fill_claims(), False
except Exception:
    kept, raised = None, True
finally:
    c.read_csv_rows = _real_read
check("UNREADABLE_LIVE_FILLS_KEEPS_THE_CLAIM_AND_NEVER_RAISES",
      not raised and kept == 0 and claim_file(FID2).exists(), str((kept, raised)))

failed = [n for n, ok in R if not ok]
print("TOTAL=%d FAILED=%d" % (len(R), len(failed)))
raise SystemExit(1 if failed else 0)
