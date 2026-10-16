"""Validate the bounded REGR2 artifact against main's committed register."""
import json
import subprocess
from pathlib import Path

EXPECTED = {"B4-I12", "B4-I13", "B4-I20", "B4-I21", "B4-I26", "F-EXC-017"}
ARTIFACT = Path(__file__).with_name("REGR2_f28341d1.json")


def main():
    matrix_bytes = subprocess.check_output(
        ["git", "show", "main:certification/certification_matrix.json"]
    )
    matrix = json.loads(matrix_bytes)
    records = {r["id"]: r for r in matrix["records"] if r["id"] in EXPECTED}
    assert set(records) == EXPECTED, ("register rows missing", EXPECTED - set(records))
    artifact = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    assert artifact["register_of_record"].startswith("main:certification/certification_matrix.json@")
    assert artifact["engine_commit"] == "f28341d1f02f76060c384844ab6aa439ddee976e"
    rows = {row["id"]: row for row in artifact["rows"]}
    assert set(rows) == EXPECTED, ("artifact rows mismatch", set(rows))
    for row_id, row in rows.items():
        source = records[row_id]
        assert row["register_result"] == source["result"] == "NOT_TESTED", row_id
        assert row["applicability"] == source["applicability"] == "OPEN_DECISION", row_id
        assert row["open_decisions"] == source["open_decisions"], row_id
        assert row["check_results"] == {"proof": "NOT_TESTED", "oracle": "NOT_TESTED", "negative": "NOT_TESTED"}, row_id
        assert row["missing_routes"], row_id
    assert artifact["overall"] == "NOT_TESTED"
    print("PASS: six exact main-register rows reconciled; all proof/oracle/negative checks remain NOT_TESTED with named missing routes")


if __name__ == "__main__":
    main()
