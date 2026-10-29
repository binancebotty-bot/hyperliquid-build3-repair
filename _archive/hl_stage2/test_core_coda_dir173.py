"""C7-DIR-173: offline Track B close, recovery, identity, and terminal-proof tests.

No exchange, network, key, or runtime actions. Run: pytest -q test_core_coda_dir173.py
"""
import csv
from types import SimpleNamespace
import HL_Live_Copy_Service_Core as core
from test_core_coda_dir163_dust import setup, intent, ACCOUNT, LEADER, USER


def _order_response(size, price, oid=1):
    return {"status": "ok", "response": {"type": "order", "data": {"statuses": [
        {"filled": {"totalSz": str(size), "avgPx": str(price), "oid": oid}}
    ]}}}


def test_nonro_unknown_net_caps_engine_and_preserves_user_on_wire(monkeypatch, tmp_path):
    """Reviewer collision case: combined account -10, engine -5, USER -5,
    BUY 5 leaves exchange at USER -5 without modifying USER sleeve."""
    g = setup(monkeypatch, tmp_path)
    i = intent()
    i.copy_size = 9.0  # adversarial request > current ENGINE ownership
    i.fill.price = 100.0
    g.ledger.signed = -5.0
    g.ledger.user = -5.0
    g._fresh_exchange_net = lambda coin: None  # normal-size unknown -> non-RO
    ro, qty, skipped = g._close_wire_plan(i, 9.0, 2, lambda s: s * 100 >= 10, {})
    assert not skipped and ro is False and qty == 5.0
    wire, account = [], {"net": -10.0}
    g._master_gate_reason = lambda *args, **kwargs: ""
    g._reserve_exchange_order_slot = lambda **kwargs: core.utc_now_ms()
    g._note_sender_key_rejection = lambda *args: None
    g._begin_pending_send = lambda *args, **kwargs: None
    def physical(coin, is_buy, size, px, tif, **kwargs):
        wire.append((coin, is_buy, size, px, kwargs["reduce_only"]))
        account["net"] += (size if is_buy else -size)
        return _order_response(size, px)
    res = g._place_order(SimpleNamespace(order=physical), "NEAR", True, qty, 100.0,
                         "Ioc", ro, cloid="0x" + "1" * 32,
                         timing={"final_wire_min_notional": 10, "final_wire_sz_decimals": 2},
                         intent=i, path="test_exit")
    assert g._parse_hl_response(res)[1] == "ORDER_FILLED"
    assert wire == [("NEAR", True, 5.0, 100.0, False)]
    assert wire[0][2] <= abs(g.ledger.signed)
    assert account["net"] == -5.0
    assert g.ledger.sleeve(USER, "NEAR")["signed_size"] == -5.0


def test_sdk_account_resolution_shared_for_proof_and_reservation(monkeypatch, tmp_path):
    g = setup(monkeypatch, tmp_path)
    i = intent()
    monkeypatch.setattr(core, "USER_WALLET", "0x" + "a" * 40)
    assert g._sdk_order_account() == ACCOUNT
    assert g._follower_order_account_for_proof(allow_rebind=True) == ACCOUNT
    assert g._follower_order_account_for_proof() is None  # false-clear protection
    ok, why = g._reserve_close_wire(i, "NEAR", True, 0.1, 2.5, True, "0x" + "3" * 32, 10)
    assert ok, why
    assert list(g._close_reservations.values())[0]["account"] == ACCOUNT


def test_rejected_resting_close_attempt_can_queue_fresh_gtc(monkeypatch, tmp_path):
    g = setup(monkeypatch, tmp_path)
    i = intent()
    i.position_id = "p1"
    g.ledger.coin_net = lambda coin: -0.1
    monkeypatch.setattr(core, "STANDING_CLOSES_FILE", tmp_path / "standing.json")
    g._standing_closes = {}
    g._recovery_intent_ids = {i.intent_id}  # FAILED historical recovery must not block
    assert not g._exit_recovery_exists(i)
    g.cfg.master_switch_now = lambda: True
    g._resolve_coin = lambda coin: {
        "ok": True, "raw_coin": coin, "sdk_coin": coin, "min_order_value_usd": 10}
    g._recovery_send_hooks = lambda *args, **kwargs: ("0x" + "4" * 32, lambda: None)
    g._record_placed_order = lambda *args, **kwargs: None
    g.audit.append_reconciliation = lambda *args, **kwargs: None
    sent = []
    def fake_place(exchange, coin, is_buy, size, px, tif, ro, **kwargs):
        sent.append((coin, is_buy, size, px, tif, ro))
        return {"status": "ok", "response": {"type": "order", "data": {
            "statuses": [{"resting": {"oid": 17}}]}}}
    g._place_order = fake_place
    g._queue_exit_recovery_if_needed(
        SimpleNamespace(), "NEAR", i, i.fill.price, 0.1,
        {"status": "ok", "response": {"data": {"statuses": [
            {"error": "MinTradeNtl"}]}}}, "MinTradeNtl", sz_dec=2)
    assert sent == [("NEAR", True, 0.1, i.fill.price, "Gtc", True)]
    assert g._exit_recovery_exists(i)  # only accepted resting order inhibits duplicate
    assert g._standing_closes[i.sleeve_id]["oid"] == "17"


