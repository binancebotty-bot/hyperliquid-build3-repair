"""C7-DIR-163: offline Track B physical dust / sleeve reservation regressions.
No API or real exchange calls. Run: pytest -q test_core_coda_dir163_dust.py
"""
import os
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.setdefault("HL_LIVE_ENV_FILE", "/nonexistent/core_coda_dir163.env")
os.environ.setdefault("HL_LEADER_NETWORK", "testnet")
os.environ.setdefault("HL_FOLLOWER_NETWORK", "testnet")
import HL_Live_Copy_Service_Core as core


class Ledger:
    def __init__(self, signed=-0.1, user=-10.4):
        self.signed = signed
        self.user = user
    def sleeve(self, wallet, coin):
        return {"signed_size": self.user if wallet == USER else self.signed}

LEADER = "0x" + "d" * 40
USER = "0x" + "e" * 40
ACCOUNT = "0x" + "c" * 40


def setup(monkeypatch, tmp_path):
    monkeypatch.setattr(core, "CLOSE_RESERVATIONS_FILE", tmp_path / "close_claims.json")
    monkeypatch.setattr(core, "CLOSE_ESCALATIONS_FILE", tmp_path / "owed.json")
    monkeypatch.setattr(core, "USER_WALLET", ACCOUNT)
    monkeypatch.setenv("HL_LIVE_HL_ACCOUNT_ADDRESS", ACCOUNT)
    g = core.SenderGateway(core.ConfigManager(), core.AuditLogWriter(), Ledger())
    g._fresh_exchange_net = lambda coin: None
    return g


def intent():
    return SimpleNamespace(
        fill=SimpleNamespace(leader_wallet=LEADER, coin="NEAR", leader_fill_id="f1",
                             price=2.5, timestamp_ms=core.utc_now_ms()),
        sleeve_id="NEAR-leader", intent_id="i1", copy_side="BUY", copy_size=0.1,
        reduce_only_intended=True, notes="lifecycle=EXIT", copy_notional=0.25,
    )


def test_unknown_net_capped_ro_dust_sent_not_hold(monkeypatch, tmp_path):
    g = setup(monkeypatch, tmp_path)
    i = intent()
    # The planner cannot use intent-time position; the verified ledger owns -0.1.
    g._fresh_exchange_net = lambda coin: None
    planned = g._close_wire_plan(i, 0.1, 2, lambda q: q * 2.5 >= 10, {})
    assert planned == (True, 0.1, "")
    calls = []
    g._master_gate_reason = lambda *a, **k: ""
    g._reserve_exchange_order_slot = lambda **k: core.utc_now_ms()
    g._note_sender_key_rejection = lambda *a: None
    g._begin_pending_send = lambda *a, **k: None
    g._trackb_escalate(i, "UNKNOWN_NET_CAPPED_DUST_CLOSE")
    ex = SimpleNamespace(order=lambda coin, buy, qty, px, tif, **k:
        (calls.append((coin, buy, qty, tif, k)) or
         {"status":"ok","response":{"type":"order","data":{"statuses":[{"filled":{"totalSz":"0.1","avgPx":"2.5","oid":17}}]}}}))
    r = g._place_order(ex, "NEAR", True, planned[1], 2.5, "Ioc", planned[0],
                       timing={"final_wire_min_notional":10}, cloid="0x"+"1"*32,
                       intent=i, path="test_close")
    assert len(calls) == 1 and calls[0][0:3] == ("NEAR", True, 0.1)
    assert calls[0][4]["reduce_only"] is True
    assert r["status"] == "ok"
    assert g._trackb_escalations[i.sleeve_id]["state"] == "OPEN"


