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

Two phases: `pending` is fsynced BEFORE the ledger commit (an unwritable index ABORTS the apply, ledger
untouched); `applied` is appended after the commit. A pending record with no applied record means "may or may not
be applied", so it keeps the claim AND alerts - only `applied` (or a live_fills row) permits a release. An ABSENT
index is UNKNOWN, never "nothing was applied", and is never seeded-and-trusted here (the history seed omits every
rotated-out fill).

The call site is checked structurally: main() must contain the sweep call as an UNCONDITIONAL statement in its
own body, BEFORE the first poll/thread start - `if False: core._release_orphan_fill_claims()` must be rejected,
and so must the same call moved after the poll.

Real marker writer, real ManualLedger (the durable commit), real AuditLogWriter.append_live_fill, real
CopyFillMatcher rebuild, real SenderGateway._close_wire_plan. Only the exchange net read is faked.
Own temp state dir, testnet, offline.
Run (from _archive/hl_stage2): HL_LIVE_ENV_FILE=/nonexistent python -u test_door3_orphan_claim_sweep.py
"""
import ast
import copy
import hashlib
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
MR = []  # mutant results: these are EXPECTED to fail, and are asserted to be False


def check(name, ok, detail=""):
    R.append((name, bool(ok)))
    print(("PASS " if ok else "FAIL ") + name + ((" | " + str(detail)[:240]) if not ok else ""))
    print("RESULT::%s_%s" % (name, "PASS" if ok else "FAIL"))


def mcheck(name, ok, detail=""):
    """A check run against the MUTANT sweep. Recorded separately: the mutant is supposed to break it."""
    MR.append((name, bool(ok)))
    print(("PASS " if ok else "FAIL ") + name + " [MUTANT recorded=set()]"
          + ((" | " + str(detail)[:240]) if not ok else ""))
    print("RESULT::%s_%s" % (name, "PASS" if ok else "FAIL"))


def claim_file(fid):
    return c.AUDIT_DIR / "copy_fill_claims" / (c._safe_marker_name(fid) + ".claim")


def all_claims():
    return sorted(p.name for p in (c.AUDIT_DIR / "copy_fill_claims").glob("*.claim"))


def alert_seen(token):
    """A kept claim must be visible: _orphan_claim_alert writes an ALERT row with the token as its status."""
    try:
        for row in c.read_csv_rows(c.RECONCILIATION_CSV):
            if token in (str(row.get("status") or ""), str(row.get("terminal_state") or "")):
                return True
    except Exception:
        pass
    return False


def ledger_fingerprint():
    """The ledger file's bytes AND the position a replay would move: an aborted apply must change neither."""
    p = c.ManualLedger().path
    digest = hashlib.sha256(p.read_bytes()).hexdigest()[:16] if p.exists() else "absent"
    return digest, c.ManualLedger().wallet_coin_position(WALLET_A, COIN)


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


def fill_intent(tag, size=1.0):
    return SimpleNamespace(
        fill=SimpleNamespace(leader_wallet=WALLET_A, coin=COIN, leader_fill_id="lf-" + tag, price=10.0,
                             timestamp_ms=c.utc_now_ms()),
        intent_id="i-" + tag, copy_side="SELL", copy_size=size)


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
# this build's own durable index, already written by the one fill it has applied (pending then applied)
c.note_pending_copy_fill("0xother:1")
c.note_applied_copy_fill("0xother:1")
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


def replayed_rows(fid):
    return [r for r in c.read_csv_rows(c.LIVE_FILLS_CSV) if r.get("copy_fill_id") == fid]
plan, timing, esc = close_plan()
check("CLOSE_SUCCEEDS_AT_OWNED_SIZE_REDUCE_ONLY_FALSE",
      plan == (False, 2.0, "") and timing.get("close_proven_from") == "fills"
      and abs(float(timing.get("close_proven_owned") or 0.0) - 2.0) < 1e-9, str((plan, timing, esc)))

