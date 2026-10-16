"""Validate LIFE2 evidence structure; no lifecycle certification claim."""
import json, pathlib
p=pathlib.Path(__file__).with_name("LIFE2_31e599c5f5.json")
d=json.loads(p.read_text())
assert d["register_ref"] == "main:certification/certification_matrix.json"
assert [r["id"] for r in d["rows"]] == ["F25-P07", "F25-P08", "F25-P09", "F25-P10"]
assert all(r["result"] == "NOT_TESTED" and r["missing_runtime"] for r in d["rows"])
print("PASS: 4 rows recorded NOT_TESTED; no lifecycle execution claimed")
