#!/usr/bin/env python3
"""DOOR_3: release a copy-fill claim ONLY on durable proof of absence; fail closed on anything unknown.

claim_copy_fill_process_marker writes AUDIT_DIR/copy_fill_claims/<id>.claim BEFORE the ledger commit and a
successful apply never removes it. A crash between the claim and the commit leaves the fill unclaimable forever
(COPY_FILL_XPROC_DEDUPE_WINAGENT): no live_fills row -> _proven_owned_for_sleeve proves 0 -> every close HOLDs
while the sleeve still holds 2.0. The startup sweep releases exactly those claims - but live_fills.csv ROTATES,
so a fill that WAS applied and whose row rotated away looks identical to a crash orphan. Releasing that claim
re-applies the fill on the next poll (matched_copy_fill_ids only protects a live process) and double-counts the
position in the ledger. So absence is proven only against the durable, non-rotating applied_copy_fill_ids.jsonl,
and every unreadable/empty/ambiguous state keeps the claim.

Real marker writer, real ManualLedger (the durable commit), real AuditLogWriter.append_live_fill, real
CopyFillMatcher rebuild, real SenderGateway._close_wire_plan. Only the exchange net read is faked.
Own temp state dir, testnet, offline.
Run (from _archive/hl_stage2): HL_LIVE_ENV_FILE=/nonexistent python -u test_door3_orphan_claim_sweep.py
"""
import ast
import inspect
import os
import sys
import tempfile
import textwrap
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
    print(("PASS " if ok else "FAIL ") + name + ((" | " + str(detail)[:240]) if not ok else ""))
    print("RESULT::%s_%s" % (name, "PASS" if ok else "FAIL"))


def claim_file(fid):
    return c.AUDIT_DIR / "copy_fill_claims" / (c._safe_marker_name(fid) + ".claim")


def fill_row(fid, coin="OTHER", size="1.0", side="BUY", wallet=WALLET_B):
    row = {k: "" for k in c.LIVE_FILL_FIELDS}
    row.update(created_at=c.utc_now_iso(), created_at_ms=c.utc_now_ms(), copy_fill_id=fid,
               leader_wallet=wallet, sleeve_id=c.ManualLedger.sleeve_id(wallet, coin), coin=coin,
               side=side, fill_price="10.0", fill_size=size, fill_notional="10.0", fee="0.0",
               source="COPY_FILL", ledger_action="ENTRY")
    return row


def current_live_ids():
    return {str(r.get("copy_fill_id") or "") for r in c.read_csv_rows(c.LIVE_FILLS_CSV)}


def rotate_live_fills():
    """Move the current file aside exactly as the audit rotator does and let the next fill start a fresh one."""
    p = c.LIVE_FILLS_CSV
    dest = p.with_name("%s.20260101.1.csv" % p.stem)
    c._close_audit_handle(p)  # the rotator does this first: Windows cannot rename a file with an open append handle
    os.replace(str(p), str(dest))
    c.append_csv(p, c.LIVE_FILL_FIELDS, fill_row("0xafter-rotation:1", coin="ROT"))
    return dest


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


# --- 1. the crash: a claim with ZERO live_fills rows, the sleeve still holding 2.0 ------------------------
led = c.ManualLedger()
led.sleeve(WALLET_A, COIN).update(signed_size=2.0, direction="LONG", avg_entry_px=10.0,
                                  opened_by_intent_id="i-door3", last_copy_fill_id="")
led.sleeve(WALLET_B, COIN).update(signed_size=-0.5, direction="SHORT", avg_entry_px=10.0,
                                  opened_by_intent_id="i-b")
led._recompute_net(led.data)
led.save()
claimed = c.claim_copy_fill_process_marker(FID)
c.append_csv(c.LIVE_FILLS_CSV, c.LIVE_FILL_FIELDS, fill_row("0xother:1"))  # live_fills is a live record
check("SETUP_CRASH_LEFT_A_CLAIM_WITH_NO_ROW_FOR_THAT_FILL",
      claimed and claim_file(FID).exists() and FID not in current_live_ids()
      and abs(c.ManualLedger().wallet_coin_position(WALLET_A, COIN) - 2.0) < 1e-12,
      (claimed, claim_file(FID).exists(), FID in current_live_ids()))

core = c.LiveCopyCore(source_csv=TMP / "none.csv")

released = core._release_orphan_fill_claims()
check("SWEEP_RELEASES_A_CLAIM_ABSENT_FROM_THE_DURABLE_RECORD",
      released == 1 and not claim_file(FID).exists(), released)

