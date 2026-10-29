# Running the Core tests in this directory

## The rule: these are SCRIPTS, not pytest modules

Five files here define their own `def check(...)` helper and print `RESULT::...` lines. **They do not
import `pytest` or `unittest` and must never be collected or batched by a test runner.** Invoking them
through `pytest`, `python -m pytest`, or any batching harness either skips them entirely or reports a
green that never executed a single assertion.

Run each one as a script, one process per file:

```
python test_core_reduce_only_repair.py
```

Judge the outcome from the printed `TOTAL=` / `FAILED=` lines and the process exit code, not from a
runner's summary line.

### The five script-class files

| File | Shape | Exit behaviour |
|---|---|---|
| `test_core_batch_parallel.py` | `check()` + `RESULT::` | no `SystemExit` |
| `test_core_retry_send_integrity.py` | `check()` + `RESULT::` | no `SystemExit` |
| `test_core_audit_reduce_only_matches_wire.py` | `check()` + `RESULT::` | raises `SystemExit` |
| `test_core_reduce_only_repair.py` | `check()` + `RESULT::` | raises `SystemExit` |
| `test_core_standing_close_guard.py` | `check()` + `RESULT::` | raises `SystemExit` |

The `SystemExit` files terminate with a non-zero status on failure by design. A batching harness that
catches `SystemExit` (or treats it as a skip) will silently swallow the failure and report success.

## Use a clean worktree, and check it is actually clean

A directory whose *name* contains "clean" is not evidence that it is clean. Verify before trusting any
green:

```
git rev-parse HEAD          # must equal the sha you intend to certify
git status --porcelain      # must be empty
```

Uncommitted edits to a test file can turn a real failure into a false green. This happened on
2026-10-29: `test_core_audit_reduce_only_matches_wire.py` carried 16 uncommitted inserted lines and
reported `TOTAL=11 FAILED=0` from the dirty tree, while the same file at the same base sha in a clean
worktree reported `TOTAL=11 FAILED=8`. Every green produced from that tree was void.

## Use the interpreter that has the SDK

The Hyperliquid SDK is installed only under Python 3.11 on this host. Hermes' default `python` is newer
and lacks it, so engine calls return `SDK_UNAVAILABLE` — which is not a credential problem:

```
C:/Users/wigmore/AppData/Local/Programs/Python/Python311/python.exe test_core_<name>.py
```
