#!/usr/bin/env python3
"""Pinned Build-3 read-budget vs send observations; fake HTTP, NO REAL SOCKETS.

Run from _archive/hl_stage2:
    python -u test_core_read_budget_vs_send.py
Characterization only: a reproduced dangerous behavior prints OBSERVED_*; it is
not an endorsement or a request to change the engine. No keys, no real orders.
"""
from __future__ import annotations

import contextlib
import os
import socket
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

_TMP = tempfile.TemporaryDirectory(prefix="read_budget_send_")
os.environ.update({
    "HL_LIVE_AUDIT_DIR": str(Path(_TMP.name) / "audit"),
    "HL_LIVE_ENV_FILE": str(Path(_TMP.name) / "no.env"),
    "HL_LEADER_NETWORK": "testnet",
    "HL_FOLLOWER_NETWORK": "testnet",
    "HL_LIVE_WS_ENABLED": "0",
    "HL_LIVE_AUTO_SEND_ENABLED": "0",
    "HL_LIVE_MOCK_SEND": "1",
    "HL_LIVE_SCOPE_SWEEP_THREAD": "0",
    "HL_LIVE_DISABLE_NETWORK_REFRESH": "1",
    "HL_LIVE_FOREIGN_WS_SCAN": "0",
    "HL_LIVE_PREWARM_SDK_CLIENT": "0",
    "HL_LIVE_PREWARM_SYMBOL_META": "0",
    "HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS": "0",
    "HL_LIVE_HTTP_SESSION": "0",
})
import HL_Live_Copy_Service_Core as core  # noqa: E402
import headroom  # noqa: E402

WALLET = "0x" + "a" * 40
FOLLOWER = "0x" + "c" * 40


class FakeResponse:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status_code = status

    def json(self):
        return self.payload


class FakeHTTP:
    def __init__(self):
        self.calls = []
        self.sequence = []

    def post(self, url, json=None, timeout=None):
        self.calls.append((url, dict(json or {})))
        if self.sequence:
            value = self.sequence.pop(0)
            if isinstance(value, BaseException):
                raise value
            return value
        return FakeResponse([] if (json or {}).get("type") == "userFillsByTime"
                            else {"assetPositions": []})


class FakeExchange:
    def __init__(self):
        self.calls = []

    def order(self, coin, is_buy, size, px, order_type, **kwargs):
        self.calls.append((coin, size, kwargs))
        return {"status": "ok", "response": {"data": {"statuses": [{"resting": {"oid": 1}}]}}}


class InjectedDeferred(Exception):
    """Test-only pre-dispatch denial. The PINNED core has no such named skip."""