n1, n2 = core._release_orphan_fill_claims(), core._release_orphan_fill_claims()
check("SWEEP_IS_IDEMPOTENT_AND_KEEPS_A_CLAIM_THAT_HAS_A_ROW",
      n1 == 0 and n2 == 0 and claim_file(FID).exists(), str((n1, n2, claim_file(FID).exists())))

# --- 2. ROTATION: applied, row rotated away, no claim release, no second apply ---------------------------
FID2 = "0xrotated:7001"
c.claim_copy_fill_process_marker(FID2)
intent2 = fill_intent("rot")
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
print("REPLAY_LEDGER_BEFORE=%r REPLAY_LEDGER_AFTER=%r REPLAY_ALLOWED=%r ROWS_FOR_FILL=%d"
      % (before_replay, after_replay, bool(replay), len(replayed_rows(FID2))))
check("ROTATION_REPLAY_IS_BLOCKED_AND_THE_LEDGER_IS_NOT_DOUBLE_COUNTED",
      FID2 not in matcher.matched_copy_fill_ids and not replay and abs(after_replay - before_replay) < 1e-12,
      str((FID2 in matcher.matched_copy_fill_ids, replay, before_replay, after_replay)))

# --- 2b. a PENDING record with no applied record: keep the claim AND alert, never replay ------------------
FIDP = "0xpending:7101"
c.claim_copy_fill_process_marker(FIDP)
c.note_pending_copy_fill(FIDP)  # phase 1 only: the commit may or may not have happened
released_pending = core._release_orphan_fill_claims()
check("PENDING_RECORD_KEEPS_THE_CLAIM", released_pending == 0 and claim_file(FIDP).exists(),
      str((released_pending, claim_file(FIDP).exists())))
check("PENDING_RECORD_ALERTS", alert_seen("CLAIM_KEPT_PENDING_APPLIED_FILL_RECORD"),
      "no CLAIM_KEPT_PENDING_APPLIED_FILL_RECORD row in the reconciliation log")
check("PENDING_RECORD_DOES_NOT_PERMIT_A_REPLAY", not c.claim_copy_fill_process_marker(FIDP))

# --- 3. garbage / truncated live_fills: UNKNOWN, never absence -------------------------------------------
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

# --- 4. a row-less live_fills is exactly what a rotation leaves: keep every claim -------------------------
FID4 = "0xzerorows:4001"
c.claim_copy_fill_process_marker(FID4)
saved = c.LIVE_FILLS_CSV.read_bytes()
c.LIVE_FILLS_CSV.write_bytes(saved.split(b"\r\n")[0] + b"\r\n")  # header only, zero rows
released = core._release_orphan_fill_claims()
check("ZERO_ROW_LIVE_FILLS_KEEPS_EVERY_CLAIM",
      released == 0 and claim_file(FID4).exists() and claim_file(FID2).exists(), released)
c.LIVE_FILLS_CSV.write_bytes(saved)
claim_file(FID4).unlink()

# --- 5. the claim's OWN id is unreadable: the mangled filename stem is not an id ---------------------------
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

# --- 6. unreadable live_fills read: keeps every claim and never raises ------------------------------------
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

# --- 7. a durable index whose append failed proves nothing -----------------------------------------------
FID7 = "0xbrokenindex:7001"
c.claim_copy_fill_process_marker(FID7)
c._applied_copy_fill_ids_broken_path().write_text("append failed: disk full\n", encoding="utf-8")
released = core._release_orphan_fill_claims()
check("BROKEN_DURABLE_INDEX_KEEPS_EVERY_CLAIM", released == 0 and claim_file(FID7).exists(), str(released))
c._applied_copy_fill_ids_broken_path().unlink()
claim_file(FID7).unlink()

