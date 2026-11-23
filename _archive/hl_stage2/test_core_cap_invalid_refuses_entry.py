"""Exercise invalid cap handling through the fill planner and send gate."""

import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


_local_env = Path(__file__).resolve().parent.parent / "hl_stage2.env"
_path_exists = Path.exists
with patch.object(Path, "exists", lambda path: path != _local_env and _path_exists(path)):
    import HL_Live_Copy_Service as service


WALLET = "0x" + "a" * 40
COIN = "BTC"


class InvalidCapTest(unittest.TestCase):
    def test_invalid_cap_refuses_entry_and_add_and_allows_close(self):
        with tempfile.TemporaryDirectory(prefix="invalid_cap_") as tmp:
            root = Path(tmp)
            saved_paths = service.AUDIT_DIR, service.RAW_LEADER_FILLS_CSV
            self.addCleanup(service.configure_paths, *saved_paths)
            service.configure_paths(root, root / "unused.csv")

            def set_cap(cap):
                service.APP_CONFIG_FILE.write_text(json.dumps({
                    "global_controls": {"max_order_notional_usd": cap},
                    "wallets": {WALLET: {"mode": "LIVE", "enabled": True,
                                         "copy_mode": "fixed", "fixed_notional": 1000.0}},
                }), encoding="utf-8")

            def rows(path, fill_id):
                with path.open(newline="", encoding="utf-8-sig") as records:
                    return [row for row in csv.DictReader(records) if row["leader_fill_id"] == fill_id]

            with (
                patch.multiple(service, XTRUTH=None, TEST_INJECTION_ENABLED=True),
                patch.dict("os.environ", {"HL_LIVE_WALLET_GATE_FILE": str(root / "unused.json")}),
                patch.object(service.DryRunLiveCopyService, "maybe_auto_send_would_send") as send,
            ):
                engine = service.DryRunLiveCopyService()

                def position():
                    return float(engine.get_position(WALLET, COIN).get("signed_size") or 0.0)

                engine.account_net_provider = lambda coin: position()

                def process(fill_id, delta):
                    fill = service.LeaderFill(
                        fill_id=fill_id, wallet=WALLET, coin=COIN,
                        side="BUY" if delta > 0 else "SELL", price=100.0, size=abs(delta),
                        signed_size_delta=delta, timestamp_ms=1000, timestamp_iso="",
                        source="ws", recording_method="test", raw={},
                    )
                    engine.process_fill(fill, engine.load_config()[WALLET])

                def assert_blocked(fill_id, expected_position):
                    send.reset_mock()
                    process(fill_id, 10.0)
                    intent, = rows(service.ORDER_INTENTS_CSV, fill_id)
                    self.assertEqual(intent["status"], "BLOCKED_GLOBAL_CAP_INVALID")
                    self.assertEqual(intent["execution_decision"], "BLOCKED_GLOBAL_CAP_INVALID")
                    self.assertEqual(intent["decision_reason"], "GLOBAL_CAP_INVALID")
                    self.assertEqual(rows(service.WOULD_SEND_ORDERS_CSV, fill_id), [])
                    send.assert_not_called()
                    self.assertEqual(engine.in_flight, {})
                    self.assertEqual(position(), expected_position)

                set_cap("not-a-number")
                assert_blocked("entry", 0.0)

                set_cap(0.0)
                process("seed", 10.0)
                self.assertEqual(position(), 10.0)

                set_cap("not-a-number")
                assert_blocked("add", 10.0)

                process("close", -10.0)
                close, = rows(service.WOULD_SEND_ORDERS_CSV, "close")
                self.assertEqual(close["execution_decision"], "WOULD_REDUCE_OR_EXIT")
                self.assertEqual(close["reduce_only"], "True")
                send.assert_called_once()
                self.assertEqual(position(), 0.0)


if __name__ == "__main__":
    unittest.main()
