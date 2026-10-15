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
check("LEADER_COUNT_FULL", exported["processed_leader_fill_count"] == N, exported["processed_leader_fill_count"])
check("COPY_COUNT_FULL", exported["processed_copy_fill_count"] == N // 10, exported["processed_copy_fill_count"])

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

print("TOTAL=%d FAILED=%d" % (len(R), R.count(False))); sys.exit(1 if False in R else 0)
