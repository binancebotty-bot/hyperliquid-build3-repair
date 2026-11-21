"""R2 regression: duplicate leader offers must not reach exchange.order twice.

Exercises unmodified production _dispatch_fill -> hot worker -> IntentBuilder ->
SenderGateway._missed_entry_rest_or_diff -> SenderGateway._place_order -> exchange.order.
The existing offline harness supplies the exchange/ledger spies only.
"""
from __future__ import annotations

import importlib.util
import threading
from pathlib import Path

import pytest


_HARNESS_PATH = Path(__file__).with_name("test_r2_production_worker_e2e.py")
_spec = importlib.util.spec_from_file_location("_r2_production_worker_harness", _HARNESS_PATH)
assert _spec is not None and _spec.loader is not None
r2 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(r2)


@pytest.mark.parametrize("shape", ["concurrent", "retry", "reoffer"])
def test_same_leader_fill_never_double_sends_or_mints_new_attempt(
    shape, tmp_path, monkeypatch
):
    r2.errors.clear()
    monkeypatch.setenv("HL_LIVE_HOT_INNER", "1")
    h = r2.create_harness(tmp_path / "reconcile.csv")
    item = r2.fill(1, stale=True)
    fid = item.leader_fill_id

    # Count the actual exchange.order boundary, not just a synthetic sender
    # return value. Delegate to the existing spy so its assertions remain live.
    physical_calls = []
    exchange = h.sender._physical_exchange
    original_order = exchange.order

    def physical_order(*args, **kwargs):
        physical_calls.append((args, kwargs))
        return original_order(*args, **kwargs)

    monkeypatch.setattr(exchange, "order", physical_order)

    def attempt_ids():
        return [
            row["attempt_id"]
            for event, status, row in h.audit.rows
            if event == "SEND_ATTEMPT" and row.get("leader_fill_id") == fid
        ]

    if shape == "concurrent":
        # Two distinct source deliveries race into the real dispatch function.
        # Delay worker launch so both admissions have finished before send.
        gate = threading.Barrier(3)
        decisions = []
        failures = []

        def offer():
            try:
                gate.wait(timeout=5)
                decisions.append(h._dispatch_fill(r2.fill(1, stale=True)))
            except BaseException as exc:
                failures.append(exc)

        threads = [threading.Thread(target=offer) for _ in range(2)]
        for thread in threads:
            thread.start()
        gate.wait(timeout=5)
        for thread in threads:
            thread.join(timeout=5)
            assert not thread.is_alive(), "concurrent dispatch hung"
        assert not failures, f"concurrent dispatch raised: {failures!r}"
        assert decisions == [True, True]
    else:
        assert h._dispatch_fill(item) is True
        if shape == "retry":
            # Source immediately retries while its first delivery is queued.
            assert h._dispatch_fill(r2.fill(1, stale=True)) is True

    worker = r2.launch_worker(h)
    assert h.drain_startup_hot_queue(timeout_sec=5)
    if shape == "reoffer":
        # Source redelivers AFTER the prior delivery has left the hot queue.
        # A new fill object deliberately carries the same leader_fill_id.
        before = attempt_ids()
        assert len(before) == 1, f"first send has no unique attempt: {before!r}"
        assert h._dispatch_fill(r2.fill(1, stale=True)) is True
        assert h.drain_startup_hot_queue(timeout_sec=5)
        assert attempt_ids() == before, "reoffer minted another send_attempt_id"
    r2.shutdown(h, worker)

    ids = attempt_ids()
    assert len(physical_calls) == 1, (
        f"{shape}: duplicate {fid} reached physical exchange.order "
        f"{len(physical_calls)} times, expected exactly 1"
    )
    assert len(h.sender.orders) == 1
    assert h.sender.orders[0][:2] == ("MISSED_REOFFER", fid)
    assert len(ids) == 1 and ids[0], (
        f"{shape}: duplicate offer minted a second send_attempt_id or no attempt: {ids!r}"
    )
    assert len(set(ids)) == 1
    assert h.sender.remedies == [(fid, "ORD_010_ENTRY_AGE_OVER_30S")]
    assert len(h.audit.intents) == 1
    assert not h._past_send_keys, "stale recovery was premarked as normal send"



