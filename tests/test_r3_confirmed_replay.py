"""R3 replay: only independent OID+CLOID+ledger proof closes sends."""
from tools.cert.replay_confirmed_attempts import replay

C = "0x" + "1" * 32

def inputs():
    sends = [{"attempt_id": "a", "cloid": C, "exchange_order_id": "", "status": "pending_send",
              "copy_size": "2", "leader_fill_id": "leader-1"},
             {"attempt_id": "b", "cloid": "0x" + "2"*32, "exchange_order_id": "",
              "status": "pending_send", "copy_size": "1", "leader_fill_id": "leader-2"}]
    confirms = [{"cloid": C, "oid": "123", "status": "FILLED", "filled_size": "2"}]
    ledger = [{"exchange_order_id": "123", "leader_fill_id": "leader-1",
               "copy_fill_id": "fill-a", "fill_size": "2"}]
    return sends, confirms, ledger

def test_closes_only_exchange_and_ledger_proven_attempt():
    sends, confirms, ledger = inputs()
    rows = replay(sends, confirms, ledger)
    assert len(rows) == 1
    assert rows[0]["attempt_id"] == "a"
    assert rows[0]["exchange_order_id"] == "123"
    assert len(replay(sends + rows, confirms, ledger)) == 0

def test_missing_ledger_or_wrong_oid_cannot_claim_fill():
    sends, confirms, ledger = inputs()
    assert replay(sends, confirms, []) == []
    sends[0]["exchange_order_id"] = "124"
    assert replay(sends, confirms, ledger) == []

def test_conflicting_cloid_confirmation_cannot_close():
    sends, confirms, ledger = inputs()
    confirms.append({"cloid": C, "oid": "124", "status": "FILLED", "filled_size": "2"})
    assert replay(sends, confirms, ledger) == []

def test_partial_not_called_complete():
    sends, confirms, ledger = inputs()
    confirms[0]["filled_size"] = "1.999999999"
    assert replay(sends, confirms, ledger) == []
