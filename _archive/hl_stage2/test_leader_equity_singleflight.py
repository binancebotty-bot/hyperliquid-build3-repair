import os

os.environ.clear()
os.environ["HL_LIVE_ENV_FILE"] = r"Z:\\codex-no-env-file"

import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest import TestCase, main

import HL_Live_Copy_Service_Core as core


class LeaderEquitySingleflightTests(TestCase):
    def test_concurrent_same_wallet_refresh_uses_one_read_set(self):
        workers = 12
        start = threading.Barrier(workers + 1)
        counts = {"dexes": 0, "exposure": 0, "portfolio": 0}
        count_lock = threading.Lock()

        def result(name, value):
            def call(*_args, **_kwargs):
                with count_lock:
                    counts[name] += 1
                time.sleep(0.02)
                return value
            return call

        builder = core.IntentBuilder.__new__(core.IntentBuilder)
        builder._leader_equity = {}
        builder._leader_equity_locks = {}
        builder._leader_equity_locks_guard = threading.Lock()
        builder._leader_dexes_lock = threading.Lock()
        builder._leader_dexes = None
        builder._leader_dexes_ms = 0

        saved = (core._XNET.list_perp_dexes, core._XNET.master_exposure, core._XNET.rolling_day_pnl)
        core._XNET.list_perp_dexes = result("dexes", {"ok": True, "dexes": [""]})
        core._XNET.master_exposure = result("exposure", {"ok": True, "equity_usd": 80.0})
        core._XNET.rolling_day_pnl = result("portfolio", {"ok": True, "account_value_usd": 100.0})
        try:
            def read_equity():
                start.wait()
                return builder.leader_equity("0x0000000000000000000000000000000000000001")

            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = [pool.submit(read_equity) for _ in range(workers)]
                start.wait()
                values = [future.result() for future in futures]
        finally:
            core._XNET.list_perp_dexes, core._XNET.master_exposure, core._XNET.rolling_day_pnl = saved

        self.assertEqual(values, [100.0] * workers)
        self.assertEqual(counts, {"dexes": 1, "exposure": 1, "portfolio": 1})

    def test_concurrent_wallet_misses_share_the_leader_dex_list(self):
        workers = 12
        start = threading.Barrier(workers + 1)
        counts = {"dexes": 0, "exposure": 0, "portfolio": 0}
        count_lock = threading.Lock()

        def result(name, value):
            def call(*_args, **_kwargs):
                with count_lock:
                    counts[name] += 1
                time.sleep(0.02)
                return value
            return call

        builder = core.IntentBuilder.__new__(core.IntentBuilder)
        builder._leader_equity = {}
        builder._leader_equity_locks = {}
        builder._leader_equity_locks_guard = threading.Lock()
        builder._leader_dexes_lock = threading.Lock()
        builder._leader_dexes = None
        builder._leader_dexes_ms = 0
        saved = (core._XNET.list_perp_dexes, core._XNET.master_exposure, core._XNET.rolling_day_pnl)
        core._XNET.list_perp_dexes = result("dexes", {"ok": True, "dexes": [""]})
        core._XNET.master_exposure = result("exposure", {"ok": True, "equity_usd": 80.0})
        core._XNET.rolling_day_pnl = result("portfolio", {"ok": True, "account_value_usd": 100.0})
        try:
            def read_equity(index):
                start.wait()
                wallet = f"0x{index:040x}"
                return builder.leader_equity(wallet)

            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = [pool.submit(read_equity, index) for index in range(1, workers + 1)]
                start.wait()
                values = [future.result() for future in futures]
        finally:
            core._XNET.list_perp_dexes, core._XNET.master_exposure, core._XNET.rolling_day_pnl = saved

        self.assertEqual(values, [100.0] * workers)
        self.assertEqual(counts, {"dexes": 1, "exposure": workers, "portfolio": workers})


if __name__ == "__main__":
    main()