class BudgetSendTests(unittest.TestCase):
    def setUp(self):
        self.http = FakeHTTP()
        self.monitor = headroom.HeadroomMonitor(clock=lambda: 1000.0)
        self._patchers = [
            mock.patch.object(core, "requests",
                headroom.CountingRequests(self.http, self.monitor,
                                         [core.HL_LEADER_INFO_URL, core.HL_INFO_URL])),
            mock.patch("socket.socket", side_effect=AssertionError("REAL_SOCKET_DENIED")),
            mock.patch("socket.create_connection",
                       side_effect=AssertionError("REAL_CONNECT_DENIED")),
            mock.patch("socket.getaddrinfo",
                       side_effect=AssertionError("REAL_DNS_DENIED")),
            mock.patch.object(core, "log_error", lambda *args, **kwargs: None),
        ]
        for p in self._patchers:
            p.start()
            self.addCleanup(p.stop)

    def _sender(self):
        gateway = core.SenderGateway.__new__(core.SenderGateway)
        gateway._master_gate_reason = lambda *a, **k: ""
        gateway._reserve_exchange_order_slot = lambda *a, **k: core.utc_now_ms()
        gateway._note_sender_key_rejection = lambda *a: None
        return gateway

    def _order(self, gateway, exchange):
        with mock.patch.object(core, "_sender_lease_owned", return_value=True):
            return gateway._place_order(exchange, "BTC", True, 1.0, 100.0,
                                        "Ioc", False, intent=None)

    def _poll(self, start=1000, end=2000):
        return core.LeaderFillIngestor().poll_hyperliquid_fills(WALLET, start, end)

    def _snapshot(self):
        recon = core.ExchangeReconciler.__new__(core.ExchangeReconciler)
        writes = []
        with (mock.patch.object(core, "USER_WALLET", FOLLOWER),
              mock.patch.object(core, "follower_dex_scope", return_value=[""]),
              mock.patch.object(core.ExchangeReconciler, "_xyz_positions_from_app_snapshot",
                                return_value={}),
              mock.patch.object(core, "xyz_state_positions", return_value={}),
              mock.patch.object(core, "atomic_write_json",
                                side_effect=lambda path, doc: writes.append(doc)),
              mock.patch.object(core, "append_account_history_point",
                                return_value=None)):
            snapshot, status = recon.fetch_snapshot()
        return snapshot, status, writes

    def test_01_actual_sender_burst_and_info_weight_over_1200(self):
        exchange = FakeExchange()
        gateway = self._sender()
        sends, reads = 40, 75
        for i in range(max(sends, reads)):
            if i < sends:
                self.assertEqual(self._order(gateway, exchange)["status"], "ok")
            if i < reads:
                fills, status = self._poll()
                self.assertEqual((fills, status), ([], "POLL_OK"))
        weight = self.monitor.info_used("api.hyperliquid-testnet.xyz")
        info_http = [c for c in self.http.calls if c[1].get("type") == "userFillsByTime"]
        assert len(exchange.calls) == sends
        assert len(info_http) == reads
        assert weight >= 1200
        print("CASE1 SENDS=%d LEADER_INFO_HTTP=%d WEIGHT=%d "
              "BUDGET_SKIP_IN_PINNED_PATH=0 POLL_DEFERRED_IN_PINNED_PATH=0" %
              (len(exchange.calls), len(info_http), weight), flush=True)
        # Counting is not prevention: there is no budget refusal in this path.
        self.assertEqual((len(exchange.calls), len(info_http)), (40, 75))

    def test_02_deferred_or_failed_read_is_not_a_good_poll(self):
        self.http.sequence = [InjectedDeferred("injected would-be budget skip")]
        fills, status = self._poll()
        self.assertEqual((fills, status), ([], "POLL_NETWORK_ERROR"))
        snapshot_reads = self.http.calls
        self.assertEqual(len(snapshot_reads), 1)
        self.http.sequence = [InjectedDeferred("injected would-be budget skip")]
        snapshot, snap_status, writes = self._snapshot()
        self.assertEqual((snapshot, snap_status, writes), ({}, "SNAPSHOT_UNAVAILABLE", []))
        print("CASE2 FORCED_DEFERRED_EXCEPTION POLL=%s SNAPSHOT=%s "
              "SNAPSHOT_WRITES=%d (no native RATE_BUDGET_SKIP verdict)" %
              (status, snap_status, len(writes)), flush=True)

    def test_03_none_payload_becomes_flat_successful_snapshot(self):
        self.http.sequence = [FakeResponse(None)]
        snapshot, status, writes = self._snapshot()
        # Characterisation of a defect, not an assertion that this is safe.
        self.assertEqual(status, "SNAPSHOT_OK")
        self.assertEqual(snapshot.get("raw"), {})
        self.assertEqual(snapshot.get("positions_by_coin"), {})
        self.assertEqual(len(writes), 1)
        print("CASE3 RESPONSE_NONE SNAPSHOT=%s RAW=%s POSITIONS=%s "
              "PERSISTED=%d OBSERVED_FALSE_FLAT_SUCCESS=YES" %
              (status, snapshot["raw"], snapshot["positions_by_coin"], len(writes)), flush=True)

    def test_04_429_json_error_poll_preserves_retry_opportunity(self):
        raw = {"coin": "BTC", "side": "B", "px": "100", "sz": "1",
               "time": 1500, "hash": "test-fill-429", "user": WALLET}
        self.http.sequence = [
            FakeResponse({"error": "too many requests"}, 429),
            FakeResponse([raw], 200),
        ]
        first, status1 = self._poll(start=1000, end=2000)
        second, status2 = self._poll(start=1000, end=2000)
        self.assertEqual((first, status1), ([], "POLL_NETWORK_ERROR"))
        self.assertEqual(status2, "POLL_OK")
        self.assertEqual([f.leader_fill_id for f in second], ["test-fill-429"])
        starts = [body["startTime"] for url, body in self.http.calls
                  if body.get("type") == "userFillsByTime"]
        self.assertEqual(starts, [1000, 1000])
        print("CASE4 HTTP429_JSON_ERROR FIRST=%s SECOND=%s EVENT_ID=%s "
              "SAME_CURSOR_RETRIED=YES" % (status1, status2, second[0].leader_fill_id),
              flush=True)

    def test_05_429_with_empty_list_is_misclassified_as_success(self):
        self.http.sequence = [FakeResponse([], 429)]
        fills, status = self._poll(start=1000, end=2000)
        self.assertEqual((fills, status), ([], "POLL_OK"))
        print("CASE5 HTTP429_WITH_EMPTY_LIST POLL=%s FILLS=%d "
              "POSSIBLE_CURSOR_ADVANCE=YES (run_cycle:15443)" %
              (status, len(fills)), flush=True)

    def test_06_429_snapshot_error_body_is_false_flat(self):
        self.http.sequence = [FakeResponse({"error": "rate limited"}, 429)]
        snapshot, status, writes = self._snapshot()
        self.assertEqual(status, "SNAPSHOT_OK")
        self.assertEqual(snapshot["positions_by_coin"], {})
        self.assertEqual(len(writes), 1)
        print("CASE6 HTTP429_SNAPSHOT_ERROR POLLUTION=%s POSITIONS=%s "
              "PERSISTED=%d FALSE_FLAT=YES" %
              (status, snapshot["positions_by_coin"], len(writes)), flush=True)

    def test_07_429_order_exception_classifies_definite_refusal(self):
        class Http429(Exception):
            status_code = 429
        self.assertEqual(core.classify_rate_limit_kind(Http429("refused")), "RATE_LIMIT")
        self.assertEqual(core.classify_rate_limit_kind(RuntimeError("429")), "TIMEOUT")
        print("CASE7 EXCHANGE_429_EXCEPTION=RATE_LIMIT STRING_ONLY_429=TIMEOUT "
              "LEADER_EVENT_CONSUMPTION_NOT_DECIDED_BY_SEND_CLASSIFIER", flush=True)


if __name__ == "__main__":
    print("OFFLINE_TEST_ONLY=1 SOCKETS_DENIED=1 LIVE_KEYS_READ=0", flush=True)
    unittest.main(verbosity=2)