def test_terminal_clear_requires_open_order_and_terminal_record(monkeypatch, tmp_path):
    g = setup(monkeypatch, tmp_path)
    g.ledger.signed = 0.0
    row = {"leader_wallet": LEADER, "coin": "NEAR", "intent_id": "i1",
           "leader_fill_id": "f1", "state": "OPEN"}
    core.atomic_write_json(core.CLOSE_ESCALATIONS_FILE, {"NEAR-leader": row})
    g._trackb_escalations = {"NEAR-leader": row}
    g._fresh_exchange_net = lambda coin: 0.0
    proof = {"orders_clear": False, "terminal": False}
    g._trackb_fresh_open_orders_clear = lambda account, coin: proof["orders_clear"]
    g._trackb_terminal_close_evidence = lambda sleeve, row: proof["terminal"]
    assert g.clear_trackb_escalations() == 0
    proof["orders_clear"] = True
    assert g.clear_trackb_escalations() == 0  # no terminal row
    proof["orders_clear"] = False
    proof["terminal"] = True
    assert g.clear_trackb_escalations() == 0  # still outstanding order
    proof["orders_clear"] = True
    g.audit.append_reconciliation = lambda *a, **kwargs: None
    assert g.clear_trackb_escalations() == 1
    assert g._trackb_escalations == {}


def test_fresh_open_orders_uses_sdk_account_and_rejects_working_coin(monkeypatch, tmp_path):
    g = setup(monkeypatch, tmp_path)
    monkeypatch.setattr(core, "follower_dex_scope", lambda: [""])
    requests = []
    out = {"ok": True, "data": [{"coin": "NEAR", "oid": 17}]}
    def post(fetcher, payloads, url, timeout):
        requests.extend(payloads)
        return [out]
    monkeypatch.setattr(core, "_XNET", SimpleNamespace(post_many=post))
    assert not g._trackb_fresh_open_orders_clear(ACCOUNT, "NEAR")
    assert requests[0]["user"] == ACCOUNT
    out = {"ok": True, "data": []}
    # Change the result used by the same callable rather than returning cache.
    # An unreadable fresh exchange order read must retain the red close.
    def fresh(fetcher, payloads, url, timeout):
        return [out]
    monkeypatch.setattr(core, "_XNET", SimpleNamespace(post_many=fresh))
    assert g._trackb_fresh_open_orders_clear(ACCOUNT, "NEAR")
    out = {"ok": False, "data": None}
    assert not g._trackb_fresh_open_orders_clear(ACCOUNT, "NEAR")


def test_terminal_fill_requires_matching_final_sleeve_row(monkeypatch, tmp_path):
    g = setup(monkeypatch, tmp_path)
    p = tmp_path / "copy_fills.csv"
    monkeypatch.setattr(core, "LIVE_FILLS_CSV", p)
    monkeypatch.setattr(core, "RECONCILIATION_CSV", tmp_path / "reconciliation.csv")
    row = {"coin": "NEAR", "intent_id": "i1", "leader_wallet": LEADER}
    assert not g._trackb_terminal_close_evidence("NEAR-leader", row)
    core.append_csv(p, core.LIVE_FILL_FIELDS, {
        "intent_id": "i1", "sleeve_id": "NEAR-leader", "leader_wallet": LEADER,
        "coin": "NEAR", "fill_size": 0.1, "exchange_order_id": "17",
        "wallet_position_after": -0.1})
    assert not g._trackb_terminal_close_evidence("NEAR-leader", row)
    core.append_csv(p, core.LIVE_FILL_FIELDS, {
        "intent_id": "i1", "sleeve_id": "NEAR-leader", "leader_wallet": LEADER,
        "coin": "NEAR", "fill_size": 0.1, "exchange_order_id": "18",
        "wallet_position_after": 0.0})
    assert g._trackb_terminal_close_evidence("NEAR-leader", row)