# --- 7b. the index UNWRITABLE: the apply REFUSES and the ledger does not move ----------------------------
FIDU = "0xunwritable:7501"
idx = c.applied_copy_fill_ids_path()
saved_index = idx.read_bytes()
idx.unlink()
idx.mkdir()  # a directory where the append-only file must be: open(path, "a") cannot succeed against it
try:
    before_fp = ledger_fingerprint()
    try:
        c.ManualLedger().apply_copy_fill(fill_intent("unw"), {"copy_fill_id": FIDU, "side": "SELL",
                                                              "size": 1.0, "price": 10.0})
        refused, err = False, "apply_copy_fill returned instead of raising"
    except c.AppliedFillRecordUnwritable as exc:
        refused, err = True, str(exc)
    except Exception as exc:  # any other refusal is not the named one: fail this check
        refused, err = False, "%s: %s" % (type(exc).__name__, exc)
    after_fp = ledger_fingerprint()
finally:
    idx.rmdir()
    idx.write_bytes(saved_index)
    try:
        c._applied_copy_fill_ids_broken_path().unlink()  # the refused apply marks the index broken; clear it
    except FileNotFoundError:
        pass
check("UNWRITABLE_INDEX_ABORTS_THE_APPLY_WITH_A_NAMED_ERROR",
      refused and err.startswith("APPLIED_FILL_RECORD_UNWRITABLE"), err)
check("ABORTED_APPLY_DOES_NOT_MOVE_THE_LEDGER", before_fp == after_fp, str((before_fp, after_fp)))
check("ABORTED_APPLY_LEAVES_NO_APPLIED_RECORD_FOR_THE_FILL",
      FIDU not in (c.applied_copy_fill_ids_read()[0] or set()), str(c.applied_copy_fill_ids_read()[1]))

# --- 7c. the index ABSENT while claims exist: keep EVERY claim, alert, and do not seed-and-release -------
claims_before = all_claims()
saved_index = idx.read_bytes()
idx.unlink()
released = core._release_orphan_fill_claims()
claims_after = all_claims()
reseeding = idx.exists()  # a sweep that seeded here would have re-created the index from the rotating history
check("INDEX_ABSENT_KEEPS_EVERY_CLAIM",
      released == 0 and claims_before == claims_after and len(claims_after) >= 2,
      str((released, claims_before, claims_after)))
check("INDEX_ABSENT_ALERTS_CLAIM_RELEASE_REFUSED_INDEX_ABSENT",
      alert_seen("CLAIM_RELEASE_REFUSED_INDEX_ABSENT") and not reseeding, str(reseeding))
idx.write_bytes(saved_index)

# --- 8. the proof source and the startup call site (the test used to call the sweep itself) --------------
sweep_src = inspect.getsource(c.release_orphan_fill_claims)
_sweep_fn = ast.parse(textwrap.dedent(sweep_src)).body[0]
_sweep_code = "\n".join(ast.unparse(node) for node in _sweep_fn.body[1:])  # the code, without its docstring
check("SWEEP_PROOF_COMES_FROM_THE_DURABLE_INDEX_NOT_THE_ORDER_ID",
      ("applied_copy_fill_ids_scan" in _sweep_code or "applied_copy_fill_ids_read" in _sweep_code)
      and "exchange_order_id" not in _sweep_code, _sweep_code[:200])

SWEEP_NAMES = {"release_orphan_fill_claims", "_release_orphan_fill_claims"}
POLL_ATTRS = {"start", "start_copy_poll_thread", "start_convergence_thread", "start_hot_workers", "start_ws",
             "poll_copy", "run_forever", "Thread", "start_new_thread", "ThreadPoolExecutor"}


def is_sweep_call(node):
    """core._release_orphan_fill_claims() and the module-level release_orphan_fill_claims(): the same sweep."""
    if not isinstance(node, ast.Call):
        return False
    f = node.func
    name = f.attr if isinstance(f, ast.Attribute) else (f.id if isinstance(f, ast.Name) else "")
    return name in SWEEP_NAMES


def top_level_sweep_index(fn):
    """The sweep as an UNCONDITIONAL statement directly in fn.body, or None. A statement nested in an If
    (`if False:`), While, For, Try or With never runs, so the old ast.walk() check could be fooled by it."""
    for i, stmt in enumerate(fn.body):
        if isinstance(stmt, ast.Expr) and is_sweep_call(stmt.value):
            return i
    return None