retry_claimed = c.claim_copy_fill_process_marker(FID)
if retry_claimed:
    c.AuditLogWriter().append_live_fill(fill_row(FID, coin=COIN, size="2.0", wallet=WALLET_A))
check("RETRY_CLAIMS_THE_FILL_ONCE_THE_ORPHAN_CLAIM_IS_GONE", retry_claimed)
rows = [r for r in c.read_csv_rows(c.LIVE_FILLS_CSV) if r.get("copy_fill_id") == FID]
check("RETRY_WRITES_THE_LIVE_FILLS_ROW", len(rows) == 1, str(len(rows)))

plan, timing, esc = close_plan()
check("CLOSE_SUCCEEDS_AT_OWNED_SIZE_REDUCE_ONLY_FALSE",
      plan == (False, 2.0, "") and timing.get("close_proven_from") == "fills"
      and abs(float(timing.get("close_proven_owned") or 0.0) - 2.0) < 1e-9, str((plan, timing, esc)))

n1, n2 = core._release_orphan_fill_claims(), core._release_orphan_fill_claims()
check("SWEEP_IS_IDEMPOTENT_AND_KEEPS_A_CLAIM_THAT_HAS_A_ROW",
      n1 == 0 and n2 == 0 and claim_file(FID).exists(), str((n1, n2, claim_file(FID).exists())))

# --- 2. ROTATION: applied, row rotated away, no claim release, no second apply ----------------------------
FID2 = "0xrotated:7001"
c.claim_copy_fill_process_marker(FID2)
intent2 = SimpleNamespace(
    fill=SimpleNamespace(leader_wallet=WALLET_A, coin=COIN, leader_fill_id="lf-rot", price=10.0,
                         timestamp_ms=c.utc_now_ms()),
    intent_id="i-rot", copy_side="SELL", copy_size=1.0)
c.ManualLedger().apply_copy_fill(intent2, {"copy_fill_id": FID2, "side": "SELL", "size": 1.0, "price": 10.0})
c.AuditLogWriter().append_live_fill(fill_row(FID2, coin=COIN, size="1.0", side="SELL", wallet=WALLET_A))
durable, why_unknown = c.applied_copy_fill_ids_read()
rotated_to = rotate_live_fills()
check("SETUP_ROTATION_LEFT_THE_APPLIED_FILL_OUT_OF_THE_CURRENT_CSV",
      rotated_to.exists() and durable is not None and FID2 in durable and FID2 not in current_live_ids()
      and claim_file(FID2).exists(), str((rotated_to.exists(), why_unknown, FID2 in (durable or set()))))

released = core._release_orphan_fill_claims()
check("ROTATED_APPLIED_FILL_KEEPS_ITS_CLAIM_ON_DURABLE_PROOF",
      released == 0 and claim_file(FID2).exists(), str((released, claim_file(FID2).exists())))

matcher = c.CopyFillMatcher(c.ManualLedger(), c.AuditLogWriter())  # the restart: rebuilt from the rotating CSV
before_replay = c.ManualLedger().wallet_coin_position(WALLET_A, COIN)
replay = c.claim_copy_fill_process_marker(FID2)
if replay:  # the bug: only a retained claim stops this second apply now
    c.ManualLedger().apply_copy_fill(intent2, {"copy_fill_id": FID2, "side": "SELL", "size": 1.0, "price": 10.0})
after_replay = c.ManualLedger().wallet_coin_position(WALLET_A, COIN)
check("ROTATION_REPLAY_IS_BLOCKED_AND_THE_LEDGER_IS_NOT_DOUBLE_COUNTED",
      FID2 not in matcher.matched_copy_fill_ids and not replay and abs(after_replay - before_replay) < 1e-12,
      str((FID2 in matcher.matched_copy_fill_ids, replay, before_replay, after_replay)))

# --- 3. garbage / truncated live_fills: UNKNOWN, never absence ------------------------------------------
FID3 = "0xgarbagecsv:3001"
c.claim_copy_fill_process_marker(FID3)
saved = c.LIVE_FILLS_CSV.read_bytes()
c.LIVE_FILLS_CSV.write_bytes(b"\x00\xff\xfe not a csv at all\r\n" * 3)
try:
    released, raised = core._release_orphan_fill_claims(), False
except Exception:
    released, raised = None, True
