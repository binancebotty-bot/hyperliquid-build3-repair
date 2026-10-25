#!/usr/bin/env python3
"""Item 3/4: the exact row-name allow-list and the trigger accounting of _retention_replay.

Every row name the sender can write must be classified as an exchange outcome or as not one. The names are
enumerated from the source with ast: every string literal assigned to terminal_state (keyword argument or dict
key) plus every string classify_terminal_state can return. A new sender row name nobody classified makes this
file fail instead of falling through silently. A trigger is released again when mark_attempting fails.

Run (from _archive/hl_stage2):  env -u HL_LIVE_AUDIT_DIR python3 test_core_deferred_entry_rows.py
No network, no orders."""
from __future__ import annotations

import ast
import os
import re
import sys
import tempfile
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
R = []
A = "0x" + "a" * 40


def check(n, ok, d=""):
    R.append(bool(ok))
    print("RESULT::%s_%s%s" % (n, "PASS" if ok else "FAIL", (" | " + str(d)) if d and not ok else ""))


def unclassified(term, non, names):
    """The oracle: a name in neither set is unclassified, so the test can prove a name was missed."""
    return set(names) - set(term) - set(non)


def emittable(source):
    tree = ast.parse(source)
    ok = re.compile(r"^[A-Z][A-Z0-9_]{3,}$")
    names = set()

    def take(node):
        for leaf in ast.walk(node):
            if isinstance(leaf, ast.Constant) and isinstance(leaf.value, str) and ok.match(leaf.value):
                names.add(leaf.value)

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            for kw in node.keywords:
                if kw.arg == "terminal_state":
                    take(kw.value)
        if isinstance(node, ast.Dict):
            for k, v in zip(node.keys, node.values):
                if isinstance(k, ast.Constant) and k.value == "terminal_state":
                    take(v)
        if isinstance(node, ast.FunctionDef) and node.name == "classify_terminal_state":
            for leaf in ast.walk(node):
                if isinstance(leaf, ast.Return) and isinstance(leaf.value, ast.Constant) \
                        and isinstance(leaf.value.value, str):
                    names.add(leaf.value.value)
                if isinstance(leaf, ast.Dict):
                    for v in leaf.values:
                        if isinstance(v, ast.Constant) and isinstance(v.value, str):
                            names.add(v.value)
    return names


