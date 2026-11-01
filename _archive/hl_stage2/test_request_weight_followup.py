"""Offline regressions for the weight, CLO polling, and exit cooldown follow-up."""
from __future__ import annotations

import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

_TEST_DIR = Path(tempfile.mkdtemp(prefix="request_weight_followup_"))
os.environ["HL_LIVE_AUDIT_DIR"] = str(_TEST_DIR / "audit")
os.environ["HL_LIVE_ENV_FILE"] = str(_TEST_DIR / "missing.env")
os.environ["HL_FOLLOWER_NETWORK"] = "testnet"
os.environ["HL_LIVE_GLOBAL_LOCK_FILE"] = str(_TEST_DIR / "sender.lock")

import HL_Live_Copy_Service_Core as core  # noqa: E402
core.acquire_global_instance_lock(_TEST_DIR / "instance")
assert core._sender_lease_owned(), "isolated sender lease required for physical fake-wire tests"


LIVE = "0x0000000000000000000000000000000000000001"
CLO_A = "0x0000000000000000000000000000000000000002"
CLO_B = "0x0000000000000000000000000000000000000003"
OFF = "0x0000000000000000000000000000000000000004"


class FakeConfig:
    def __init__(self, modes):
        self.modes = dict(modes)

    def wallets(self):
        return {wallet: {"mode": mode} for wallet, mode in self.modes.items()}

    def active_wallets(self):
        return [wallet for wallet, mode in self.modes.items() if mode != "OFF"]

    def wallet_mode(self, wallet):
        return self.modes.get(wallet, "OFF")

    def stream_wallets(self):
        return [w for w, mode in self.modes.items() if mode == "ON"][:core.MAX_WALLETS]

    def wallet_enabled(self, wallet):
        return wallet in self.modes

    def wallet_cfg(self, wallet):
        return {"norm_base": 1_000.0} if wallet in self.modes else {}

    def fixed_notional(self, _wallet):
        return 12.0

    def copy_mode(self, _wallet):
        return "proportional"


class FakeCore:
    def __init__(self, cfg, wallets, ledger):
        self.cfg = cfg
        self.wallets = list(wallets)
        self.ledger = ledger


