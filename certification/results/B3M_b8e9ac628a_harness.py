import json
from pathlib import Path

p = Path(__file__).with_name("B3M_b8e9ac628a.json")
d = json.loads(p.read_text(encoding="utf-8"))
assert d["row_id"] == "UI-FP-193"
assert d["register_ref"] == "main:certification/certification_matrix.json"
assert d["engine_commit"] == "b8e9ac628aaf60f94033f1eaf3b738573afb311a"
assert d["result"] == "NOT_TESTED"
assert len(d["checks"]) == 5
assert all(c["result"] in {"PASS", "FAIL", "NOT_TESTED"} for c in d["checks"])
assert all(c["result"] != "NOT_TESTED" or "MISSING ROUTE:" in c["detail"] for c in d["checks"])
print("PASS: UI-FP-193 evidence schema, row/ref/commit, and named missing routes verified")