def main():
    tmp = Path(tempfile.mkdtemp(prefix="deferred_rows_"))
    os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LEADER_NETWORK": "testnet",
                       "HL_FOLLOWER_NETWORK": "testnet", "HL_LIVE_ENV_FILE": str(tmp / "none.env"),
                       "HL_LIVE_SCOPE_SWEEP_THREAD": "0", "HL_LIVE_LIQ_PARITY": "0"})
    global c
    import HL_Live_Copy_Service_Core as c

    term = c.LiveCopyCore._RETENTION_TERMINAL_ROWS
    non = c.LiveCopyCore._RETENTION_NON_TERMINAL_ROWS
    names = emittable((HERE / "HL_Live_Copy_Service_Core.py").read_text(encoding="utf-8-sig"))
    left = unclassified(term, non, names)
    check("R0_EVERY_SENDER_ROW_NAME_IS_CLASSIFIED", not left and len(names) > 50, sorted(left) or len(names))
    check("R1_THE_TWO_SETS_ARE_DISJOINT", not (term & non), sorted(term & non))
    check("R2_THE_TEST_DETECTS_AN_UNCLASSIFIED_NAME",
          unclassified(term - {"ORDER_FILLED"}, non, {"ORDER_FILLED"}) == {"ORDER_FILLED"})
    check("R3_MISSED_ENTRY_LIMIT_REJECTED_IS_NOT_AN_OUTCOME", "MISSED_ENTRY_LIMIT_REJECTED" in non)
    check("R4_MISSED_ENTRY_LIMIT_OUTCOME_UNKNOWN_IS_AN_OUTCOME", "MISSED_ENTRY_LIMIT_OUTCOME_UNKNOWN" in term)
    check("R5_PENDING_SEND_AND_ORDER_RESTING_ARE_NOT_OUTCOMES",
          not ({"PENDING_SEND", "ORDER_RESTING"} & term) and {"PENDING_SEND", "ORDER_RESTING"} <= non)
    bad = [n for n in term if not c.LiveCopyCore._retention_classifies(n)]
    bad += [n for n in non if c.LiveCopyCore._retention_classifies(n)]
    check("R6_CLASSIFIER_AGREES_WITH_BOTH_SETS", not bad, bad)
    check("R7_AN_UNKNOWN_NAME_IS_NOT_AN_OUTCOME",
          c.LiveCopyCore._retention_classifies("SOME_FUTURE_ROW_NAME") is False)

    class Sender:
        _market_halted_until_ms = {}

        def _read_open_orders(self):
            return True, [], "read 1/1 dexes"

    core = c.LiveCopyCore.__new__(c.LiveCopyCore)
    core.sender = Sender()
    core.audit = c.AuditLogWriter()
    core.retention = c.DeferredEntryRetention()
    c._read_all_copy_fills = lambda s, e, **k: ([], "FILLS_COMPLETE")
    cl = c.generate_cloid("rows-1")
    core.audit.append_send_attempt({"attempt_id": "at-rows-1", "intent_id": "i-rows-1", "leader_fill_id": "rows-1",
        "leader_wallet": A, "coin": "BTC", "side": "BUY", "status": "ORDER_REJECTED",
        "terminal_state": "MISSED_ENTRY_LIMIT_REJECTED", "exchange_order_id": "", "exchange_response": "{}",
        "cloid": cl})
    since = c.utc_now_ms() - 1000
    pending, _why = core._retention_terminal_outcome("rows-1", cl, "i-rows-1", since)
    check("R8_REJECTED_LIMIT_ROW_ALONE_IS_NOT_AN_OUTCOME", pending is False, pending)
    core.audit.append_reconciliation("SEND_TERMINAL", "MISSED_ENTRY_LIMIT_OUTCOME_UNKNOWN", leader_wallet=A,
        leader_fill_id="rows-1", intent_id="i-rows-1", coin="BTC", cloid=cl,
        terminal_state="MISSED_ENTRY_LIMIT_OUTCOME_UNKNOWN")
    after, why2 = core._retention_terminal_outcome("rows-1", cl, "i-rows-1", since)
    check("R9_THE_OUTCOME_ROW_IS_AN_OUTCOME", after is True, why2)

    class Fake:
        pass

    f = c.LiveCopyCore.__new__(c.LiveCopyCore)   # the real _retention_replay, no threads, no sockets
    f.retention = c.DeferredEntryRetention()
    f.sender = Fake()
    f.sender.recheck_deferred_entry = lambda intent: ""
    f.sender._market_halted_until_ms = {}
    f.audit = c.AuditLogWriter()
    f._idem_lock, f._idem_accepted = threading.Lock(), set()
    f.dedupe = Fake()
    f.dedupe._lock = threading.RLock()
    f.dedupe.processed = set()
    f._guard_key = c.LiveCopyCore._guard_key
    sent = []
    f._dispatch_fill = sent.append
    f._retention_terminal_outcome = lambda *a: (False, "")

    lf = c.LeaderFill("trig-rows", A, "BTC", "BUY", 100.0, 1.0, c.utc_now_ms(), "TEST", 0, {"dir": "Open Long"})
    assert f.retention.retain(lf, "MARKET_HALTED") is True
    trig = "halt:btc"
    f.sender._market_halted_until_ms["btc"] = c.utc_now_ms() - 1
    real_mark = f.retention.mark_attempting
    f.retention.mark_attempting = lambda *a: False
    f._retention_replay("trig-rows", f.retention.snapshot()["trig-rows"], trig)
    it = f.retention.snapshot()["trig-rows"]
    check("T1_FAILED_ATTEMPT_WRITE_RELEASES_THE_TRIGGER",
          it.get("triggers_done") == [] and int(it.get("attempts") or 0) == 0, it)
    check("T2_FAILED_ATTEMPT_WRITE_DISPATCHES_NOTHING", sent == [], sent)
    check("T3_THE_ITEM_STAYS_RETAINED_FOR_A_LATER_TRIGGER", it.get("state") == "RETAINED", it)
    check("T4_THE_TRIGGER_IS_OFFERED_AGAIN",
          f._retention_trigger(dict(it, reason="MARKET_HALTED"), c.utc_now_ms()) == trig, it)
    f.retention.mark_attempting = real_mark
    f._retention_replay("trig-rows", f.retention.snapshot()["trig-rows"], trig)
    ok_item = f.retention.snapshot()["trig-rows"]
    check("T5_THE_NEXT_ATTEMPT_USES_THE_TRIGGER",
          ok_item.get("triggers_done") == [trig] and int(ok_item.get("attempts") or 0) == 1
          and ok_item.get("state") == "ATTEMPTING" and len(sent) == 1, (ok_item, len(sent)))

    failed = [i for i, ok in enumerate(R) if not ok]
    print("TOTAL=%d FAILED=%d" % (len(R), len(failed)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