def test_subminimum_exchange_reject_owed_and_gtc_leader_price(monkeypatch, tmp_path):
    g = setup(monkeypatch, tmp_path)
    i = intent()
    g._master_gate_reason = lambda *a, **k: ""
    g._reserve_exchange_order_slot = lambda **k: core.utc_now_ms()
    g._begin_pending_send = lambda *a, **k: None
    g._note_sender_key_rejection = lambda *a: None
    calls = []
    def send(coin, buy, qty, px, tif, **kw):
        calls.append((qty, px, tif, kw["reduce_only"]))
        if len(calls) == 1:
            return {"status":"ok","response":{"type":"order","data":{"statuses":[{"error":"Order must have minimum value of $10"}]}}}
        return {"status":"ok","response":{"type":"order","data":{"statuses":[{"resting":{"oid":22}}]}}}
    ex = SimpleNamespace(order=send)
    g._trackb_escalate(i, "DUST_ORDER_OWED")
    first = g._place_order(ex, "NEAR", True, 0.1, 2.51, "Ioc", True,
                           timing={"final_wire_min_notional":10}, cloid="0x"+"2"*32,
                           intent=i, path="test_close")
    assert g._parse_hl_response(first)[1] == "ORDER_REJECTED"
    # Definitively refused IOC releases the reservation, so recovery can try once.
    second = g._place_order(ex, "NEAR", True, 0.1, i.fill.price, "Gtc", True,
                            timing={"final_wire_min_notional":10}, cloid="0x"+"3"*32,
                            intent=i, path="exit_recovery")
    assert g._parse_hl_response(second)[1] == "ORDER_RESTING"
    assert calls == [(0.1, 2.51, "Ioc", True), (0.1, 2.5, "Gtc", True)]
    assert g._trackb_escalations[i.sleeve_id]["state"] == "OPEN"


def test_user_inventory_and_two_parallel_closes_never_overclaim(monkeypatch, tmp_path):
    g = setup(monkeypatch, tmp_path)
    i = intent()
    gate = threading.Barrier(3)
    results = []
    def attempt(n):
        gate.wait()
        results.append(g._reserve_close_wire(i, "NEAR", True, 0.1, 2.5, True,
                                              "0x"+str(n)*32, 10))
    threads = [threading.Thread(target=attempt, args=(n,)) for n in (4,5)]
    for t in threads: t.start()
    gate.wait()
    for t in threads: t.join()
    assert sorted(ok for ok, _ in results) == [False, True]
    assert sum(float(r["size"]) for r in g._close_reservations.values()) <= 0.1 + 1e-9
    assert g.ledger.sleeve(USER, "NEAR")["signed_size"] == -10.4
    assert g.ledger.sleeve(LEADER, "NEAR")["signed_size"] == -0.1


def test_unresolved_timeout_holds_claim_until_proven_not_landed(monkeypatch, tmp_path):
    g = setup(monkeypatch, tmp_path)
    i = intent()
    good, _ = g._reserve_close_wire(i, "NEAR", True, .1, 2.5, True, "0x"+"6"*32, 10)
    assert good
    # Ambiguous outcome cannot be assumed to mean no fill, even if timeout.
    g._finish_close_wire("0x"+"6"*32, {"status":"err", "response":"timeout"})
    assert not g._reserve_close_wire(i, "NEAR", True, .1, 2.5, True, "0x"+"7"*32, 10)[0]

def test_certain_filled_claim_reconciles_before_second_wire(monkeypatch, tmp_path):
    g = setup(monkeypatch, tmp_path)
    i = intent()
    assert g._reserve_close_wire(i, "NEAR", True, 0.05, 2.5, True, "0x"+"a"*32, 10)[0]
    fill = {"status":"ok","response":{"type":"order","data":{"statuses":[{"filled":{"totalSz":"0.05", "oid":88}}]}}}
    g._finish_close_wire("0x"+"a"*32, fill)
    # Other slice of ENGINE sleeve exists, but wait until first fill reaches ledger.
    assert not g._reserve_close_wire(i, "NEAR", True, 0.05, 2.5, True, "0x"+"b"*32, 10)[0]
    g.ledger.signed = -0.05
    g._owned_fill_size = lambda oid: 0.05 if str(oid) == "88" else 0.0
    assert g._reserve_close_wire(i, "NEAR", True, 0.05, 2.5, True, "0x"+"b"*32, 10)[0]
    assert g.ledger.user == -10.4


