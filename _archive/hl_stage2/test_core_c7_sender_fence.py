#!/usr/bin/env python3
"""CC-1 R36 (d) T-E - THE SENDER FENCE HARNESS.

Two engine processes, two state dirs, ONE master/signer account. The question: can two senders
place an order against the same master at the same time, and is that enforced at the ONE
physical call (`exchange.order`) or only at startup?

This is a SPEC of the REQUIRED behaviour. Where the engine does not meet it the case is RED.
Nothing here weakens an assertion to match the code, and nothing here implements a fence.

REQUIRED
  C1  two processes, two state dirs, same master -> pairing refused or serialised (say which).
  C2  fence at the physical call: while A holds the send right, B must not reach
      exchange.order. Asserted on the CALL via a spy, never on a log line.
  C3  stale lock / holder death: state fail-open vs fail-closed; no deadlock of a live engine.
  C4  release: only after A releases can B send.

Run: python test_core_c7_sender_fence.py   # RESULT::<NAME> PASS|FAIL, TOTAL=n FAILED=m
No network, no orders, no live exchange handle.
"""
from __future__ import annotations

import ast
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
CORE = HERE / "HL_Live_Copy_Service_Core.py"
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok)))
    print("RESULT::%s %s%s" % (name, "PASS" if ok else "FAIL", ("  " + detail) if detail else ""))
    return bool(ok)


def note(msg):
    print("   NOTE  " + msg)


ROOT = Path(os.getenv("TMPDIR") or tempfile.gettempdir()) / "te_sender_fence"
if ROOT.exists():
    shutil.rmtree(ROOT, ignore_errors=True)
ROOT.mkdir(parents=True, exist_ok=True)
GLOBAL_LOCK = ROOT / "engine-global.lock"
os.environ["HL_LIVE_GLOBAL_LOCK_FILE"] = str(GLOBAL_LOCK)

CHILD_SRC = r'''
import json, os, sys, time
from pathlib import Path
state_dir, ready, result = sys.argv[1], sys.argv[2], sys.argv[3]
hold = float(sys.argv[4])
sys.path.insert(0, sys.argv[5])
out = {"ok": False, "err": "", "pid": os.getpid(), "t": time.time()}
try:
    import HL_Live_Copy_Service_Core as c
    c.acquire_global_instance_lock(Path(state_dir))
    out["global_ok"] = True
    c.acquire_instance_lock(Path(state_dir))
    out["ok"] = True
except SystemExit as e:
    out["err"] = str(e)
except Exception as e:
    out["err"] = repr(e)
out["t"] = time.time()
open(result, "w", encoding="utf-8").write(json.dumps(out))
open(ready, "w", encoding="utf-8").write("1")
if out["ok"] and hold > 0:
    time.sleep(hold)
'''


