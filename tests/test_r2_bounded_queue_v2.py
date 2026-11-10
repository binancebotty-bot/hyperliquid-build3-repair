"""R2 hot queue capacity contracts; source-level smoke checks (offline)."""
import ast
from pathlib import Path
CORE=Path(__file__).resolve().parents[1]/"_archive/hl_stage2/HL_Live_Copy_Service_Core.py"
text=CORE.read_text(encoding="utf-8-sig")
tree=ast.parse(text)
def cls(n):return next(x for x in tree.body if isinstance(x,ast.ClassDef) and x.name==n)
def method(c,n):return next(x for x in cls(c).body if isinstance(x,ast.FunctionDef) and x.name==n)
def source(c,n):return ast.get_source_segment(text,method(c,n))
def test_global_entry_and_close_admission():
    init=source("LiveCopyCore","__init__")
    assert "BoundedSemaphore(384)" in init and "BoundedSemaphore(96)" in init
    assert "maxsize=32" in source("WSManager","__init__")
def test_overflow_has_durable_retry_evidence():
    s=source("LiveCopyCore","_dispatch_fill")
    assert "HOT_QUEUE_CAP_AUDIT_FAILED" in s
    assert "durable=True" in s
def test_slot_kind_pinned_across_ledger_changes():
    assert "_queue_slot_kind.pop(_gk, None)" in source("LiveCopyCore","_release_queued")
def test_stale_reoffer_precedes_physical_send_key():
    s=source("LiveCopyCore","_process_leader_fill_inner")
    assert s.index('"QUEUE_STALE_ENTRY"') < s.index("self._past_send_keys.add(self._guard_key(fill))")
def test_startup_drain_covers_deferred_and_inflight():
    s=source("LiveCopyCore","drain_startup_hot_queue")
    assert "self._deferred" in s and "self._inflight" in s
