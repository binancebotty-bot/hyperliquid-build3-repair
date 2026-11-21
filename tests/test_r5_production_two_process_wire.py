"""Production SenderGateway admission/wire methods, two distinct spawned OS processes.

No network: real production methods are AST loaded from the exact committed core.
Exchange observations are deliberately frozen; the fake exchange only records
physical calls. The durable SQLite reservation is production code, not a toy.
"""
import importlib.util
import multiprocessing as mp
import os
import queue
import sqlite3
from pathlib import Path

import pytest

SOURCE = Path(__file__).with_name("test_r5_physical_concurrency.py")
spec = importlib.util.spec_from_file_location("r5_real_wire_harness", SOURCE)
harness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(harness)

class RecordedExchange:
    def __init__(self, physical):
        self.physical = physical
    def order(self, *args, **kwargs):
        self.physical.put(("exchange.order", kwargs.get("reduce_only")))
        return {"status":"ok","response":{"type":"order","data":{"statuses":[{"resting":{"oid":123}}]}}}

def _sender_process(db_path, name, release, physical, outcomes):
    os.environ["HL_LIVE_WIRE_CAP_DB"] = db_path
    sender = harness.Gateway()
    release.wait(10)
    try:
        result = sender._send(RecordedExchange(physical), harness.intent(name))
        outcomes.put((name, repr(result)))
    except Exception as exc:
        outcomes.put((name, "ERROR:" + repr(exc)))
        raise

def test_two_real_sender_processes_one_wire_restart_and_settlement(tmp_path, monkeypatch):
    db_path = str(tmp_path/"shared-wire-cap.sqlite3")
    monkeypatch.setenv("HL_LIVE_WIRE_CAP_DB",db_path)
    ctx = mp.get_context("spawn")
    release, physical, outcomes = ctx.Event(), ctx.Queue(), ctx.Queue()
    workers = [ctx.Process(target=_sender_process,args=(db_path, f"entry-{i}", release, physical, outcomes))
               for i in range(2)]
    for p in workers: p.start()
    release.set()
    for p in workers:
        p.join(15)
        assert p.exitcode == 0
    results = [outcomes.get(timeout=3) for _ in workers]
    assert not any("ERROR:" in result for _, result in results)
    orders = [physical.get(timeout=3)]
    with pytest.raises(queue.Empty):
        physical.get(timeout=0.3)
    assert len(orders) == 1, f"unexpected physical exchange.order calls: {results!r}"

    with sqlite3.connect(db_path) as con:
        rows = con.execute("SELECT wallet,fill_id,intent_id,notional,state FROM wire_cap_holds").fetchall()
    assert len(rows) == 1 and rows[0][-1] == "UNKNOWN_UNTIL_PROVEN"

    # A brand new SenderGateway instance must see the previous process's hold.
    restarted = harness.Gateway()
    no_wire = harness.FakeExchange()
    restarted._send(no_wire, harness.intent("after-restart"))
    assert no_wire.calls == []

    # Real lifecycle close bypasses the entry cap but still runs physical close proof.
    restarted._send(no_wire, harness.intent("true-close","EXIT"), reduce_only=True)
    assert len(no_wire.calls) == 1 and no_wire.calls[0][1]["reduce_only"] is True

    winning_intent = harness.intent(rows[0][1])
    assert restarted._reconcile_wire_cap_hold(winning_intent,"OBSERVED_IN_EXPOSURE",
                                               exchange_confirmed=False,counted_in_exposure=True) is False
    assert restarted._reconcile_wire_cap_hold(winning_intent,"OBSERVED_IN_EXPOSURE",
                                               exchange_confirmed=True,counted_in_exposure=True) is True
    # Now the same 6 USD must be counted via exchange truth, not also as reservation.
    restarted.cap_source.follower_exposure = lambda: {"ok":True,"total_usd":6.}
    restarted.ledger.wallet_abs_exposure_usd = lambda *args:6.
    assert restarted._wire_entry_exposure_block(harness.intent("next-entry"),4.,1.,False,reserve=True) == ""
    with sqlite3.connect(db_path) as con:
        states = [r[0] for r in con.execute("SELECT state FROM wire_cap_holds").fetchall()]
    assert sorted(states) == ["OBSERVED_IN_EXPOSURE","UNKNOWN_UNTIL_PROVEN"]

def test_unproven_release_preserves_unknown_after_restart(tmp_path,monkeypatch):
    monkeypatch.setenv("HL_LIVE_WIRE_CAP_DB",str(tmp_path/"cap.sqlite3"))
    sender = harness.Gateway()
    assert sender._wire_entry_exposure_block(harness.intent("pending"),6,1,False,reserve=True) == ""
    restarted = harness.Gateway()
    assert not restarted._reconcile_wire_cap_hold(harness.intent("pending"),"OBSERVED_IN_EXPOSURE",
                                                    exchange_confirmed=True,counted_in_exposure=False)
    assert restarted._wire_entry_exposure_block(harness.intent("second"),6,1,False,reserve=True) == "ENTRY_WALLET_EXPOSURE_CAP"
