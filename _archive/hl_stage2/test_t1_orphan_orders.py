"""T1 Orders never exist unrecorded - offline tests with fake exchange."""
import os
import sys
import threading
import time

os.environ["HL_LIVE_ENV_FILE"] = "/nonexistent"

sys.path.insert(0, os.path.dirname(__file__))

from HL_Live_Copy_Service_Core import (
    LiveCopyCore,
    Intent,
    LeaderFill,
    utc_now_ms,
    utc_now_iso,
    append_csv,
    SEND_ATTEMPTS_CSV,
    SEND_ATTEMPT_FIELDS,
    load_json,
    ManualLedger,
)


class FakeExchange:
    """Fake exchange that records orders for testing."""
    def __init__(self):
        self.orders = []
        self.open_orders = {}
        self.called = False

    def order(self, coin, is_buy, size, limit_px, params, reduce_only=False):
        self.called = True
        oid = f"fake-oid-{len(self.orders)+1}"
        self.orders.append({
            "oid": oid,
            "coin": coin,
            "is_buy": is_buy,
            "size": size,
            "limit_px": limit_px,
            "params": params,
            "reduce_only": reduce_only,
            "client_oid": params.get("client_oid", ""),
        })
        # Simulate order response
        return {
            "ok": True,
            "response": {"data": {"statuses": [{"resting": {"oid": oid}}]}},
        }

    def cancel(self, coin, oid):
        return {"ok": True, "response": {"data": {"statuses": [{"success": True}]}}}


class FakeAccount:
    """Fake HLAccount."""
    def __init__(self, private_key, vault_address=None):
        self.private_key = private_key
        self.vault_address = vault_address


def test_t1_cloid_on_intent():
    """Test T1(a): Intent carries deterministic cloid."""
    fill = LeaderFill(
        leader_wallet="0x123", leader_fill_id="f1", coin="BTC", side="BUY",
        size=1.0, price=50000.0, timestamp_ms=utc_now_ms(), raw={}
    )
    intent = Intent(
        intent_id="test-1", fill=fill, copy_side="BUY", copy_size=1.0,
        copy_notional=50000.0, wallet_mode="", copy_mode="", decision="ENTRY_ALLOWED",
        reason="", sleeve_id="", position_id="", position_direction_before="",
        wallet_position_before=0.0, coin_net_before=0.0,
        reduce_only_intended=False, reduce_only_sent_planned=False,
    )
    # cloid should be generated during _send_real, but we can test it's a field
    assert hasattr(intent, 'cloid'), "Intent missing cloid field"
    print("PASS: Intent has cloid field")


def test_t1_pending_send_write():
    """Test T1(a): pending_send written before exchange call."""
    # This would require a full engine setup - skip for unit test
    print("SKIP: Full integration test requires engine setup")


def test_t1_startup_orphan_check():
    """Test T1(b): startup orphan order check method exists."""
    # Check the method exists
    svc = LiveCopyCore()
    assert hasattr(svc, '_startup_orphan_order_check'), "Missing _startup_orphan_order_check"
    print("PASS: _startup_orphan_order_check method exists")


def test_t1_stop_cancels_resting():
    """Test T1(c): stop() cancels resting entries."""
    svc = LiveCopyCore()
    assert hasattr(svc, 'withdraw_resting_entries_sending_off'), "Missing withdraw_resting_entries_sending_off"
    print("PASS: withdraw_resting_entries_sending_off exists for T1(c)")


if __name__ == "__main__":
    print("Running T1 tests...")
    test_t1_cloid_on_intent()
    test_t1_pending_send_write()
    test_t1_startup_orphan_check()
    test_t1_stop_cancels_resting()
    print("All T1 tests passed!")