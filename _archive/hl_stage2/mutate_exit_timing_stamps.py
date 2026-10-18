#!/usr/bin/env python3
"""Mutation harness for EXIT timing stamps: delete or pin stamps, expect test failure.

Usage:
  HL_EXIT_STAMP_MODULE_DIR=<dir with mutated copy> python test_core_exit_timing_stamps.py

The harness creates a temporary copy of HL_Live_Copy_Service_Core.py, applies a
mutation, and runs the test suite in a subprocess. Each mutation must cause the
test to fail (non-zero exit). If any mutation passes, the harness fails.

Mutations:
  * DELETE_<STAMP>   -- delete the two assignments for <STAMP> from the source
  * PIN_<STAMP>_CONST -- replace the two assignments with constant values (0)

Stamps: standing_close_started_ms, standing_close_finished_ms,
        close_plan_started_ms, close_plan_finished_ms,
        exchange_net_started_ms, exchange_net_finished_ms
"""
import os
import sys
import tempfile
import shutil
import subprocess
import textwrap

MODULE = 'HL_Live_Copy_Service_Core.py'
TEST = 'test_core_exit_timing_stamps.py'

STAMP_PAIRS = [
    'standing_close_started_ms',
    'standing_close_finished_ms',
    'close_plan_started_ms',
    'close_plan_finished_ms',
    'exchange_net_started_ms',
    'exchange_net_finished_ms',
]

def stamp_lines(stamp):
    """Return the two lines that assign the stamp (started_ms and finished_ms)."""
    return [
        f'timing["{stamp}"] = utc_now_ms()',
    ]

def delete_stamp_pair(src, stamp):
    lines = src.splitlines(keepends=True)
    out = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.strip() == f'timing["{stamp}"] = utc_now_ms()':
            # Skip this line and the next (finished_ms) if it follows immediately
            # Look ahead for the finished_ms line (allow blank lines/comments)
            j = i + 1
            while j < len(lines) and lines[j].strip() == '':
                j += 1
            if j < len(lines) and lines[j].strip() == f'timing["{stamp.replace("started", "finished")}"] = utc_now_ms()':
                # Skip both lines
                i = j + 1
                continue
            # If not paired, just skip this one
            i += 1
            continue
        out.append(line)
        i += 1
    return ''.join(out)

def pin_stamp_pair(src, stamp):
    lines = src.splitlines(keepends=True)
    out = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.strip() == f'timing["{stamp}"] = utc_now_ms()':
            # Replace with constant 0
            out.append(f'timing["{stamp}"] = 0\n')
            # Skip the finished_ms line and replace it too
            j = i + 1
            while j < len(lines) and lines[j].strip() == '':
                j += 1
            if j < len(lines) and lines[j].strip() == f'timing["{stamp.replace("started", "finished")}"] = utc_now_ms()':
                out.append(f'timing["{stamp.replace("started", "finished")}"] = 0\n')
                i = j + 1
                continue
            i += 1
            continue
        out.append(line)
        i += 1
    return ''.join(out)

def run_test_with_module(module_dir):
    env = os.environ.copy()
    env['HL_EXIT_STAMP_MODULE_DIR'] = module_dir
    # Use the same python that runs this script
    result = subprocess.run(
        [sys.executable, '-u', TEST],
        cwd=module_dir,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.returncode, result.stdout, result.stderr

def main():
    # Start from the original module in the worktree
    orig_dir = os.path.dirname(os.path.abspath(__file__))
    orig_module = os.path.join(orig_dir, MODULE)
    if not os.path.exists(orig_module):
        print(f"ERROR: {orig_module} not found", file=sys.stderr)
        sys.exit(1)

    failures = []
    for stamp in STAMP_PAIRS:
        print(f"\n=== Testing DELETE_{stamp} ===", flush=True)
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copy(orig_module, tmp)
            mod_path = os.path.join(tmp, MODULE)
            with open(mod_path, 'r', encoding='utf-8-sig') as f:
                src = f.read()
            mutated = delete_stamp_pair(src, stamp)
            with open(mod_path, 'w', encoding='utf-8') as f:
                f.write(mutated)
            code, out, err = run_test_with_module(tmp)
            if code == 0:
                failures.append(f"DELETE_{stamp} unexpectedly PASSED")
                print(f"STDOUT:\n{out}", file=sys.stderr)
                print(f"STDERR:\n{err}", file=sys.stderr)
            else:
                print(f"DELETE_{stamp} FAILED as expected (exit {code})", flush=True)

        print(f"\n=== Testing PIN_{stamp}_CONST ===", flush=True)
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copy(orig_module, tmp)
            mod_path = os.path.join(tmp, MODULE)
            with open(mod_path, 'r', encoding='utf-8-sig') as f:
                src = f.read()
            mutated = pin_stamp_pair(src, stamp)
            with open(mod_path, 'w', encoding='utf-8') as f:
                f.write(mutated)
            code, out, err = run_test_with_module(tmp)
            if code == 0:
                failures.append(f"PIN_{stamp}_CONST unexpectedly PASSED")
                print(f"STDOUT:\n{out}", file=sys.stderr)
                print(f"STDERR:\n{err}", file=sys.stderr)
            else:
                print(f"PIN_{stamp}_CONST FAILED as expected (exit {code})", flush=True)

    if failures:
        print("\n=== MUTATION TEST FAILURES ===", file=sys.stderr)
        for f in failures:
            print(f, file=sys.stderr)
        sys.exit(1)
    else:
        print("\n=== ALL MUTATIONS CAUSED TEST FAILURE ===")
        sys.exit(0)

if __name__ == '__main__':
    main()