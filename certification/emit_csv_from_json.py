#!/usr/bin/env python3
"""Emit certification_matrix.csv from the existing certification_matrix.json.

The outcomes live in the JSON. certification/gen_matrix.py builds every record with
result="NOT_TESTED" and never reads certification/results, so re-running it would
erase the PASS/FAIL/BLOCKED rows. This derives the CSV from the JSON instead, copies
each record verbatim, and refuses to write a CSV whose result column is uniform.
"""
import argparse
import csv
import json
import os
import sys
from pathlib import Path

COLUMNS = ["id", "area", "result", "tested_commit", "proof_network", "evidence",
           "verified", "verifier", "notes"]
HERE = Path(__file__).resolve().parent
DEFAULT_JSON = os.environ.get("HL_CERT_MATRIX_JSON") or str(HERE / "certification_matrix.json")
DEFAULT_CSV = os.environ.get("HL_CERT_MATRIX_CSV") or str(HERE / "certification_matrix.csv")


def load_records(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    records = data["records"] if isinstance(data, dict) else data
    if not records:
        sys.exit(f"REFUSED: {path} holds no records; nothing to export")
    return records


def cell(value):
    """Verbatim copy: a missing/None field is an empty cell, never a substituted default."""
    if value is None:
        return ""
    return value if isinstance(value, str) else str(value)


def main():
    ap = argparse.ArgumentParser(description="Derive the certification CSV from the matrix JSON.")
    ap.add_argument("--json", default=DEFAULT_JSON, help="matrix JSON to read")
    ap.add_argument("--out", default=DEFAULT_CSV, help="CSV to write")
    args = ap.parse_args()

    records = load_records(args.json)

    # Guard: a uniform result column means the export is not carrying outcomes.
    results = {cell(r.get("result")) for r in records}
    if len(results) == 1:
        only = next(iter(results))
        print(f"REFUSED: all {len(records)} rows have result={only!r}. A uniform result column "
              f"means this export is not carrying outcomes; refusing to write {args.out}.")
        sys.exit(2)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, lineterminator="\r\n")  # matches the existing CSV's CRLF convention
        writer.writerow(COLUMNS)
        for record in records:
            writer.writerow([cell(record.get(col)) for col in COLUMNS])
    print(f"wrote {len(records)} rows to {out}")


if __name__ == "__main__":
    main()
