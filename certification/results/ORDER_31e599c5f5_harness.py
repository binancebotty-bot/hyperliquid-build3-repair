#!/usr/bin/env python3
"""Harness for ORDER_31e599c5f5.json - verifies the certification result independently."""

import json
import sys
from pathlib import Path


def verify_result(result_path: Path) -> int:
    """Verify the ORDER certification result."""
    with result_path.open(encoding="utf-8") as f:
        data = json.load(f)

    print(f"Verifying {result_path.name}")
    print(f"  Task: {data.get('task_id')}")
    print(f"  Tested commit: {data.get('tested_commit')}")
    print(f"  Tested at: {data.get('tested_at_utc')}")
    print(f"  Overall: {data.get('summary', {}).get('overall')}")

    checks = data.get("checks", {})
    negative_tests = data.get("negative_tests", [])
    summary = data.get("summary", {})

    # Verify all 9 target rows are present
    target_rows = ["ORD-001", "ORD-002", "ORD-003", "ORD-004", "ORD-005", "ORD-006", "ORD-007", "ORD-008", "TN-F05"]
    for row in target_rows:
        if row not in checks:
            print(f"  FAIL: Missing row {row}")
            return 1
        row_checks = checks[row]
        if not row_checks:
            print(f"  FAIL: Row {row} has no checks")
            return 1
        for check in row_checks:
            name = check.get("name")
            passed = check.get("pass")
            detail = check.get("detail", "")
            print(f"  {row}.{name}: {'PASS' if passed else 'FAIL'} - {detail}")

    # Verify negative tests
    print(f"\nNegative tests ({len(negative_tests)}):")
    for nt in negative_tests:
        mutation = nt.get("mutation")
        actual = nt.get("actual")
        non_vacuous = nt.get("non_vacuous")
        detail = nt.get("detail", "")
        print(f"  {mutation}: actual={actual}, non_vacuous={non_vacuous} - {detail}")

    # Verify summary consistency
    total_checks = summary.get("total_checks", 0)
    passed_checks = summary.get("passed_checks", 0)
    total_negative = summary.get("total_negative", 0)
    non_vacuous_negative = summary.get("non_vacuous_negative", 0)

    if total_checks != len(target_rows):
        print(f"  FAIL: summary.total_checks ({total_checks}) != number of target rows ({len(target_rows)})")
        return 1

    if passed_checks != 0:
        print(f"  FAIL: summary.passed_checks ({passed_checks}) != 0 (all NOT_TESTED)")
        return 1

    if total_negative != len(target_rows):
        print(f"  FAIL: summary.total_negative ({total_negative}) != number of target rows ({len(target_rows)})")
        return 1

    if non_vacuous_negative != 0:
        print(f"  FAIL: summary.non_vacuous_negative ({non_vacuous_negative}) != 0 (no runtime)")
        return 1

    if summary.get("overall") != "NOT_TESTED":
        print(f"  FAIL: summary.overall != 'NOT_TESTED'")
        return 1

    if not summary.get("note"):
        print(f"  FAIL: summary.note is missing")
        return 1

    print(f"\nAll verifications PASSED")
    print(f"  Total checks: {total_checks}")
    print(f"  Passed checks: {passed_checks}")
    print(f"  Total negative: {total_negative}")
    print(f"  Non-vacuous negative: {non_vacuous_negative}")
    print(f"  Overall: {summary.get('overall')}")

    return 0


if __name__ == "__main__":
    result_path = Path(__file__).with_name("ORDER_31e599c5f5.json")
    sys.exit(verify_result(result_path))