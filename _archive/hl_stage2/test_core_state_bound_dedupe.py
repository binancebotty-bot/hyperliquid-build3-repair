#!/usr/bin/env python3
"""Bound dedupe ids: export() keeps only a bounded tail (5000 ids) + counts in the JSON state file;
full sets are persisted in an append-only dedupe_ids.jsonl. 200k ids, write < 100ms CPU, JSON < 2MB.
Reload from JSONL restores all ids; migration from legacy JSON keys works.
Run: HL_LIVE_ENV_FILE=/nonexistent python test_core_state_bound_dedupe.py"""
import json
import os
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
tmp = Path(tempfile.mkdtemp(prefix="dedupe_bound_"))
os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LIVE_ENV_FILE": "/nonexistent"})
import HL_Live_Copy_Service_Core as c

R = []
def check(n, ok, d=""):
    R.append(bool(ok)); print("RESULT::%s_%s%s" % (n, "PASS" if ok else "FAIL", (" | " + str(d)) if d and not ok else ""))

state_dir = tmp / "hl_live_copy_audit"
state_dir.mkdir(parents=True, exist_ok=True)

# ---- 1. Bounded export: 200k ids, JSON < 2MB, write < 100ms CPU
N = 200_000
dedupe = c.DedupeStore(state_dir=state_dir)
for i in range(N):
    dedupe.accept_leader("leader_fill_%d" % i)