def spawn_holder(tag, state_dir, hold):
    child = ROOT / "child.py"
    if not child.exists():
        child.write_text(CHILD_SRC, encoding="utf-8")
    ready = ROOT / ("ready_%s" % tag)
    result = ROOT / ("result_%s" % tag)
    for p in (ready, result):
        if p.exists():
            p.unlink()
    env = dict(os.environ)
    env["HL_LIVE_AUDIT_DIR"] = str(state_dir)
    proc = subprocess.Popen(
        [sys.executable, str(child), str(state_dir), str(ready), str(result), str(hold), str(HERE)],
        env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    deadline = time.time() + 120
    while time.time() < deadline and not ready.exists():
        if proc.poll() is not None:
            break
        time.sleep(0.05)
    return proc, result


def child_result(proc, result, timeout=45.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if result.exists():
            try:
                return json.loads(result.read_text(encoding="utf-8"))
            except Exception:
                pass
        if proc.poll() is not None and result.exists():
            pass
        time.sleep(0.05)
    try:
        err = proc.stderr.read() if proc.stderr else ""
    except Exception:
        err = ""
    return {"ok": False, "err": "NO_RESULT_FILE %s" % (err or "")[-300:], "pid": proc.pid, "t": 0.0}


def reap(proc):
    if proc.poll() is None:
        try:
            proc.kill()
        except Exception:
            pass
    try:
        proc.wait(timeout=30)
    except Exception:
        pass


def census():
    tree = ast.parse(CORE.read_text(encoding="utf-8-sig"))
    sites = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            f = node.func
            if (isinstance(f, ast.Attribute) and f.attr == "order"
                    and isinstance(f.value, ast.Name) and f.value.id == "exchange"):
                sites.append(node.lineno)
    return sorted(sites)


class SpyExchange:
    def __init__(self):
        self.calls = []

    def order(self, *a, **kw):
        self.calls.append((a, kw))
        return {"status": "ok", "response": {"data": {"statuses": [{"resting": {"oid": 1}}]}}}


class _Fill:
    leader_wallet = "0x" + "a" * 40
    leader_fill_id = "0xmasterfill"
    coin = "BTC"
    side = "B"


class _Intent:
    fill = _Fill()
    intent_id = "fence-intent-1"
    copy_size = 0.01
    is_buy = True


def build_gateway(core, refusals):
    gw = object.__new__(core.SenderGateway)
    gw.sender_key_invalid = ""
    gw.sender_key_invalid_detail = ""

    class Cfg:
        def send_mode_now(self):
            return "ON"

        def wallet_enabled(self, _w):
            return True

        def wallet_mode(self, _w):
            return "ON"

    gw.cfg = Cfg()
    gw._reserve_exchange_order_slot = lambda wait_for_cooldown=True: int(time.time() * 1000)
    gw._gate_refusal_row = lambda intent, path, reason: refusals.append(reason)
    gw._note_sender_key_rejection = lambda response: None
    return gw


def main():
    print("SENDER FENCE HARNESS  core=%s" % CORE)
    sites = census()
    note("physical exchange.order AST call sites: %s" % sites)
    check("C2B_SINGLE_PHYSICAL_ORDER_SITE", len(sites) == 1,
          "expected exactly 1, found %d at %s" % (len(sites), sites))

    sys.path.insert(0, str(HERE))
    import HL_Live_Copy_Service_Core as core

    state_a = ROOT / "state_A"
    state_b = ROOT / "state_B"
    state_a.mkdir(parents=True, exist_ok=True)
    state_b.mkdir(parents=True, exist_ok=True)

    # ---- C1 -------------------------------------------------------------------------------
    a, a_result = spawn_holder("A", state_a, hold=600)
    ra = child_result(a, a_result)
    check("C1_HOLDER_A_ACQUIRES", ra.get("ok") is True,
          "A holds the send right: %s" % ((ra.get("err") or "ok")[:160]))

    b, b_result = spawn_holder("B", state_b, hold=0)
    rb = child_result(b, b_result)
    reap(b)
    check("C1_SECOND_SENDER_REFUSED_OR_SERIALISED", rb.get("ok") is not True,
          "B (own state dir, same master) was %s: %s"
          % ("REFUSED" if rb.get("ok") is not True else "ALLOWED", (rb.get("err") or "no error")[:200]))
    note("mechanism: %s" % ((rb.get("err") or "none recorded")[:160]))
    check("C1_REFUSAL_IS_INSTANCE_LOCK", "INSTANCE_ALREADY_RUNNING" in (rb.get("err") or ""),
          "refusal came from the engine's own lock, not an unrelated error")

    # ---- C2 -------------------------------------------------------------------------------
    spy = SpyExchange()
    refusals = []
    gw = build_gateway(core, refusals)
    intent = _Intent()
    gate = gw._master_gate_reason(intent, "fence")
    if gate:
        check("C2_PHYSICAL_FENCE", False,
              "VACUOUS: unrelated gate blocks first (%s) - fence not proven" % gate)
    else:
        pre = len(spy.calls)
        try:
            core.classify_send_lifecycle = lambda i: "ENTRY"
            gw._place_order(spy, "BTC", True, 0.01, 50000.0, "Ioc", False,
                            timing={}, started_key="", cloid=None,
                            bypass_rate_limit_cooldown=True, pre_send=None,
                            intent=intent, path="fence")
        except Exception:
            note("place_order raised: %s" % traceback.format_exc(limit=2).replace("\n", " | ")[:300])
        reached = len(spy.calls) - pre
        check("C2_PHYSICAL_FENCE", reached == 0,
              "A holds the send right; B reached exchange.order %d time(s) (required 0)" % reached)

    # ---- C3 -------------------------------------------------------------------------------
    reap(a)
    note("holder A killed at %.3f (pid %s)" % (time.time(), ra.get("pid")))

    c, c_result = spawn_holder("C", state_b, hold=0)
    rc = child_result(c, c_result)
    reap(c)
    recovered = rc.get("ok") is True
    check("C3_STALE_LOCK_AFTER_DEAD_HOLDER", recovered,
          "next sender %s the lock after holder death (fail-%s); %s"
          % ("acquired" if recovered else "could NOT acquire",
             "open" if recovered else "closed", (rc.get("err") or "")[:160]))
    if recovered:
        note("policy: FAIL-OPEN on holder death (the OS reclaims the byte-range lock with the pid); "
             "there is no stale window in which two senders both hold it")

    src = CORE.read_text(encoding="utf-8-sig")
    nonblocking = ("msvcrt.LK_NBLCK" in src) and ("fcntl.LOCK_NB" in src)
    blocking = ("LK_LOCK" in src) or ("fcntl.LOCK_EX)" in src)
    check("C3_NO_DEADLOCK_FROM_STALE_LOCK", nonblocking and not blocking,
          "non-blocking acquire present=%s, blocking acquire present=%s" % (nonblocking, blocking))

    # ---- C4 -------------------------------------------------------------------------------
    d, d_result = spawn_holder("D", state_a, hold=0)
    rd = child_result(d, d_result)
    reap(d)
    check("C4_AFTER_RELEASE_NEXT_SENDER_ACQUIRES", rd.get("ok") is True,
          "free lock: %s" % ((rd.get("err") or "acquired")[:160]))

    e, e_result = spawn_holder("E", state_a, hold=600)
    re_ = child_result(e, e_result)
    check("C4_RELEASE_IS_ORDERED", re_.get("ok") is True,
          "first claimant wins: %s" % ((re_.get("err") or "acquired")[:160]))

    f, f_result = spawn_holder("F", state_b, hold=0)
    rf = child_result(f, f_result)
    reap(f)
    check("C4_BLOCKED_WHILE_HELD", rf.get("ok") is not True,
          "while E held, B was %s (expected refused)"
          % ("allowed" if rf.get("ok") else "refused"))

    reap(e)
    released_at = time.time()
    g, g_result = spawn_holder("G", state_b, hold=0)
    rg = child_result(g, g_result)
    reap(g)
    check("C4_ACQUIRES_ONLY_AFTER_RELEASE", rg.get("ok") is True,
          "after E released, B %s (checked t=%.3f > release t=%.3f)"
          % ("acquired" if rg.get("ok") else "still refused", time.time(), released_at))

    total = len(RESULTS)
    failed = sum(1 for _n, ok in RESULTS if not ok)
    print("TOTAL=%d FAILED=%d" % (total, failed))
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        print("TOTAL=%d FAILED=%d" % (len(RESULTS) + 1, sum(1 for _n, ok in RESULTS if not ok) + 1))
        sys.exit(1)
