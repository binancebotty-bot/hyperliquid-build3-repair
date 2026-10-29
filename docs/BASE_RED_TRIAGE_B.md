# BASE_RED_TRIAGE_B — unparseable test output at a1acc28

Scope: `_archive/hl_stage2/`, commit `a1acc28`, interpreter `C:/Users/wigmore/AppData/Local/Programs/Python/Python311/python.exe`. Probe: `tools/triage/probe_no_total.py` (read-only w.r.t. tests). Raw table: `docs/BASE_RED_TRIAGE_B_raw.md`.

## What was measured

| metric | value | how |
|---|---|---|
| `test_*.py` files present | 167 | `glob(test_*.py)` |
| stdout has `TOTAL=` | 133 | substring |
| stdout has no `TOTAL=` | 34 | same |
| exit non-zero | 24 | returncode |
| timed out (120s) | 0 | `subprocess.run(timeout=120)` |
| `TOTAL=…FAILED=n`, n>0 | 14 | regex |
| verdict-bearing failure (`FAILED: n>0`, `FAILED (failures=n)`, `^FAIL `, `RESULT::*_FAIL`) | 18 | both streams |
| exit non-zero with no verdict (crash) | 6 | returncode minus verdict |

No file hung in either pass; a second full sweep of all 167 with `timeout 120` produced zero exit-124s. Timeouts are not a defect class at this commit.

## Per-class counts (34 no-`TOTAL=` files)

| class | count |
|---|---|
| SILENT_PASS | 24 |
| IMPORT_CRASH | 6 |
| HANGS / TIMEOUT | 0 |
| NO_ASSERTIONS | 0 |
| SKIPS_ITSELF | 0 |
| UNDECIDED | 0 |
| FAILS_WITHOUT_TOTAL (note) | 4 |

Taxonomy note: four files fail and say so unambiguously but do not use `TOTAL=`. They are neither silent nor undecided, so forcing them into SILENT_PASS or UNDECIDED would be false; they are reported as a clearly-labelled seventh group.

### SILENT_PASS (24)

Three idioms:

- local `check()` harness printing `PASS <name>` then `FAILED: 0`, exit 0 — `test_core_all_mids_dex_isolation.py`, `test_core_all_mids_dex_keys.py`, `test_core_follower_mid_dex_keys.py`, `test_core_snapshot_reads_every_dex.py`, `test_core_summary_account_value_sign.py`, `test_core_xyz_equity_not_double_source.py` (quoted final line: `FAILED: 0`).
- `RESULT::<name>_PASS` marker, exit 0 — `test_core_csv_field_limit.py`, `test_core_fill_trace_buffering.py`, `test_core_fill_trace_concurrency.py`, `test_core_fill_trace_retry.py`, `test_core_fill_trace_status_context.py`, `test_core_follower_volume_payload.py`, `test_core_trace_rotation.py`, `test_run_report_paging.py`, `test_ui_account_tile_all_dexes.py`, `test_ui_global_controls_preserve_unowned.py`, `test_csv_field_limit.py`, `test_g2_copy_correctness.py`, `test_g3_exchange_truth.py`.
- other positive forms — `test_core_latency_trace_details.py` prints `PASS: proc_end records rejection details, real replies, stage stamps, and blocked/exception outcomes` and asserts via nine `raise AssertionError(...)` sites, exit 0; `test_core_outage_paging.py` (7 asserts) ends `PASS retained=3333/14000 dense=14000/14000 pages=8`; `test_outage_classify_deferred.py` (6 asserts) ends `PASS test_outage_classify_deferred`.
- `unittest` summaries on **stderr**, exit 0 — `test_leader_equity_singleflight.py` (`Ran 2 tests … OK`), `test_single_exchange_order_callsite.py` (`Ran 1 test … OK`). A stdout-only reader sees empty files and calls them silent; they are not.

### IMPORT_CRASH (6) — the silent holes

Five die partway through, after having printed passing lines — worse than an import crash, because partial PASS output precedes the abort and a tail-reading harness records a pass.

| file | terminal exception | died at |
|---|---|---|
| `test_core_open_orders_cache.py` | `AttributeError: 'types.SimpleNamespace' object has no attribute '_master_gate_reason'` | line 55, after `RESULT::TWO_SWEEPS_ONE_CALL_INSIDE_TTL_PASS` |
| `test_core_release_send_guards.py` | `AttributeError: 'types.SimpleNamespace' object has no attribute '_master_gate_reason'` | line 51, before any output |
| `test_core_sender_key.py` | `AttributeError: 'StartupConfig' object has no attribute 'live_over_stream_cap'` | line 362, after **32** `RESULT::…_PASS` lines |
| `test_core_queue_timing_stamps.py` | `FileNotFoundError: [Errno 2] No such file or directory: 'c:\temp\queue_timing_stamps_…\fill_trace.jsonl'` | line 122, before any output |
| `test_core_rw12_retry_cloid.py` | `RecursionError: maximum recursion depth exceeded while calling a Python object` | line 208, before any output |
| `test_core_rw9_timeout_vs_429.py` | `RecursionError: maximum recursion depth exceeded while calling a Python object` | line 219, before any output |

