"""R1 v3 candidate source-bound regression checks."""
import ast
from pathlib import Path
CORE=Path(__file__).with_name("HL_Live_Copy_Service_Core.py")
def get(name):
    source=CORE.read_text(encoding="utf-8-sig")
    t=ast.parse(source)
    cls=next(x for x in t.body if isinstance(x,ast.ClassDef) and x.name=="SenderGateway")
    f=next(x for x in cls.body if isinstance(x,ast.FunctionDef) and x.name==name)
    return ast.get_source_segment(source,f)
def test_no_startup_adoption_or_cancel():
    assert "self._cancel_orphan_order(" not in get("startup_orphan_order_check")
    assert "self._adopt_orphan_order(" not in get("startup_orphan_order_check")
def test_legacy_and_cross_dex_hold():
    assert "follower_account" in get("_resting_key")
    assert "not key or self._resting_quarantined(r)" in get("_claim_rows")
    assert "self._resting_quarantined(row)" in get("_withdraw_rows")
def test_restoration_is_durable():
    assert "atomic_write_json(RESTING_ENTRY_QUARANTINE_FILE, replacement)" in get("restore_resting_quarantine")
