#!/usr/bin/env python3
"""ENG-INV-08 step 2 ADDENDUM: revert control — fails on ASSERTION about hold behaviour.

This script:
1. Reverts ONLY the hold's replay wiring (the call site in _process_leader_fill_inner)
2. Runs the original ENG-INV-08 step 2 test (test_core_eng_inv_08_stale_held.py)
3. Shows the failure is an ASSERTION on hold behaviour (W_HOLD_CALL_IS_IN_ENTRY_PATH, etc.)
   NOT a missing-method error.
"""
from __future__ import annotations

import os
import sys
import tempfile
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
CORE_FILE = HERE / "HL_Live_Copy_Service_Core.py"
TEST_FILE = HERE / "test_core_eng_inv_08_stale_held.py"

def read_file(path: Path) -> str:
    return path.read_text(encoding='utf-8')

def write_file(path: Path, content: str) -> None:
    path.write_text(content, encoding='utf-8')

def main() -> None:
    # Backup original
    original_content = read_file(CORE_FILE)
    backup_path = CORE_FILE.with_suffix('.py.revert_backup')
    write_file(backup_path, original_content)
    print(f"Backed up original to {backup_path}")

    try:
        # Apply revert: remove the hold call site
        content = original_content
        
        # Find and remove the hold call site
        hold_call = '            if not converge and self._stale_held_hold(fill, intent, merged_ids):\n                return False, "STALE_HELD_ENTRY_HELD", intent\n'
        if hold_call in content:
            content = content.replace(hold_call, '')
            print("Applied revert: removed hold call site")
        else:
            # Try alternative formatting
            hold_call_alt = '            if not converge and self._stale_held_hold(fill, intent, merged_ids):\n                return False, "STALE_HELD_ENTRY_HELD", intent\n'
            if hold_call_alt in content:
                content = content.replace(hold_call_alt, '')
                print("Applied revert: removed hold call site (alt)")
            else:
                print("ERROR: Could not find hold call site to revert")
                # Show context around where it should be
                idx = content.find('_stale_held_hold')
                if idx >= 0:
                    print("Found _stale_held_hold at:", idx)
                    print("Context:", content[max(0,idx-200):idx+200])
                sys.exit(1)
        
        write_file(CORE_FILE, content)
        
        # Now run the original ENG-INV-08 step 2 test
        print("\n=== Running original ENG-INV-08 step 2 test on REVERTED engine ===\n")
        sys.path.insert(0, str(HERE))
        
        import subprocess
        result = subprocess.run([
            sys.executable, str(TEST_FILE)
        ], capture_output=True, text=True, cwd=str(HERE))
        
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        
        # Check for wire-level assertion failures (not missing-method)
        output = result.stdout
        wire_failures = [
            'W_HOLD_CALL_IS_IN_ENTRY_PATH_FAIL',
            'W_HOLD_CALL_PRECEDES_DEFER_FAIL',
            'W_HOLD_CALL_GUARDED_BY_NOT_CONVERGE_FAIL',
            'W_HOLD_RETURNS_HELD_NOT_BLOCKED_FAIL',
            'W_NO_HARD_BLOCK_CLASS_ADDED_FAIL',
            'W_HOLD_IS_OUTSIDE_ALERT_ONLY_GATE_WRAPPER_FAIL',
        ]
        
        found_assertion_failure = False
        for failure in wire_failures:
            if failure in output:
                print(f"\n✓ REVERT CONTROL PASSED: Assertion {failure} failed as expected")
                print("  This confirms the hold wiring is required in the entry path.")
                for line in output.split('\n'):
                    if failure in line:
                        print(f"  Failure detail: {line}")
                found_assertion_failure = True
                break
        
        if not found_assertion_failure:
            if "N_HOLD_METHOD_EXISTS_FAIL" in output or "the narrow hold is missing" in output:
                print("\n✗ REVERT CONTROL FAILED: Missing-method error (not an assertion on hold behaviour)")
                print("  This is the unacceptable failure mode.")
                sys.exit(1)
            else:
                print("\n? REVERT CONTROL UNCLEAR: No expected assertion failure found")
                print("  Exit code:", result.returncode)
                sys.exit(2)
        else:
            sys.exit(0)
            
    finally:
        # Restore original
        write_file(CORE_FILE, original_content)
        print(f"\nRestored original from {backup_path}")
        backup_path.unlink(missing_ok=True)


if __name__ == '__main__':
    main()