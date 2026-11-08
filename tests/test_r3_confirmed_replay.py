"""R3 strict replay: never partially apply, one staged replacement (offline)."""
import importlib.util
from pathlib import Path
import pytest
MOD=Path(__file__).resolve().parents[1]/"tools/cert/replay_confirmed_attempts.py"
spec=importlib.util.spec_from_file_location("r3_replay",MOD)
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
A="0x"+"a"*32
def rows():
    sends=[dict(attempt_id="a",cloid=A,status="pending_send",copy_size="2",leader_fill_id="leader")]
    confirmation=[dict(cloid=A,oid="123",status="FILLED",filled_size="2")]
    ledger=[dict(exchange_order_id="123",leader_fill_id="leader",copy_fill_id="f1",fill_size="2")]
    return sends,confirmation,ledger
def test_complete_preflight_then_idempotent():
    a,b,c=rows()
    end=mod.replay(a,b,c)
    assert len(end)==1
    assert mod.replay(a+end,b,c)==[]
def test_no_evidence_is_explicit_failure():
    a,b,c=rows()
    with pytest.raises(RuntimeError,match="R3_UNRESOLVED=1"):
        mod.replay(a,[],c)
def test_no_ledger_proof_is_explicit_failure():
    a,b,c=rows()
    with pytest.raises(RuntimeError,match="R3_UNRESOLVED=1"):
        mod.replay(a,b,[])
def test_non_strict_is_diagnostic_only():
    a,b,c=rows()
    assert mod.replay(a,[],c,strict=False)==[]
def test_conflicting_confirmation_refuses():
    a,b,c=rows()
    b.append(dict(cloid=A,oid="124",status="FILLED",filled_size="2"))
    with pytest.raises(RuntimeError,match="R3_UNRESOLVED=1"):
        mod.replay(a,b,c)
