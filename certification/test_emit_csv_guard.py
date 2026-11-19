"""Two-way test for certification/emit_csv_from_json.py.

Red side: a JSON whose every row shares one result must be refused (exit 2, no CSV written).
Green side: a JSON with mixed results must emit one CSV row per record, verbatim.
"""
import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
EMITTER = HERE / "emit_csv_from_json.py"
COLUMNS = ["id", "area", "result", "tested_commit", "proof_network", "evidence",
           "verified", "verifier", "notes"]


def write_fixture(path, results):
    records = [{"id": f"ROW-{i:03d}", "area": "TEST", "result": r,
                "tested_commit": "abc1234", "proof_network": "TESTNET",
                "evidence": f"certification/results/row{i}.json", "verified": "",
                "verifier": "", "notes": f"row {i}"} for i, r in enumerate(results)]
    path.write_text(json.dumps({"schema": "hl_certification_matrix_v1",
                                "records": records}), encoding="utf-8")


def run(json_path, out_path):
    return subprocess.run([sys.executable, str(EMITTER), "--json", str(json_path),
                           "--out", str(out_path)], capture_output=True, text=True)


def test_uniform_result_refuses(tmp):
    src, out = tmp / "uniform.json", tmp / "uniform.csv"
    write_fixture(src, ["NOT_TESTED"] * 5)
    p = run(src, out)
    assert p.returncode == 2, f"exit {p.returncode}, stdout={p.stdout!r}, stderr={p.stderr!r}"
    assert "5" in p.stdout and "NOT_TESTED" in p.stdout, p.stdout
    assert not out.exists(), "emitter wrote a CSV despite refusing"


def test_mixed_results_emit_verbatim(tmp):
    src, out = tmp / "mixed.json", tmp / "mixed.csv"
    results = ["PASS", "FAIL", "NOT_TESTED", "BLOCKED", "PASS"]
    write_fixture(src, results)
    p = run(src, out)
    assert p.returncode == 0, f"exit {p.returncode}, stderr={p.stderr!r}"
    assert out.exists(), "no CSV written"
    with out.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert list(rows[0].keys()) == COLUMNS, list(rows[0].keys())
    assert len(rows) == len(results), f"{len(rows)} rows for {len(results)} records"
    by_id = {r["id"]: r for r in rows}
    for i, want in enumerate(results):
        got = by_id[f"ROW-{i:03d}"]["result"]
        assert got == want, f"ROW-{i:03d}: result {got!r} != JSON {want!r}"
        assert by_id[f"ROW-{i:03d}"]["tested_commit"] == "abc1234"


def main():
    cases = [test_uniform_result_refuses, test_mixed_results_emit_verbatim]
    failed = 0
    for case in cases:
        with tempfile.TemporaryDirectory() as td:
            try:
                case(Path(td))
                print(f"PASS {case.__name__}")
            except AssertionError as exc:
                failed += 1
                print(f"FAIL {case.__name__}: {exc}")
    print(f"TOTAL={len(cases)} FAILED={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