class FakeExchange:
    def __init__(self):
        self.calls = []

    def order(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return {"status": "ok"}


def sender_gateway():
    gateway = core.SenderGateway.__new__(core.SenderGateway)
    gateway._exchange_order_lock = threading.Lock()
    gateway._last_exchange_order_ms = 0
    gateway._exchange_rate_limit_cooldown_until_ms = 0
    gateway.sender_key_invalid = ""
    gateway._note_sender_key_rejection = lambda _response: None
    gateway.cfg = FakeConfig({LIVE: "ON"})
    gateway.cfg.send_mode_now = lambda: "ON"
    gateway.audit = mock.Mock()
    return gateway


def valid_entry():
    fill = core.LeaderFill("rw13-entry", LIVE, "BTC", "BUY", 100.0, 1.0, 100_000, "TEST")
    return core.Intent("rw13-entry", fill, "BUY", 1.0, 100.0, "ON", "fixed",
                       "ENTRY_ALLOWED", "ENTRY", "rw13-sleeve", "", "FLAT",
                       0.0, 0.0, False, False)


class RequestWeightFollowupTests(unittest.TestCase):
    def test_equity_cache_default_is_120_seconds(self):
        builder = core.IntentBuilder.__new__(core.IntentBuilder)
        builder._leader_equity = {}
        builder._leader_equity_locks = {}
        builder._leader_equity_locks_guard = threading.Lock()
        builder._leader_dexes_lock = threading.Lock()
        builder._leader_dexes = [""]
        builder._leader_dexes_ms = 100_000
        now = [100_000]
        exposure = mock.Mock(return_value={"ok": True, "equity_usd": 80.0})
        portfolio = mock.Mock(return_value={"ok": True, "account_value_usd": 100.0})
        with (mock.patch.dict(os.environ, {"HL_LIVE_LEADER_EQUITY_TTL_SEC": ""}),
              mock.patch.object(core, "utc_now_ms", side_effect=lambda: now[0]),
              mock.patch.object(core._XNET, "master_exposure", exposure),
              mock.patch.object(core._XNET, "rolling_day_pnl", portfolio)):
            self.assertEqual(builder.leader_equity(LIVE), 100.0)
            now[0] += 119_999
            self.assertEqual(builder.leader_equity(LIVE), 100.0)
            self.assertEqual((exposure.call_count, portfolio.call_count), (1, 1))
            now[0] += 2
            self.assertEqual(builder.leader_equity(LIVE), 100.0)
            self.assertEqual((exposure.call_count, portfolio.call_count), (2, 2))

    def test_exit_uses_local_sleeve_without_leader_equity_read(self):
        ledger = core.ManualLedger(path=_TEST_DIR / "missing-ledger.json")
        sleeve = ledger.sleeve(LIVE, "BTC")
        sleeve.update(signed_size=3.0, position_id="sleeve-1", opened_by_intent_id="open-1")
        cfg = FakeConfig({LIVE: "ON"})
        builder = core.IntentBuilder(cfg, ledger)
        builder._decision = lambda *_args: ("EXIT_ALLOWED", "")
        builder.leader_equity = mock.Mock(side_effect=AssertionError("exit made a leader equity request"))
        fill = core.LeaderFill("close-1", LIVE, "BTC", "SELL", 100.0, 1.0, 123, "TEST")

        builder.prewarm(fill, local_block=True)
        intent = builder.build(fill)

        self.assertEqual(intent.decision, "EXIT_ALLOWED")
        self.assertEqual(intent.copy_size, 3.0)
        self.assertEqual(intent.copy_notional, 300.0)
        builder.leader_equity.assert_not_called()

    def test_flat_clo_sleeves_skip_poll_but_netted_opposites_do_not(self):
        path = _TEST_DIR / "flat-poll-ledger.json"
        core.atomic_write_json(path, {
            "schema": "manual_live_positions.v1.wallet_sleeves",
            "by_wallet": {
                CLO_A: {"BTC": {"coin": "BTC", "signed_size": 2.0}},
                CLO_B: {"BTC": {"coin": "BTC", "signed_size": -2.0}},
            },
            "by_coin_net": {"BTC": {"signed_size": 0.0}},
        })
        ledger = core.ManualLedger(path=path)
        cfg = FakeConfig({LIVE: "ON", CLO_A: "CLO", CLO_B: "CLO", OFF: "OFF"})
        test_core = FakeCore(cfg, [LIVE], ledger)

        with mock.patch.dict(os.environ, {"HL_LIVE_POLL_ALL_ACTIVE": "1"}):
            self.assertEqual(set(core.LiveCopyCore.poll_wallets(test_core)), {LIVE, CLO_A, CLO_B})

        core.atomic_write_json(path, {
            "schema": "manual_live_positions.v1.wallet_sleeves",
            "by_wallet": {CLO_A: {"BTC": {"coin": "BTC", "signed_size": 0.0}}},
            "by_coin_net": {"BTC": {"signed_size": 0.0}},
        })
        with mock.patch.dict(os.environ, {"HL_LIVE_POLL_ALL_ACTIVE": "1"}):
            self.assertEqual(set(core.LiveCopyCore.poll_wallets(test_core)), {LIVE})

    def test_flat_clo_fail_open_and_poll_all_active_zero(self):
        path = _TEST_DIR / "invalid-poll-ledger.json"
        path.write_text("{broken", encoding="utf-8")
        ledger = core.ManualLedger(path=path)
        cfg = FakeConfig({LIVE: "ON", CLO_A: "CLO", CLO_B: "CLO", OFF: "OFF"})
        test_core = FakeCore(cfg, [LIVE], ledger)
        with mock.patch.dict(os.environ, {"HL_LIVE_POLL_ALL_ACTIVE": "1"}):
            self.assertEqual(set(core.LiveCopyCore.poll_wallets(test_core)), {LIVE, CLO_A, CLO_B})

        core.atomic_write_json(path, {
            "schema": "manual_live_positions.v1.wallet_sleeves",
            "by_wallet": {CLO_A: {"BTC": {"coin": "BTC", "signed_size": "0"}}},
            "by_coin_net": {},
        })
        with mock.patch.dict(os.environ, {"HL_LIVE_POLL_ALL_ACTIVE": "0"}):
            self.assertEqual(set(core.LiveCopyCore.poll_wallets(test_core)), {LIVE, CLO_A, CLO_B})

    def test_wallet_mode_transition_forces_poll_cycle(self):
        path = _TEST_DIR / "mode-poll-ledger.json"
        core.atomic_write_json(path, {"schema": "manual_live_positions.v1.wallet_sleeves", "by_wallet": {}, "by_coin_net": {}})
        cfg = FakeConfig({LIVE: "ON", CLO_A: "CLO"})
        test_core = FakeCore(cfg, [LIVE], core.ManualLedger(path=path))
        with mock.patch.dict(os.environ, {"HL_LIVE_POLL_ALL_ACTIVE": "1"}):
            core.LiveCopyCore.poll_wallets(test_core)
            core.atomic_write_json(path, {
                "schema": "manual_live_positions.v1.wallet_sleeves",
                "by_wallet": {CLO_A: {"BTC": {"coin": "BTC", "signed_size": 1.0}}},
                "by_coin_net": {"BTC": {"signed_size": 1.0}},
            })
            self.assertEqual(set(core.LiveCopyCore.poll_wallets(test_core)), {LIVE, CLO_A})
            self.assertTrue(test_core._poll_wallet_selection_changed)
            test_core._last_leader_poll_ms = 99_000
            test_core.leader_poll_interval_sec = lambda: 30.0
            with mock.patch.object(core.HEADROOM, "evaluate", return_value=None), \
                 mock.patch.object(core, "utc_now_ms", return_value=100_000):
                self.assertTrue(core.LiveCopyCore._leader_poll_due(
                    test_core, force=test_core._poll_wallet_selection_changed))
            cfg.modes[CLO_A] = "ON"
            test_core.wallets = [LIVE, CLO_A]
            core.LiveCopyCore.poll_wallets(test_core)

        self.assertTrue(getattr(test_core, "_poll_wallet_selection_changed", False))
        test_core._last_leader_poll_ms = 99_000
        test_core.leader_poll_interval_sec = lambda: 30.0
        with mock.patch.object(core.HEADROOM, "evaluate", return_value=None), \
             mock.patch.object(core, "utc_now_ms", return_value=100_000):
            self.assertTrue(core.LiveCopyCore._leader_poll_due(test_core, force=True))

    def test_nonflat_clo_uses_60_second_poll_interval(self):
        cfg = FakeConfig({CLO_A: "CLO"})
        test_core = FakeCore(cfg, [], mock.Mock())
        test_core.ws = mock.Mock(enabled=True, _socket_open=True, _subscribed={CLO_A})
        test_core.ledger.nonflat_wallets_from_disk.return_value = {CLO_A}
        test_core.leader_poll_interval_sec = core.LiveCopyCore.leader_poll_interval_sec.__get__(test_core)
        self.assertEqual(test_core.leader_poll_interval_sec(), 60.0)

    def test_nonflat_clo_polls_on_schedule_and_delivers_its_exit(self):
        path = _TEST_DIR / "nonflat-clo-ledger.json"
        core.atomic_write_json(path, {
            "schema": "manual_live_positions.v1.wallet_sleeves",
            "by_wallet": {CLO_A: {"BTC": {"coin": "BTC", "signed_size": 2.0}}},
            "by_coin_net": {"BTC": {"signed_size": 2.0}},
        })
        ledger = core.ManualLedger(path=path)
        cfg = FakeConfig({CLO_A: "CLO"})
        test_core = FakeCore(cfg, [], ledger)
        now = [130_000]
        with mock.patch.dict(os.environ, {"HL_LIVE_POLL_ALL_ACTIVE": "1", "HL_LIVE_LEADER_POLL_INTERVAL_SEC": "30"}), \
             mock.patch.object(core, "utc_now_ms", side_effect=lambda: now[0]), \
             mock.patch.object(core.HEADROOM, "evaluate", return_value=None):
            wallets = core.LiveCopyCore.poll_wallets(test_core)
            test_core._last_leader_poll_ms = 100_000
            test_core.leader_poll_interval_sec = lambda: 30.0
            self.assertEqual(wallets, [CLO_A])
            self.assertTrue(core.LiveCopyCore._leader_poll_due(test_core))

        exit_fill = core.LeaderFill("clo-exit", CLO_A, "BTC", "SELL", 100.0, 1.0, 123, "POLL",
                                    raw={"dir": "Close Long"})
        calls = []
        def poll(wallet, _start, _end=None):
            calls.append(wallet)
            return ([exit_fill] if wallet == CLO_A else [], "POLL_OK")

        fills, status = poll(CLO_A, 100_000, now[0])
        builder = core.IntentBuilder(cfg, ledger)
        builder._decision = lambda *_args: ("EXIT_ALLOWED", "")
        intent = builder.build(fills[0])

        self.assertEqual(calls, [CLO_A])
        self.assertEqual(status, "POLL_OK")
        self.assertIn("lifecycle=EXIT", intent.notes)
        self.assertEqual(intent.copy_size, 2.0)

    def test_429_does_not_pause_entries_beyond_short_slot_pacing(self):
        sleeps = []
        now_ms = 100_000
        current_ms = [now_ms]

        def virtual_sleep(seconds):
            sleeps.append(seconds)
            current_ms[0] += int(round(seconds * 1000))

        with (mock.patch.dict(os.environ, {"HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS": "250"}),
              mock.patch.object(core, "utc_now_ms", side_effect=lambda: current_ms[0]),
              mock.patch.object(core.time, "sleep", side_effect=virtual_sleep)):
            exit_gateway = sender_gateway()
            exit_gateway._exchange_rate_limit_cooldown_until_ms = now_ms + 8_000
            self.assertEqual(exit_gateway._reserve_exchange_order_slot(wait_for_cooldown=False), now_ms)
            self.assertEqual(sleeps, [], "EXIT slot skips 429 delay")

            entry_gateway = sender_gateway()
            entry_gateway._exchange_rate_limit_cooldown_until_ms = now_ms + 8_000
            fake = FakeExchange()
            intent = valid_entry()
            response = entry_gateway._place_order(fake, "BTC", True, 1.0, 100.0, "Ioc", False,
                                                  intent=intent)
            self.assertEqual(response.get("status"), "ok")
            self.assertEqual(len(fake.calls), 1, "same fixture must have a positive physical fake send")
            self.assertEqual(entry_gateway._last_exchange_order_ms, now_ms,
                             "429 must not defer an ENTRY beyond the short slot pacing")
            self.assertEqual(sleeps, [], "8 second HTTP429 cooldown violates Boss's no-entry-pause rule")
            entry_gateway.cfg.send_mode_now = lambda: "OFF"
            blocked = entry_gateway._place_order(fake, "BTC", True, 1.0, 100.0, "Ioc", False,
                                                  intent=intent)
            self.assertIn("MASTER_REAL_ORDERS_OFF", str(blocked))
            self.assertEqual(len(fake.calls), 1, "OFF negative must prevent another physical call")


if __name__ == "__main__":
    unittest.main()
