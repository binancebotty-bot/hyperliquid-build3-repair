"""Validate the bounded origin-only evidence artifact; never promote row status."""
import json
from pathlib import Path

EXPECTED = {"ENG-017", "ENG-018", "ENG-019", "ORD-009", "ORD-010", "SET-009"}

def validate(path: Path) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["register_ref"] == "origin/main:certification/certification_matrix.json"
    assert data["register_commit"].startswith("3ea99f4d")
    assert data["engine_commit"] == "b142cf88d389e791160f691aac3d936852b99975"
    rows = data["results"]
    assert len(rows) == 6
    assert {row["row_id"] for row in rows} == EXPECTED
    for row in rows:
        assert row["result"] == "NOT_TESTED"
        assert row["execution_proof"] and row["independent_oracle"]
        assert row["negative_tests"]
        assert row["missing_route"]

if __name__ == "__main__":
    import sys
    validate(Path(sys.argv[1]))
    print("PASS: six exact origin-only rows; declared proof/oracle/negatives retained; each remains NOT_TESTED with a named missing route.")