for i in range(N // 10):
    dedupe.accept_copy("copy_fill_%d" % i)

t0 = time.process_time()
exported = dedupe.export()
t1 = time.process_time()
cpu_ms = (t1 - t0) * 1000

json_size = len(json.dumps(exported).encode("utf-8"))
check("EXPORT_CPU_UNDER_100MS", cpu_ms < 100, "%.1fms" % cpu_ms)
check("JSON_UNDER_2MB", json_size < 2 * 1024 * 1024, "%d bytes" % json_size)
check("TAIL_LIMITED", len(exported["processed_leader_fill_ids"]) == c.DEDUPE_TAIL_LIMIT, len(exported["processed_leader_fill_ids"]))
check("COPY_TAIL_LIMITED", len(exported["processed_copy_fill_ids"]) == c.DEDUPE_TAIL_LIMIT, len(exported["processed_copy_fill_ids"]))
check("LEADER_COUNT_FULL", exported["processed_leader_fill_ids_total"] == N, exported["processed_leader_fill_ids_total"])
check("COPY_COUNT_FULL", exported["processed_copy_fill_ids_total"] == N // 10, exported["processed_copy_fill_ids_total"])

# ---- 2. JSONL persistence: flush and verify file exists
dedupe.flush_jsonl()
jsonl_path = state_dir / c.DEDUPE_IDS_JSONL_NAME
check("JSONL_EXISTS", jsonl_path.exists())
jsonl_lines = sum(1 for line in jsonl_path.open("r", encoding="utf-8") if line.strip())
check("JSONL_HAS_ALL_IDS", jsonl_lines == N + N // 10, jsonl_lines)

# ---- 3. Reload from JSONL restores all ids
dedupe2 = c.DedupeStore(state_dir=state_dir)
check("RELOAD_LEADER_ALL", len(dedupe2.processed) == N, len(dedupe2.processed))
check("RELOAD_COPY_ALL", len(dedupe2.processed_copy) == N // 10, len(dedupe2.processed_copy))
check("RELOAD_DEDUPE_WORKS", dedupe2.accept_leader("leader_fill_0") == False)
check("RELOAD_NEW_ID_ACCEPTED", dedupe2.accept_leader("new_id_after_reload") == True)

# ---- 4. Migration from legacy JSON format
tmp2 = Path(tempfile.mkdtemp(prefix="dedupe_migrate_"))
state_dir2 = tmp2 / "hl_live_copy_audit"
state_dir2.mkdir(parents=True, exist_ok=True)
legacy_leader = ["legacy_leader_%d" % i for i in range(5000)]
legacy_copy = ["legacy_copy_%d" % i for i in range(1000)]
legacy_state = {
    "processed_leader_fill_ids": legacy_leader,
    "processed_copy_fill_ids": legacy_copy,
    "live_start_ms": 12345,
}
# No JSONL exists yet -> migration should create it
dedupe3 = c.DedupeStore(state=legacy_state, state_dir=state_dir2)
jsonl_path2 = state_dir2 / c.DEDUPE_IDS_JSONL_NAME
check("MIGRATION_JSONL_CREATED", jsonl_path2.exists())
check("MIGRATION_LEADER_LOADED", len(dedupe3.processed) == 5000, len(dedupe3.processed))
check("MIGRATION_COPY_LOADED", len(dedupe3.processed_copy) == 1000, len(dedupe3.processed_copy))
check("MIGRATION_LIVE_START", dedupe3.live_start_ms == 12345)

# Verify migration JSONL content
mig_lines = [json.loads(l) for l in jsonl_path2.open("r", encoding="utf-8") if l.strip()]
mig_leader_ids = [r["id"] for r in mig_lines if r.get("type") == "leader"]
mig_copy_ids = [r["id"] for r in mig_lines if r.get("type") == "copy"]
check("MIGRATION_LEADER_IDS_MATCH", set(mig_leader_ids) == set(legacy_leader))
check("MIGRATION_COPY_IDS_MATCH", set(mig_copy_ids) == set(legacy_copy))

# ---- 5. Second reload from migrated JSONL
dedupe4 = c.DedupeStore(state_dir=state_dir2)
check("MIGRATION_RELOAD_LEADER", len(dedupe4.processed) == 5000)
check("MIGRATION_RELOAD_COPY", len(dedupe4.processed_copy) == 1000)


# ---- 6. Recency tail: keeps the MOST RECENT ids, not the lexicographically largest (FAILs without fix)
tail_ids = exported["processed_leader_fill_ids"]
check("TAIL_RECENCY_NEWEST_KEPT", "leader_fill_199999" in tail_ids, tail_ids[-3:])
check("TAIL_RECENCY_OLDEST_DROPPED", "leader_fill_0" not in tail_ids)
check("TAIL_PARTIAL_FLAG", exported["processed_leader_fill_ids_is_partial"] is True)
check("TAIL_SCHEMA_MARKER", exported["dedupe_state_schema"] == 2 and exported["dedupe_tail_limit"] == c.DEDUPE_TAIL_LIMIT)

# ---- 7. An id absent from the JSON tail but present in the JSONL is still deduped after reload
check("RELOAD_DEDUPE_OUTSIDE_TAIL", dedupe2.accept_leader("leader_fill_0") == False)
check("TAIL_EXCLUDES_OLD_ID", "leader_fill_0" not in exported["processed_leader_fill_ids"])

# ---- 8. flush_jsonl failure: batch retained + retried, never raised into the caller (FAILs without fix)
tmp5 = Path(tempfile.mkdtemp(prefix="dedupe_flushfail_"))
state_dir5 = tmp5 / "hl_live_copy_audit"
state_dir5.mkdir(parents=True, exist_ok=True)
(state_dir5 / c.DEDUPE_IDS_JSONL_NAME).mkdir()  # a directory where the file should be: every open() fails
d5 = c.DedupeStore(state_dir=state_dir5)
check("FLUSHFAIL_LOAD_FLAG_SET", d5.export()["dedupe_load_failed"] is True)
d5.accept_leader("retry_leader_1")
d5.accept_copy("retry_copy_1")
d5.flush_jsonl()  # must not raise
check("FLUSHFAIL_COUNTER", d5.export()["dedupe_jsonl_flush_failures"] == 1, d5.export()["dedupe_jsonl_flush_failures"])
check("FLUSHFAIL_BATCH_RETAINED", d5._jsonl_new_leader == ["retry_leader_1"] and d5._jsonl_new_copy == ["retry_copy_1"])
(state_dir5 / c.DEDUPE_IDS_JSONL_NAME).rmdir()  # clear the blocker
d5.flush_jsonl()  # retry must persist the retained batch
jsonl_path5 = state_dir5 / c.DEDUPE_IDS_JSONL_NAME
check("FLUSHFAIL_RETRY_PERSISTED", jsonl_path5.exists() and jsonl_path5.is_file())
lines5 = sum(1 for line in jsonl_path5.open("r", encoding="utf-8") if line.strip())
check("FLUSHFAIL_RETRY_WROTE_ALL", lines5 == 2, lines5)
d5b = c.DedupeStore(state_dir=state_dir5)
check("FLUSHFAIL_RELOAD_DEDUPES", d5b.accept_leader("retry_leader_1") == False and d5b.accept_copy("retry_copy_1") == False)

# ---- 9. Torn JSONL lines are counted, not silently skipped (FAILs without fix)
tmp6 = Path(tempfile.mkdtemp(prefix="dedupe_torn_"))
state_dir6 = tmp6 / "hl_live_copy_audit"
state_dir6.mkdir(parents=True, exist_ok=True)
jsonl_path6 = state_dir6 / c.DEDUPE_IDS_JSONL_NAME
with jsonl_path6.open("w", encoding="utf-8") as f:
    f.write(json.dumps({"type": "leader", "id": "torn_ok_1"}) + "\n")
    f.write("{this is not json\n")
    f.write(json.dumps({"type": "copy", "id": "torn_ok_2"}) + "\n")
d6 = c.DedupeStore(state_dir=state_dir6)
check("TORN_LINE_COUNTED", d6.export()["dedupe_jsonl_skipped_lines"] == 1, d6.export()["dedupe_jsonl_skipped_lines"])
check("TORN_LINE_VALID_LOADED", d6.accept_leader("torn_ok_1") == False and d6.accept_copy("torn_ok_2") == False)

# ---- 10. A failed JSONL load is fail-closed flagged (FAILs without fix)
tmp7 = Path(tempfile.mkdtemp(prefix="dedupe_loadfail_"))
state_dir7 = tmp7 / "hl_live_copy_audit"
state_dir7.mkdir(parents=True, exist_ok=True)
(state_dir7 / c.DEDUPE_IDS_JSONL_NAME).mkdir()  # directory: open() fails
d7 = c.DedupeStore(state_dir=state_dir7)
check("LOADFAIL_FLAG", d7.export()["dedupe_load_failed"] is True)

# ---- 11. Baseline re-run must not re-append ids already in processed_copy (FAILs without fix)
tmp8 = Path(tempfile.mkdtemp(prefix="dedupe_baseline_"))
state_dir8 = tmp8 / "hl_live_copy_audit"
state_dir8.mkdir(parents=True, exist_ok=True)
d8 = c.DedupeStore(state_dir=state_dir8)
fills = [{"copy_fill_id": "bh:t%d" % i, "hash": "bh", "tid": str(i), "time": 1000 + i} for i in range(50)]
d8.baseline_copy_account(fills)
d8.baseline_copy_account(fills)  # same fills again: no new ids, no new lines
d8.flush_jsonl()
jsonl_path8 = state_dir8 / c.DEDUPE_IDS_JSONL_NAME
lines8 = sum(1 for line in jsonl_path8.open("r", encoding="utf-8") if line.strip())
check("BASELINE_RERUN_NO_DUP_LINES", lines8 == 50, lines8)
d8b = c.DedupeStore(state_dir=state_dir8)
check("BASELINE_RELOAD_DEDUPES", d8b.accept_copy("bh:t49:49") == False)

# ---- 12. Compaction: file past the bound is rewritten atomically, no tmp left, nothing lost
old_compact = c.DEDUPE_JSONL_COMPACT_LINES
c.DEDUPE_JSONL_COMPACT_LINES = 10
try:
    tmp9 = Path(tempfile.mkdtemp(prefix="dedupe_compact_"))
    state_dir9 = tmp9 / "hl_live_copy_audit"
    state_dir9.mkdir(parents=True, exist_ok=True)
    d9 = c.DedupeStore(state_dir=state_dir9)
    for i in range(15):
        d9.accept_leader("compact_%d" % i)
    d9.flush_jsonl()
    jsonl_path9 = state_dir9 / c.DEDUPE_IDS_JSONL_NAME
    lines9 = sum(1 for line in jsonl_path9.open("r", encoding="utf-8") if line.strip())
    check("COMPACT_REWRITTEN", lines9 == 15, lines9)
    check("COMPACT_NO_TMP_LEFT", not (state_dir9 / (c.DEDUPE_IDS_JSONL_NAME + ".compact.tmp")).exists())
    for i in range(15, 20):
        d9.accept_leader("compact_%d" % i)
    d9.flush_jsonl()
    lines9b = sum(1 for line in jsonl_path9.open("r", encoding="utf-8") if line.strip())
    check("COMPACT_SECOND_PASS", lines9b == 20, lines9b)
    d9b = c.DedupeStore(state_dir=state_dir9)
    check("COMPACT_RELOAD_DEDUPES", all(d9b.accept_leader("compact_%d" % i) == False for i in range(20)))
finally:
    c.DEDUPE_JSONL_COMPACT_LINES = old_compact

print("TOTAL=%d FAILED=%d" % (len(R), R.count(False))); sys.exit(1 if False in R else 0)