def test_mismatched_read_wallet_rebinds_to_sdk_account(monkeypatch, tmp_path):
    g = setup(monkeypatch, tmp_path)
    monkeypatch.setattr(core, "USER_WALLET", "0x"+"a"*40)
    recorded = []
    monkeypatch.setattr(core, "follower_dex_scope", lambda: [""])
    monkeypatch.setattr(core, "_XNET", SimpleNamespace(master_exposure=lambda account, *args, **kw:
        (recorded.append(account) or {"ok":True, "by_coin":{"NEAR":{"net":-10.5}}})))
    assert g._fresh_exchange_net("NEAR") == -10.5
    assert recorded == [ACCOUNT]
    # Existing strict terminal-clear proof still refuses a misconfigured read account.
    assert g._follower_order_account_for_proof() is None

def test_timeout_error_reply_is_not_proven_reject(monkeypatch, tmp_path):
    g = setup(monkeypatch, tmp_path)
    i = intent()
    first = "0x"+"c"*32
    assert g._reserve_close_wire(i, "NEAR", True, .1, 2.5, True, first, 10)[0]
    g._finish_close_wire(first, {"status":"err", "response":"request timed out"})
    assert first in g._close_reservations
    assert not g._reserve_close_wire(i, "NEAR", True, .1, 2.5, True, "0x"+"d"*32, 10)[0]


def test_actual_nonreduce_only_subminimum_never_uses_exemption(monkeypatch, tmp_path):
    g = setup(monkeypatch, tmp_path)
    i = intent()
    accepted, reason = g._reserve_close_wire(i, "NEAR", True, .1, 2.5, False, "0x"+"e"*32, 10)
    assert not accepted and reason == "NON_REDUCE_ONLY_SUBMINIMUM_CLOSE"
    assert not g._close_reservations

def test_final_boundary_rejects_unrounded_close_size(monkeypatch, tmp_path):
    g = setup(monkeypatch, tmp_path)
    i = intent()
    key = "0x"+"f"*32
    assert g._reserve_close_wire(i, "NEAR", True, 0.005, 2.5, True, key, 10)[0]
    assert not g._verify_close_reserved_wire(i, key, True, .005, True, 2.5, 10, size_decimals=2)

def test_two_gateway_instances_cannot_close_same_coin_twice(monkeypatch, tmp_path):
    first = setup(monkeypatch, tmp_path)
    second = setup(monkeypatch, tmp_path)
    primary = intent()
    other = intent()
    other.fill = SimpleNamespace(leader_wallet="0x"+"b"*40, coin="NEAR")
    other.sleeve_id = "independent-engine-sleeve"
    second.ledger.sleeve = lambda wallet, coin: {"signed_size": -0.1}
    assert first._reserve_close_wire(primary, "NEAR", True, .1, 2.5, True, "0x"+"1"*32, 10)[0]
    accepted, why = second._reserve_close_wire(other, "NEAR", True, .1, 2.5, True, "0x"+"2"*32, 10)
    assert not accepted and why == "CLOSE_COIN_ALREADY_HAS_UNRECONCILED_WIRE"
    assert first.ledger.user == -10.4  # USER ledger untouched
    first._finish_close_wire("0x"+"1"*32, {"status":"ok","response":{"data":{"statuses":[{"error":"MinTradeNtl"}]}}})
    assert second._reserve_close_wire(other, "NEAR", True, .1, 2.5, True, "0x"+"2"*32, 10)[0]


def test_ro_flag_is_actual_wire_not_intent(monkeypatch, tmp_path):
    g = setup(monkeypatch, tmp_path)
    i = intent()
    cl = "0x"+"a"*32
    assert g._reserve_close_wire(i, "NEAR", True, .1, 2.5, True, cl, 10)[0]
    assert not g._verify_close_reserved_wire(i, cl, True, .1, False, 2.5, 10, 2)
    assert g._verify_close_reserved_wire(i, cl, True, .1, True, 2.5, 10, 2)
    assert not g._verify_close_reserved_wire(i, cl, False, .1, True, 2.5, 10, 2)