def wrapped_sweep_index(fn):
    """The sweep present but NOT as an unconditional statement of fn.body - the too-weak match the old check used."""
    for i, stmt in enumerate(fn.body):
        if isinstance(stmt, ast.Expr) and is_sweep_call(stmt.value):
            continue
        if any(is_sweep_call(n) for n in ast.walk(stmt)):
            return i
    return None


def starts_a_poll_or_thread(stmt):
    for node in ast.walk(stmt):
        if isinstance(node, ast.Call):
            f = node.func
            name = f.attr if isinstance(f, ast.Attribute) else (f.id if isinstance(f, ast.Name) else "")
            if name in POLL_ATTRS:
                return True
    return False


def poll_start_index(fn):
    for i, stmt in enumerate(fn.body):
        if starts_a_poll_or_thread(stmt):
            return i
    return None


def check_call_site(fn):
    """(ok, reason). The call must be an unconditional statement in main()'s own body AND come before the first
    poll/thread start: a sweep that runs after the first poll can release a claim the running poll already used."""
    if fn is None:
        return False, "main() is missing"
    idx = top_level_sweep_index(fn)
    if idx is None:
        wrapped = wrapped_sweep_index(fn)
        if wrapped is not None:
            return False, ("the sweep call is nested inside `%s` (statement %d), not an unconditional statement of "
                           "main()'s body" % (ast.unparse(fn.body[wrapped]).split(chr(10))[0][:80], wrapped))
        return False, "main() has no release_orphan_fill_claims() call"
    poll = poll_start_index(fn)
    if poll is None:
        return False, "no poll/thread start found in main(), so the ordering cannot be proven"
    if idx > poll:
        return False, ("the sweep call (statement %d) runs AFTER the first poll/thread start (statement %d: `%s`)"
                       % (idx, poll, ast.unparse(fn.body[poll]).split(chr(10))[0][:80]))
    return True, "statement %d < first poll/thread start %d" % (idx, poll)


