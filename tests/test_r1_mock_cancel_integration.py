"""R1 simulated cancellation boundary: exercises fake exchange cancel, not production Gateway."""
from dataclasses import dataclass

@dataclass(frozen=True)
class Order:
    oid: str
    dex: str
    account: str
    coin: str
    send_proof: str = ""

class MockExchange:
    def __init__(self):
        self.cancel_calls = []
    def cancel(self, dex, account, coin, oid):
        self.cancel_calls.append((dex, account, coin, oid))

class MockCancelGateway:
    def __init__(self, exchange, account, dex, journal):
        self.exchange, self.account, self.dex, self.journal = exchange, account, dex, journal
    def withdraw(self, row):
        key = (row.oid, row.dex, row.account, row.coin)
        authoritative = self.journal.get(key)
        if (row.dex != self.dex or row.account != self.account or
            not row.send_proof or authoritative != row.send_proof):
            return "QUARANTINED_NO_CALL"
        self.exchange.cancel(row.dex, row.account, row.coin, row.oid)
        return "CANCELLED"

def test_legacy_oid_only_never_calls_cancel():
    exchange = MockExchange()
    gateway = MockCancelGateway(exchange, "acct-1", "dex-A", {})
    legacy = Order("123", "dex-A", "acct-1", "BTC")
    assert gateway.withdraw(legacy) == "QUARANTINED_NO_CALL"
    assert exchange.cancel_calls == []

def test_same_oid_different_dex_cannot_route_cancel():
    exchange = MockExchange()
    proof = "signed-send-1"
    gateway = MockCancelGateway(exchange, "acct-1", "dex-A",
        {("123", "dex-B", "acct-1", "BTC"): proof})
    foreign = Order("123", "dex-B", "acct-1", "BTC", proof)
    assert gateway.withdraw(foreign) == "QUARANTINED_NO_CALL"
    assert exchange.cancel_calls == []

def test_restart_restores_only_scoped_proven_ownership():
    exchange = MockExchange()
    journal = {("123", "dex-A", "acct-1", "BTC"): "signed-send-1"}
    restarted = MockCancelGateway(exchange, "acct-1", "dex-A", dict(journal))
    assert restarted.withdraw(Order("123", "dex-A", "acct-2", "BTC", "signed-send-1")) == "QUARANTINED_NO_CALL"
    assert restarted.withdraw(Order("123", "dex-A", "acct-1", "BTC", "signed-send-1")) == "CANCELLED"
    assert exchange.cancel_calls == [("dex-A", "acct-1", "BTC", "123")]
