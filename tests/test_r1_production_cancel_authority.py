"""R1: execute the exact production SenderGateway cancellation methods, without SDK/network access.

The test extracts unchanged method ASTs from the committed service file (not reimplementations).
The only fake is the external exchange boundary; a physical cancel is observable there.
Run: python -m pytest -q tests/test_r1_production_cancel_authority.py
"""
import ast
import csv
import json
import re
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

SOURCE = Path(__file__).resolve().parents[1] / "_archive/hl_stage2/HL_Live_Copy_Service_Core.py"
METHODS = {"_resting_key", "_resting_send_proven", "_resting_quarantined",
           "_claim_rows", "_withdraw_rows", "_cancel_order"}


class ExchangeSpy:
    def __init__(self):
        self.calls = []

    def cancel(self, coin, oid):
        self.calls.append((coin, oid))
        return {"response": {"data": {"statuses": ["success"]}}}


class AuditSpy:
    def append_reconciliation(self, *args, **kwargs):
        pass


@pytest.fixture
def production(tmp_path):
    tree = ast.parse(SOURCE.read_text(encoding="utf-8-sig"))
    service = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "SenderGateway")
    selected = [n for n in service.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in METHODS]
    assert {n.name for n in selected} == METHODS, "production cancellation path changed"
    cls = ast.ClassDef(name="SenderGateway", bases=[], keywords=[], body=selected, decorator_list=[])
    module = ast.fix_missing_locations(ast.Module(body=[cls], type_ignores=[]))

    journal = tmp_path / "send_attempts.csv"
    registry = tmp_path / "resting_entry_orders.json"
    journal.write_text("cloid,exchange_order_id,coin,status\n", encoding="utf-8")
    registry.write_text("{}", encoding="utf-8")

    def read_csv_rows(path):
        with open(path, newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))

    def write_json(path, value):
        Path(path).write_text(json.dumps(value), encoding="utf-8")

    ns = {
        "Dict": dict, "List": list, "Any": object, "FOLLOWER_NETWORK": "testnet",
        "USER_WALLET": "0xfollower", "SEND_ATTEMPTS_CSV": journal,
        "RESTING_ENTRY_ORDERS_FILE": registry,
        "normalise_wallet": lambda v: str(v or "").lower(),
        "canonical_coin_key": lambda v: str(v or "").lower(),
        "generate_cloid": lambda intent: "cloid-" + intent,
        "read_csv_rows": read_csv_rows, "atomic_write_json": write_json,
        "json": json, "re": re, "utc_now_ms": lambda: 1000,
        "time": time, "_open_orders_send_begin": lambda: None,
        "_open_orders_send_end": lambda: None,
    }
    exec(compile(module, str(SOURCE), "exec"), ns)
    return SimpleNamespace(Gateway=ns["SenderGateway"], journal=journal, registry=registry)


def row(coin, intent="intent-a", oid="123"):
    return {"follower_account": "0xfollower", "dex": coin.split(":")[0] if ":" in coin else "",
            "coin": coin, "sdk_coin": coin.split(":")[-1], "oid": oid,
            "cloid": "cloid-" + intent, "intent_id": intent, "leader_wallet": "leader",
            "side": "BUY", "size": 1, "limit_px": 100}


def start_gateway(env, exchange):
    # An uninitialized instance avoids constructor network/SDK and uses the actual
    # SenderGateway methods, including its _cancel_order -> exchange.cancel call.
    gateway = env.Gateway.__new__(env.Gateway)
    gateway._resting_lock = threading.RLock()
    gateway._resting_entries = json.loads(env.registry.read_text(encoding="utf-8"))
    gateway._resting_quarantine = {}
    gateway._reserve_exchange_order_slot = lambda: 1000
    gateway._exchange_client_for_coin = lambda coin: (exchange, coin.split(":")[-1])
    gateway.audit = AuditSpy()
    return gateway


def persist(env, gateway, rows):
    gateway._resting_entries = {gateway._resting_key(r) or "legacy:" + r["oid"]: r for r in rows}
    env.registry.write_text(json.dumps(gateway._resting_entries), encoding="utf-8")


def journal_send(env, r):
    with env.journal.open("a", encoding="utf-8") as f:
        f.write(f'{r["cloid"]},{r["oid"]},{r["coin"]},ORDER_RESTING\n')


def attempt_withdraw(gateway):
    with gateway._resting_lock:
        claimed = gateway._claim_rows(list(gateway._resting_entries.values()))
    gateway._withdraw_rows(claimed, "test withdraw", "")


def test_legacy_oid_only_cannot_physically_cancel_after_disk_restart(production):
    ex = ExchangeSpy()
    gateway = start_gateway(production, ex)
    legacy = {"oid": "123", "coin": "xyz:BTC", "sdk_coin": "BTC", "side": "BUY"}
    persist(production, gateway, [legacy])
    del gateway
    restored = start_gateway(production, ex)  # reads registry JSON afresh
    assert len(restored._resting_entries) == 1
    attempt_withdraw(restored)
    assert ex.calls == []


def test_same_oid_wrong_dex_cannot_physically_cancel_after_disk_restart(production):
    ex = ExchangeSpy()
    gateway = start_gateway(production, ex)
    authorized = row("xyz:BTC", "owned", "123")
    foreign = row("abc:BTC", "foreign", "123")
    journal_send(production, authorized)  # ownership belongs to xyz only, not abc
    persist(production, gateway, [foreign])
    del gateway
    restored = start_gateway(production, ex)
    assert len(restored._resting_entries) == 1
    attempt_withdraw(restored)
    assert ex.calls == []


def test_proven_same_dex_calls_real_cancel_order_once(production):
    ex = ExchangeSpy()
    gateway = start_gateway(production, ex)
    authorized = row("xyz:BTC", "owned", "123")
    journal_send(production, authorized)
    persist(production, gateway, [authorized])
    del gateway
    restored = start_gateway(production, ex)
    attempt_withdraw(restored)
    assert ex.calls == [("BTC", 123)]
    assert json.loads(production.registry.read_text(encoding="utf-8")) == {}