`test_core_sender_key.py` is the sharpest case: 32 green `RESULT::` lines, then a traceback on stderr, exit 1, no `TOTAL=`. Any harness reading the tail of stdout records it green.

### FAILS_WITHOUT_TOTAL (4)

- `test_core_deferred_entry_refusal.py` — exit 1; `RESULT::R1_STALE_THEN_FRESH_WITHIN_TOLERANCE_TAKES_FAIL`, `RESULT::R6_ORD_010_OLD_ENTRY_TAKES_THE_RULE_WITH_SWITCH_OFF_FAIL`.
- `test_core_r1_cursor.py` — exit 1; four `_FAIL` markers incl. `RESULT::queued_fill_holds_cursor_FAIL`, `RESULT::crash_replay_rereads_all_unprocessed_FAIL`.
- `test_core_slot_reservation_pacing.py` — exit 1; unittest summary on stderr `FAILED (failures=3)`, e.g. `AssertionError: 0 != 32`.
- `test_request_weight_followup.py` — exit 1; stderr `FAILED (failures=1)`, `AssertionError: 0 != 100000`.

### HANGS / TIMEOUT (0)

No file exceeded 120 s in either pass; none came close.

### NO_ASSERTIONS / SKIPS_ITSELF / UNDECIDED (0)

Every zero-exit no-`TOTAL=` file either asserts, raises `AssertionError` explicitly, or emits `RESULT::…_PASS`. No file printed a skip reason. Nothing undecided.

## The defect this measures

34 files (20% of the suite) cannot be judged by the `TOTAL=` contract the runner uses. 24 genuinely pass and are merely invisible to it. 6 crash, and 2 of those crash *after* emitting passing lines — the failure mode that turns red into green.

## RECONCILIATION

Three numbers were in circulation for one commit. All three reproduce; none means what it looks like.

**1. `test_*.py` files that exist: 167.** `glob(os.path.join(d, "test_*.py"))` in `_archive/hl_stage2/` at `a1acc28`.

**2. Files the full-suite runner counted: 124.** `C:/tmp/oc_wt_suite/runner/fullreg.py` line 25:

```python
files = sorted(os.path.basename(p) for p in glob.glob(d + r"\test_core_*.py"))
```

line 26 appends `test_c7_b1_cooldown_regression.py` if present; it is not present at this commit, so the append contributes nothing.

**The filter is the filename prefix `test_core_`.** A glob, not a discovery walk, not derived from any manifest. It silently excludes **43 files** — every `test_*.py` not beginning with `test_core_`, including `test_g2_copy_correctness.py`, `test_g3_exchange_truth.py`, `test_live_screen_truth.py`, `test_request_weight_followup.py`, `test_t1a_cloid_pending_row.py` and 38 others, five of which are non-zero. Nothing in the runner records that they exist.

**3. Where "19 failures" comes from:** `fullreg.py` decides pass/fail purely on `rc == 0` (line 41; report line `pass=sum(v['rc']==0 …) fail=sum(v['rc']!=0 …)`). Among the 124 it runs, **19** exit non-zero.

**4. Where "14 failures" comes from:** across all 167 files, exactly **14** emit `TOTAL=n FAILED=m` with `m > 0`.

The two governance counts are not in conflict — different denominator, different verdict function:

| claim | denominator | verdict function | value |
|---|---|---|---|
| full-suite runner | 124 (core only) | exit code != 0 | 19 |
| direct per-file | 167 (all) | `TOTAL=…FAILED=n>0` | 14 |

Neither states "how red is the suite". Two independent mistakes each yield a plausible integer:

- **The 124 denominator hides 43 files** — 26% under-report. It excludes the file with the largest single failure signature in this triage (`test_request_weight_followup.py`) purely on filename.
- **The 14 verdict under-reports by construction** — it can only see the 133 of 167 files that emit `TOTAL=`. Six files crash without a verdict and four fail without one; using `TOTAL=` as the oracle silently converts 10 known-red files into non-findings.
- **The 19 verdict over-reports relative to real assertions** — 6 of the 19 are crashes, not assertion failures, including `test_core_sender_key.py` (crashes after 32 passing checks).

**Which count a governance claim should quote.** The fully-enumerated count, with the verdict function stated alongside:

> At `a1acc28`, `_archive/hl_stage2/` contains **167** `test_*.py` files. Running every one directly, **24 exit non-zero**: **18** carry a verdict-bearing failure (`FAILED: n>0`, `FAILED (failures=n)`, or `RESULT::…_FAIL`) and **6** abort with an exception and no verdict. A further **34** files emit no `TOTAL=` line, so their status is not machine-readable by the suite's own contract even when they pass.

Why:

- 167 is a property of the repository; 124 is a property of a glob pattern. A future `test_copy_engine_x.py` would be invisible without anyone editing the runner.
- 24 requires no trust in any test's output format — it is observable from the process itself.
- 14 and 19 should be retired as headline figures: 14 is a lower bound produced by a contract 20% of the suite does not honour; 19 conflates "assertion failed" with "process died". The pair 18 + 6 separates them honestly.

The runner is not wrong to exist — 124 files in one command is useful. It is wrong to be the *source of a governance count* while its file list is a prefix glob and its verdict is exit code alone. To quote it: switch to `glob(test_*.py)` and distinguish crash from assertion failure.