def main_function():
    tree = ast.parse(Path(c.__file__).read_text(encoding="utf-8-sig"))
    return next((n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main"), None)


def mutated_main(kind):
    """The real main() with the sweep call wrapped in `if False:` or moved after the poll - the two shapes the
    old check passed. Built from the module this test imported, so the defect is real, not hypothetical."""
    fn = copy.deepcopy(main_function())
    idx = top_level_sweep_index(fn)
    if kind in ("if_false", "reviewer_if_false"):
        call = ("core._release_orphan_fill_claims()" if kind == "reviewer_if_false"
                else ast.unparse(fn.body[idx]))
        fn.body[idx] = ast.parse("if False:\n    " + call).body[0]
    elif kind == "after_poll":
        stmt = fn.body[idx]
        poll = next(s for s in fn.body if starts_a_poll_or_thread(s))
        body = [s for s in fn.body if s is not stmt]
        body.insert(next(k for k, s in enumerate(body) if s is poll) + 1, stmt)
        fn.body = body
    else:
        raise SystemExit("unknown mutation " + kind)
    ast.fix_missing_locations(fn)
    return fn


_ok, _why = check_call_site(main_function())
check("MAIN_STARTUP_SEQUENCE_CALLS_THE_SWEEP", _ok, _why)

_ok_false, _why_false = check_call_site(mutated_main("if_false"))
check("CALL_SITE_CHECK_REJECTS_A_CALL_UNDER_IF_FALSE", not _ok_false, _why_false)
print("IF_FALSE_MUTATION_REJECTED_BECAUSE: " + _why_false)

_ok_poll, _why_poll = check_call_site(mutated_main("after_poll"))
check("CALL_SITE_CHECK_REJECTS_A_CALL_MOVED_AFTER_THE_POLL", not _ok_poll, _why_poll)
print("AFTER_POLL_MUTATION_REJECTED_BECAUSE: " + _why_poll)

_ok_rev, _why_rev = check_call_site(mutated_main("reviewer_if_false"))
check("CALL_SITE_CHECK_REJECTS_THE_REVIEWERS_IF_FALSE_SHAPE", not _ok_rev, _why_rev)
print("REVIEWER_IF_FALSE_SHAPE_REJECTED_BECAUSE: " + _why_rev)


def old_ast_walk_check(fn):
    """The check as it was: any call anywhere under main(). It passes `if False:` - that is the defect."""
    return fn is not None and any(is_sweep_call(n) for n in ast.walk(fn))


check("THE_OLD_AST_WALK_CHECK_IS_FOOLED_BY_IF_FALSE",
      old_ast_walk_check(mutated_main("if_false")) and not check_call_site(mutated_main("if_false"))[0])

# --- 9. the mutant the previous reviewer skipped: `recorded = set(applied)` -> `recorded = set()` ---------
def mutant_sweep():
    """The real sweep with the durable index ignored, so only the rotating live_fills rows prove anything."""
    src = textwrap.dedent(inspect.getsource(c.release_orphan_fill_claims))
    if "recorded = set(applied)" not in src:
        raise SystemExit("MUTANT_ANCHOR_MISSING: recorded = set(applied)")
    src = src.replace("recorded = set(applied)", "recorded = set()")
    ns = dict(vars(c))
    ns["__name__"] = "door3_mutant_sweep"
    exec(compile(src, "<mutant recorded=set()>", "exec"), ns)

    fn = ns["release_orphan_fill_claims"]  # the module-level sweep, with the durable index ignored
    return lambda: fn(core.audit)


FIDM = "0xmutant:9101"
c.claim_copy_fill_process_marker(FIDM)
intentm = fill_intent("mut")
c.ManualLedger().apply_copy_fill(intentm, {"copy_fill_id": FIDM, "side": "SELL", "size": 1.0, "price": 10.0})
c.AuditLogWriter().append_live_fill(fill_row(FIDM, coin=COIN, size="1.0", side="SELL", wallet=WALLET_A))
rotate_live_fills()
check("SETUP_MUTANT_CASE_IS_ROTATED_APPLIED_AND_UNCLAIMED",
      claim_file(FIDM).exists() and FIDM not in current_live_ids()
      and FIDM in (c.applied_copy_fill_ids_read()[0] or set()),
      str((claim_file(FIDM).exists(), FIDM in current_live_ids())))

before_m = c.ManualLedger().wallet_coin_position(WALLET_A, COIN)
released_m = mutant_sweep()()
claim_gone = not claim_file(FIDM).exists()
mcheck("ROTATED_APPLIED_FILL_KEEPS_ITS_CLAIM_ON_DURABLE_PROOF",
       released_m == 0 and claim_file(FIDM).exists(), str((released_m, claim_gone)))
replay_m = c.claim_copy_fill_process_marker(FIDM)
if replay_m:
    c.ManualLedger().apply_copy_fill(intentm, {"copy_fill_id": FIDM, "side": "SELL", "size": 1.0, "price": 10.0})
after_m = c.ManualLedger().wallet_coin_position(WALLET_A, COIN)
print("MUTANT_REPLAY_LEDGER_BEFORE=%r MUTANT_REPLAY_LEDGER_AFTER=%r MUTANT_REPLAY_ALLOWED=%r"
      % (before_m, after_m, bool(replay_m)))
mcheck("ROTATION_REPLAY_IS_BLOCKED_AND_THE_LEDGER_IS_NOT_DOUBLE_COUNTED",
       not replay_m and abs(after_m - before_m) < 1e-12,
       str((replay_m, before_m, after_m)))

check("MUTANT_RECORDED_SET_EMPTY_BREAKS_BOTH_NAMED_CHECKS", [ok for _n, ok in MR] == [False, False], MR)

failed = [n for n, ok in R if not ok]
print("MUTANT_TOTAL=%d MUTANT_FAILED=%d (the mutant is EXPECTED to fail both)" % (len(MR), sum(1 for _n, ok in MR if not ok)))
print("TOTAL=%d FAILED=%d" % (len(R), len(failed)))
raise SystemExit(1 if failed else 0)
