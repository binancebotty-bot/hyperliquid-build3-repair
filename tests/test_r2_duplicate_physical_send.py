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