check("GARBAGE_LIVE_FILLS_KEEPS_EVERY_CLAIM",
      not raised and released == 0 and claim_file(FID3).exists() and claim_file(FID2).exists(),
      str((released, raised)))
c.LIVE_FILLS_CSV.write_bytes(saved)
claim_file(FID3).unlink()

# --- 4. a row-less live_fills is exactly what a rotation leaves: keep every claim ------------------------
FID4 = "0xzerorows:4001"
c.claim_copy_fill_process_marker(FID4)
saved = c.LIVE_FILLS_CSV.read_bytes()
c.LIVE_FILLS_CSV.write_bytes(saved.split(b"\r\n")[0] + b"\r\n")  # header only, zero rows
released = core._release_orphan_fill_claims()
check("ZERO_ROW_LIVE_FILLS_KEEPS_EVERY_CLAIM",
      released == 0 and claim_file(FID4).exists() and claim_file(FID2).exists(), str(released))
c.LIVE_FILLS_CSV.write_bytes(saved)
claim_file(FID4).unlink()

# --- 5. the claim's OWN id is unreadable: the mangled filename stem is not an id -------------------------
FID5 = "0xmalformed:5001"
bad = claim_file(FID5)
bad.parent.mkdir(parents=True, exist_ok=True)
bad.write_bytes(b"\x00\x00 no id in here")
FID5b = "0xemptyid:5002"
bad2 = claim_file(FID5b)
bad2.write_text("copy_fill_id=\nclaimed_at=x\n", encoding="utf-8")
released = core._release_orphan_fill_claims()
check("MALFORMED_CLAIM_FILE_IS_KEPT", released == 0 and bad.exists(), str((released, bad.exists())))
check("EMPTY_CLAIM_ID_IS_KEPT", bad2.exists(), str(bad2.exists()))
bad.unlink()
bad2.unlink()

# --- 6. unreadable live_fills read: keeps every claim and never raises ----------------------------------
FID6 = "0xunreadable:6001"
c.claim_copy_fill_process_marker(FID6)
_real_read = c.read_csv_rows
c.read_csv_rows = lambda path: (_ for _ in ()).throw(OSError("live_fills unreadable"))
try:
    kept, raised = core._release_orphan_fill_claims(), False
except Exception:
    kept, raised = None, True
finally:
    c.read_csv_rows = _real_read
check("UNREADABLE_LIVE_FILLS_KEEPS_EVERY_CLAIM_AND_NEVER_RAISES",
      not raised and kept == 0 and claim_file(FID6).exists(), str((kept, raised)))
claim_file(FID6).unlink()

# --- 7. a durable index whose append failed proves nothing ----------------------------------------------
FID7 = "0xbrokenindex:7001"
c.claim_copy_fill_process_marker(FID7)
c._applied_copy_fill_ids_broken_path().write_text("append failed: disk full\n", encoding="utf-8")
released = core._release_orphan_fill_claims()
check("BROKEN_DURABLE_INDEX_KEEPS_EVERY_CLAIM", released == 0 and claim_file(FID7).exists(), str(released))
c._applied_copy_fill_ids_broken_path().unlink()
claim_file(FID7).unlink()

# --- 8. the proof source and the startup call site (the test used to call the sweep itself) --------------
sweep_src = inspect.getsource(c.LiveCopyCore._release_orphan_fill_claims)
_sweep_fn = ast.parse(textwrap.dedent(sweep_src)).body[0]
_sweep_code = "\n".join(ast.unparse(node) for node in _sweep_fn.body[1:])  # the code, without its docstring
check("SWEEP_PROOF_COMES_FROM_THE_DURABLE_INDEX_NOT_THE_ORDER_ID",
      "applied_copy_fill_ids_read" in _sweep_code and "exchange_order_id" not in _sweep_code, _sweep_code[:200])


def main_calls_the_sweep():
    """Does main()'s own startup sequence call the sweep? Read from the module this test imported, so removing the
    call (or pointing the test at a scratch copy without it) fails here instead of passing silently."""
    tree = ast.parse(Path(c.__file__).read_text(encoding="utf-8-sig"))
    main_fn = next((n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main"), None)
    if main_fn is None:
        return False
    return any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
               and n.func.attr == "_release_orphan_fill_claims" for n in ast.walk(main_fn))


check("MAIN_STARTUP_SEQUENCE_CALLS_THE_SWEEP", main_calls_the_sweep())

failed = [n for n, ok in R if not ok]
print("TOTAL=%d FAILED=%d" % (len(R), len(failed)))
raise SystemExit(1 if failed else 0)