@pytest.mark.parametrize("shape", ["concurrent", "retry", "reoffer"])
def test_normal_entry_duplicate_never_reaches_physical_wire(shape, tmp_path, monkeypatch):
    """Non-stale ENTRY uses the ordinary physical send, not the missed-entry remedy."""
    r2.errors.clear()
    monkeypatch.setenv("HL_LIVE_HOT_INNER", "1")
    h = r2.create_harness(tmp_path / "normal_reconcile.csv")
    fid = "fill-2"
    physical_calls = []
    exchange = h.sender._physical_exchange
    original_order = exchange.order

    def spy(*args, **kwargs):
        physical_calls.append((args, kwargs))
        return original_order(*args, **kwargs)

    monkeypatch.setattr(exchange, "order", spy)

    if shape == "concurrent":
        gate = threading.Barrier(3)
        responses = []
        failures = []

        def offer():
            try:
                gate.wait(timeout=5)
                responses.append(h._dispatch_fill(r2.fill(2, stale=False)))
            except BaseException as exc:
                failures.append(exc)

        threads = [threading.Thread(target=offer) for _ in range(2)]
        for t in threads:
            t.start()
        gate.wait(timeout=5)
        for t in threads:
            t.join(timeout=5)
            assert not t.is_alive()
        assert not failures
        assert responses == [True, True]
    else:
        assert h._dispatch_fill(r2.fill(2, stale=False)) is True
        if shape == "retry":
            assert h._dispatch_fill(r2.fill(2, stale=False)) is True

    worker = r2.launch_worker(h)
    assert h.drain_startup_hot_queue(timeout_sec=5)
    if shape == "reoffer":
        assert h._dispatch_fill(r2.fill(2, stale=False)) is True
        assert h.drain_startup_hot_queue(timeout_sec=5)
    r2.shutdown(h, worker)

    assert len(physical_calls) == 1, (
        f"normal ENTRY {shape}: physical exchange.order invoked "
        f"{len(physical_calls)} times for {fid}"
    )
    assert h.sender.orders[0][:2] == ("PHYSICAL_SEND", fid)
    assert len(h.sender.orders) == 1
    assert h.sender.remedies == []
    assert len(h.audit.intents) == 1
    # The pre-existing FakeSender's normal-send shim does not manufacture a
    # send_attempt journal row. Do not pretend that it proves stable IDs.
    assert not [row for event, _, row in h.audit.rows
                if event == "SEND_ATTEMPT" and row.get("leader_fill_id") == fid]


@pytest.mark.parametrize("stale", [False, True], ids=["normal-entry", "stale-entry"])
def test_two_production_workers_race_while_first_exchange_order_in_flight(
    stale, tmp_path, monkeypatch
):
    """Competing worker processes same ID during first order's exchange.order call.

    Dispatch's queued-key guard intentionally prevents a second dispatch from
    reaching a worker. Simulate the alternate worker/ingress after dispatch by
    invoking production _run_plan, NOT a fake sender or a second dispatch.
    Different coin keys avoid testing only the per-coin lock; leader_fill_id
    remains identical, which is what the idempotency guard must protect.
    """
    r2.errors.clear()
    monkeypatch.setenv("HL_LIVE_HOT_INNER", "1")
    h = r2.create_harness(tmp_path / "race_reconcile.csv")
    first = r2.fill(3, stale=stale)
    second = r2.fill(3, stale=stale)
    second.coin = "C4"
    assert first.leader_fill_id == second.leader_fill_id
    fid = first.leader_fill_id

    first_wire_entered = threading.Event()
    release_first_wire = threading.Event()
    second_processing_started = threading.Event()
    physical_calls = []
    exchange = h.sender._physical_exchange
    original_order = exchange.order

    def held_exchange_order(*args, **kwargs):
        physical_calls.append((args, kwargs))
        if len(physical_calls) == 1:
            first_wire_entered.set()
            assert release_first_wire.wait(5), (
                "competing worker did not reach production process while wire was held"
            )
        return original_order(*args, **kwargs)

    monkeypatch.setattr(exchange, "order", held_exchange_order)

    original_trace = h._fill_trace

    def trace(stage, fill, *args):
        if stage == "proc_start" and fill is second:
            second_processing_started.set()
        return original_trace(stage, fill, *args)

    h._fill_trace = trace
    assert h._dispatch_fill(first) is True
    worker = r2.launch_worker(h)
    competitor = None
    try:
        assert first_wire_entered.wait(5), "first worker never reached exchange.order"

        def run_competing_worker():
            # _run_plan is the real production worker-to-process call path.
            # A distinct worker ingress bypasses only the upstream queue
            # admission check, so the downstream idempotency guard is tested.
            h._run_plan(0, [second])

        competitor = threading.Thread(target=run_competing_worker,
                                      name="r2-competing-worker", daemon=True)
        competitor.start()
        assert second_processing_started.wait(5), (
            "competing worker never entered production _process_leader_fill"
        )
        assert first_wire_entered.is_set() and not release_first_wire.is_set()
        assert len(physical_calls) == 1, (
            "second worker reached physical wire while first was in flight"
        )
    finally:
        release_first_wire.set()
        if competitor is not None:
            competitor.join(timeout=5)
        assert h.drain_startup_hot_queue(timeout_sec=5)
        r2.shutdown(h, worker)

    assert competitor is not None and not competitor.is_alive()
    assert len(physical_calls) == 1, (
        f"two workers processing {fid}: physical exchange.order count "
        f"{len(physical_calls)} instead of 1"
    )
    assert len(h.sender.orders) == 1
    assert h.sender.orders[0][1] == fid
    assert len(h.audit.intents) == 1, "second worker built a duplicate intent"
    if stale:
        attempts = [row["attempt_id"] for event, _, row in h.audit.rows
                    if event == "SEND_ATTEMPT" and row.get("leader_fill_id") == fid]
        assert len(attempts) == 1 and attempts[0], (
            f"stale worker race minted additional send_attempt_id: {attempts!r}"
        )
        assert h.sender.orders[0][0] == "MISSED_REOFFER"
    else:
        assert h.sender.orders[0][0] == "PHYSICAL_SEND"
