# TEST TRIAGE FACTS — mechanical per-file evidence at a1acc28

CC-1 R35 item 2. These are FACTS, not verdicts: the KEEP / MERGE / DELETE decisions are the
controller's to hand to a writer. Machine-readable copy: `TEST_TRIAGE_FACTS.csv`.

| file | class | dialect | lines | check() helper | bare PASS print | invariant marker | exit | crash cause |
|---|---|---|---|---|---|---|---|---|
| `test_core_all_mids_dex_isolation.py` | NOT_RUN | silent | 55 | yes | no | no | 0 |  |
| `test_core_all_mids_dex_keys.py` | NOT_RUN | silent | 68 | yes | no | no | 0 |  |
| `test_core_follower_mid_dex_keys.py` | NOT_RUN | silent | 69 | yes | no | no | 0 |  |
| `test_core_latency_trace_details.py` | NOT_RUN | silent | 161 | no | yes | no | 0 |  |
| `test_core_open_orders_cache.py` | CRASH | RESULT::+die | 188 | yes | no | no | 1 | AttributeError: 'types.SimpleNamespace' object has no attribute '_master_gate_reason' |
| `test_core_outage_paging.py` | NOT_RUN | silent | 58 | no | no | no | 0 |  |
| `test_core_queue_timing_stamps.py` | CRASH | exitcode | 215 | no | yes | no | 1 | PermissionError: [WinError 32] The process cannot access the file because it is being used by anothe |
| `test_core_release_send_guards.py` | CRASH | exitcode | 96 | yes | no | no | 1 | AttributeError: 'types.SimpleNamespace' object has no attribute '_master_gate_reason' |
| `test_core_rw12_retry_cloid.py` | CRASH | exitcode | 208 | yes | no | no | 1 | RecursionError: maximum recursion depth exceeded while calling a Python object |
| `test_core_rw9_timeout_vs_429.py` | CRASH | exitcode | 219 | yes | no | no | 1 | RecursionError: maximum recursion depth exceeded while calling a Python object |
| `test_core_sender_key.py` | CRASH | RESULT::+die | 362 | yes | no | no | 1 | AttributeError: 'StartupConfig' object has no attribute 'live_over_stream_cap' |
| `test_core_snapshot_reads_every_dex.py` | NOT_RUN | silent | 68 | yes | no | no | 0 |  |
| `test_core_summary_account_value_sign.py` | NOT_RUN | silent | 46 | yes | no | no | 0 |  |
| `test_core_xyz_equity_not_double_source.py` | NOT_RUN | silent | 44 | yes | no | no | 0 |  |
| `test_outage_classify_deferred.py` | NOT_RUN | silent | 21 | no | yes | no | 0 |  |

## How to read this

- `check() helper = yes` together with `bare PASS print = no` and class NOT_RUN is the signature of
  HARNESS_CONVENTION: the file prints a line per case and never a summary or an exit code.
- `class = CRASH` rows carry the literal last stderr line; those are the harness defects.
- `invariant marker = no` on every row: none of these 15 files names an invariant, so no invariant ID
  is cited here. Mapping them is a reading task, not a grep, and inventing IDs would put fiction into
  a governance document.

## Provenance

- worktree `C:/Users/wigmore/tmp/p11_basered` detached at `a1acc28`, 167 `test_*.py`
- runner `tools/gate/fullreg.py` @ ae56046 + `--label`, `--manifest NONE`, `-j 6`
