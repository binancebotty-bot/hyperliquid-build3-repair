"""Exercise the dry-run flip cap with real sizing, config, and audit files."""

import csv
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch


# The service probes this optional file on import. Keep the test independent of it.
_default_env = Path(__file__).resolve().parent.parent / "hl_stage2.env"
_path_exists = Path.exists
with patch.object(Path, "exists", lambda path: path != _default_env and _path_exists(path)):
    import HL_Live_Copy_Service as service


WALLET = "0x" + "a" * 40
COIN = "BTC"
BLOCKED = "BLOCKED_GLOBAL_MAX_ORDER_NOTIONAL"


class FlipCapTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="flip_cap_")
        self.addCleanup(tmp.cleanup)
        saved_paths = service.AUDIT_DIR, service.RAW_LEADER_FILLS_CSV
        self.addCleanup(service.configure_paths, *saved_paths)
        root = Path(tmp.name)
        service.configure_paths(root, root / "unused.csv")
        flags = patch.multiple(
            service, XTRUTH=None, TEST_INJECTION_ENABLED=True, LIVE_AUTO_SEND_ENABLED=False
        )
        flags.start()
        self.addCleanup(flags.stop)
        wallet_gate = patch.dict("os.environ", {"HL_LIVE_WALLET_GATE_FILE": str(root / "unused.json")})
        wallet_gate.start()
        self.addCleanup(wallet_gate.stop)
        self.copy_mode = "fixed"
        self.write_config(0)
        self.engine = service.DryRunLiveCopyService()
        self.actual_net = 0.0
        self.engine.account_net_provider = lambda coin: self.actual_net

    def write_config(self, cap):
        service.APP_CONFIG_FILE.write_text(json.dumps({
            "global_controls": {"max_order_notional_usd": cap},
            "wallets": {WALLET: {
                "mode": "LIVE", "enabled": True, "copy_mode": self.copy_mode,
                "fixed_notional": 1000.0, "norm_base": 100.0, "leader_equity_base": 100.0,
            }},
        }), encoding="utf-8")

    def fill(self, fill_id, signed_size):
        return service.LeaderFill(
            fill_id=fill_id, wallet=WALLET, coin=COIN,
            side="BUY" if signed_size > 0 else "SELL",
            price=100.0, size=abs(signed_size), signed_size_delta=signed_size,
            timestamp_ms=1000, timestamp_iso="", source="test", recording_method="test", raw={},
        )

    def process(self, fill_id, signed_size):
        self.engine.process_fill(self.fill(fill_id, signed_size), self.engine.load_config()[WALLET])

    def rows(self, path, fill_id):
        with path.open(newline="", encoding="utf-8-sig") as records:
            return [row for row in csv.DictReader(records) if row["leader_fill_id"] == fill_id]

    def test_over_cap_flip_from_flat_actual_keeps_ledgers_untouched(self):
        engine = self.engine
        # The leader is long and the follower has no row. The flip therefore plans a real OPEN.
        engine.apply_leader_event(engine.load_config()[WALLET], self.fill("seed", 10.0))
        engine.processed_ids.add("seed")
        keys = ("leader_event_positions", "leader_event_checkpoint", "fixed_sleeves", "accumulators")
        before = deepcopy({key: engine.state[key] for key in keys})
        self.write_config(500)

        self.process("flip", -20.0)

        intents = self.rows(service.ORDER_INTENTS_CSV, "flip")
        self.assertEqual([(row["status"], float(row["copy_notional"])) for row in intents],
                         [(BLOCKED, 1000.0)])
        self.assertEqual(engine.positions, {})
        self.assertEqual({key: engine.state[key] for key in keys}, before)
        self.assertEqual(engine.processed_ids, {"seed"})
        self.assertEqual(engine.in_flight, {})
        self.assertEqual(self.rows(service.WOULD_SEND_ORDERS_CSV, "flip"), [])
        self.assertEqual(self.rows(service.LIVE_FILLS_CSV, "flip"), [])
        self.assertEqual(engine.state["counters"]["entries_blocked_global_max_order_notional"], 1)

    def test_above_cap_opposite_sleeve_is_refused_while_flattening(self):
        self.process("seed", 10.0)
        self.actual_net = 10.0
        self.write_config(500)

        self.process("flip", -20.0)

        engine = self.engine
        self.assertEqual(engine.positions[engine.position_key(WALLET, COIN)]["signed_size"], 0.0)
        self.assertEqual(engine.fixed_sleeve_units(WALLET, COIN), 0.0)
        self.assertEqual(engine.leader_signed_by_wallet(COIN, engine.load_config()), {WALLET: -10.0})
        intents = self.rows(service.ORDER_INTENTS_CSV, "flip")
        self.assertEqual([(row["intent_type"], row["reduce_only"]) for row in intents],
                         [("EXIT", "True")])
        self.assertEqual(engine.state["counters"]["entries_blocked_global_max_order_notional"], 1)

    def test_at_cap_opposite_sleeve_is_deferred_until_flat(self):
        self.process("seed", 10.0)
        self.actual_net = 10.0
        self.process("add", 10.0)
        self.actual_net = 20.0
        self.write_config(1000)

        self.process("flip", -30.0)

        engine = self.engine
        self.assertEqual(engine.positions[engine.position_key(WALLET, COIN)]["signed_size"], 0.0)
        self.assertEqual(engine.fixed_sleeve_units(WALLET, COIN), 10.0)
        configs = engine.load_config()
        next_order = engine.convergence_order_for_coin(
            configs[WALLET], self.fill("probe", -1.0), configs, actual_net=0.0
        )["order"]
        self.assertEqual((next_order.action, next_order.side, next_order.size), ("OPEN", "SELL", 10.0))

    def test_invalid_cap_denies_proportional_flip_open_but_allows_flatten(self):
        self.copy_mode = "proportional"
        self.write_config(0)
        self.process("seed", 10.0)
        self.actual_net = 10.0
        self.write_config("invalid")

        self.process("flip", -20.0)

        engine = self.engine
        self.assertEqual(engine.positions[engine.position_key(WALLET, COIN)]["signed_size"], 0.0)
        engine.persist()
        restarted = service.DryRunLiveCopyService()
        configs = restarted.load_config()
        next_order = restarted.convergence_order_for_coin(
            configs[WALLET], self.fill("probe", 1.0), configs, actual_net=0.0
        )["order"]
        self.assertEqual(next_order.action, "NONE")
        self.assertEqual(engine.state["counters"]["entries_blocked_global_max_order_notional"], 1)


if __name__ == "__main__":
    unittest.main()
