# TEST TRIAGE — the 15 files that produce NO VERDICT at a1acc28

CC-1 T-A (CH-8). Scope: the files the rebuilt gate runner cannot score, i.e. 6 CRASH + 9 NOT_RUN
out of 167. It does NOT cover the 18 assertion failures, which are a separate list.

**Measured, not inferred.** Baseline at a1acc28 with `tools/gate/fullreg.py` @ ae56046:

```
files=167 run | A=18 assertion failures | C=6 crashes | M=13 no TOTAL= | P=134 pass | T=0
dialects: TOTAL= 133 | RESULT:: 15 | RESULT::+die 2 | silent 9 | exitcode 4 | unittest 4
```

## The headline finding, which changes the recommendation

**All 9 NOT_RUN files are HARNESS_CONVENTION, not breakage. None of them is a delete candidate on
verdict grounds.** Each one runs, checks real behaviour, and then fails to leave a machine-readable
result. Three distinct mechanisms:

1. **A local `check()` helper that prints per-case but never summarises and never sets an exit code.**
   Seen verbatim in `test_core_all_mids_dex_isolation.py`:
   ```python
   def check(n, c, d=''):
       print(('PASS ' if c else 'FAIL ') + n + ((' :: ' + d) if d and not c else ''))
       if not c: FAIL.append(n)
   ```
   The file can run 40 green assertions, print 40 PASS lines, and exit 0 with no summary. To any
   reader, grep or gate this is indistinguishable from a file that ran nothing.
2. **A bare `"PASS"` print with no failure path in the summary.** `test_core_latency_trace_details.py`
   ends `print("PASS: proc_end records rejection details, real replies, stage stamps, and blocked/exception outcomes")`.
3. **Plain `assert` statements plus a PASS print.** `test_outage_classify_deferred.py` ends
   `assert subprocess.run([...]).returncode == 1` then `print("PASS test_outage_classify_deferred")`.
   Failure mode is an AssertionError and a traceback, which my adapter scores as CRASH — a defect
   that is really an assertion failure wearing a different coat.

The remedy for all three is **one summary line and an exit code per file**, which is a mechanical
change and does not touch the product. Converting them to a shared harness is the right next step and
is explicitly NOT a suite-wide rewrite: it is 15 files.

## The 6 CRASHES — these are real, and 4 of them are defect-shaped

| file | lines | error | cause class | verdict |
|---|---|---|---|---|
| `test_core_sender_key.py` | 362 | `AttributeError: 'StartupConfig' object has no attribute 'live_over_stream_cap'`, AFTER 32 `RESULT::..._PASS` lines | PRODUCT_MOVED — the test reads an attribute the object no longer has | REPAIR |
| `test_core_open_orders_cache.py` | 188 | `AttributeError: 'types.SimpleNamespace' object has no attribute '_master_gate_reason'` | STALE_HARNESS — the fake gateway no longer provides a method the code calls | REPAIR |
| `test_core_release_send_guards.py` | 96 | same `_master_gate_reason` AttributeError | STALE_HARNESS | REPAIR |
| `test_core_queue_timing_stamps.py` | 215 | `PermissionError: [WinError 32]` on a temp file | STALE_HARNESS — a file handle is still open when the test tries to reuse the path | REPAIR |
| `test_core_rw12_retry_cloid.py` | 208 | `RecursionError` in `hotswap.py` `_module_guard` | STALE_HARNESS — known; fixed copies exist at `3cff1fb85cd63b79cbef919448092c64dcd7fb4b` where it passes 7/0 | REPAIR (drop in the fixed copy) |
| `test_core_rw9_timeout_vs_429.py` | 219 | same RecursionError | STALE_HARNESS — same fix, passes 15/0 with it | REPAIR |

`test_core_sender_key.py` is the priority entry for one reason the others do not have: it prints
**32 green result lines and then dies**. Everything downstream of "32 PASS" reads it as healthy —
a tail read, a grep for FAIL, a human skimming. It is the clearest example in the suite of output
that actively lies about the outcome.

## The 9 NOT_RUN

| file | lines | mechanism | verdict |
|---|---|---|---|
| `test_core_all_mids_dex_isolation.py` | 55 | `check()` helper, no summary | REPAIR (add summary) |
| `test_core_all_mids_dex_keys.py` | 68 | `check()` helper, no summary | REPAIR |
| `test_core_follower_mid_dex_keys.py` | 69 | `check()` helper, no summary | REPAIR |
| `test_core_snapshot_reads_every_dex.py` | 68 | `check()` helper, no summary | REPAIR |
| `test_core_summary_account_value_sign.py` | 46 | `check()` helper, no summary | REPAIR |
| `test_core_xyz_equity_not_double_source.py` | 44 | `check()` helper, no summary | REPAIR |
| `test_core_latency_trace_details.py` | 161 | bare `print("PASS: ...")`, no exit code | REPAIR (add FAIL path + exit code) |
| `test_core_outage_paging.py` | 58 | logic inside `main()`, no verdict printed | REPAIR |
| `test_outage_classify_deferred.py` | 21 | bare `assert` + PASS print | REPAIR (assertion failures currently masquerade as crashes) |

## TOP FIVE to repair rather than delete

1. `test_core_sender_key.py` — signer/account identity and the live-over-stream cap. Deleting it
   removes the only guard on which key signs which account, which is the class of error that
   sends a real order from the wrong identity. Also the loudest liar in the suite (32 greens then die).
2. `test_core_open_orders_cache.py` + `test_core_release_send_guards.py` (counted as one capability)
   — both crash on the SAME missing `_master_gate_reason`, so they are one repair, not two, and they
   guard the master gate: whether an order is allowed to leave at all.
3. `test_core_all_mids_dex_isolation.py` / `all_mids_dex_keys.py` / `follower_mid_dex_keys.py` — three
   files, one capability: DEX-namespaced mids. Multi-DEX pricing errors silently mis-price positions,
   and M3 already reported 87 DEXs in use, so this surface is live.
4. `test_core_rw12_retry_cloid.py` / `test_core_rw9_timeout_vs_429.py` — retry-after-timeout and
   rate-limit behaviour. They already have a known fix; dropping in the fixed copies from `3cff1fb`
   converts two crashes into 7/0 and 15/0 for near-zero effort.
5. `test_outage_classify_deferred.py` — smallest file in the set (21 lines) and currently
   indistinguishable from a crash. Cheap to fix, and outage classification gates whether the engine
   refuses to trade during a venue outage.

## DELETION LIST

**Empty, deliberately.** Nothing in this set fails on "no invariant" or "duplicate" grounds — every
one of the 15 exercises behaviour this project needs. A deletion list here would be produced by
mistaking a missing summary line for a missing test, which is exactly the error this triage exists to
prevent. Deletion candidates belong to the 18 assertion-failure files, which are a different question
(there, a test may genuinely encode a superseded rule) and have not been triaged yet.

## What I could not decide

Invariant IDs are not cited per file, because these files carry no `INVARIANT:` marker and I did not
map them to GUT I01-I26 / R01-R25 / CS-I1..I4 by inference. Mapping by guess would put a made-up
invariant ID into a governance document, which is worse than an honest gap. To close it: read each
file's assertions against the invariant list and cite the ID, or add the ID as a comment in the file
when it is repaired.

## Provenance

- Worktree `C:/Users/wigmore/tmp/p11_basered`, detached at `a1acc28`, 167 `test_*.py`.
- Runner `tools/gate/fullreg.py` @ ae56046, `--manifest NONE`, `-j 6`, 62s.
- Dispatched twice as a delegated task; both attempts produced an empty branch and no commit.
  This document replaces those attempts.
