# Lane D / G3 UI Truth Results

## Commits

- No new commit SHA was created. Base HEAD: `5e92b50e55e210b9bd853bf1277a2b1c853d6e60`.
- The test-first commit attempt failed because Git could not create `.git/index.lock` (`Permission denied`). Changes remain uncommitted on `lane-d/g3-ui-truth`; nothing was pushed.

## UI cells audited and changes

- **Trades and skips:** `_archive/hl_stage2/HL_Copy_App_SSOT.py:1310` now derives counters from final send rows and current-run intents, deduplicates repeated attempt/intent IDs, and scopes activity to `started_at_ms`. The status and audit chips use those counters at lines 7498 and 7758. Skip reasons are shown at lines 7499 and 7625. Source-decision chips at line 7779 now use current-run intent decisions.
- **Latency p50/p95:** no percentile cell was wired; the status strip only exposed the latest warning. The new current-run send-total percentile data is rendered at line 7500. Percentiles use nearest-rank over rows available in the existing 5,000-row send window.
- **Health:** `_load_live_ws_health` at line 1043 previously passed cached freshness through. It now marks an old health snapshot stale using its file age. `_build_health_summary` at line 1183 now reports unresolved active-red outcomes instead of leaving health green.
- **Per-leader counts:** `_build_live_wallet_rows` at lines 3139 and 3303 previously used recent/history-derived counts. Its activity fields now come from current-run counts; the wallet detail shows the leader's skip reasons at line 7625. Current-run leaders absent from config are also included in the rows.
- **Stuck positions:** these were already projected from `manual_live_positions.json` in `_build_live_wallet_rows` and rendered by `renderPositions` at line 7709. Activity counters are now separate from that durable position source, so a restart can zero activity without hiding positions. The regression case carries two open sleeves through the projection.

## Changed files

- `_archive/hl_stage2/HL_Copy_App_SSOT.py`
- `_archive/hl_stage2/test_live_copy_ui_run_truth.py`
- `LANE_RESULTS.md`

## Expected failures on the base

These new tests should fail on the base revision; they were not run here:

- `test_run_activity_counts_trades_skips_reasons_latency_and_each_leader` â€” the run-scoped activity builder and counters do not exist.
- `test_clean_restart_zeros_activity_without_hiding_persistent_positions` â€” historical activity is not scoped to the engine start.
- `test_live_copy_status_renders_run_activity_and_latency_cells` â€” the status strip has no run activity, skip reason, or p50/p95 cells.
- `test_stale_websocket_health_snapshot_is_not_reported_fresh` â€” stale snapshot age is not recomputed by the UI loader.
- `test_unresolved_active_red_outcome_is_not_reported_healthy` â€” active-red counts do not affect the health summary.

## Verification and blockers

- No Python, pytest, uv, or other interpreter was executed. No test pass count is claimed; the coordinator must run the suite.
- Read-only tracked-source `git diff --check` with `core.whitespace=cr-at-eol` reported no whitespace issues. This was a source diff check, not a test run.
- Activity inputs use the existing 5,000-row send and intent windows. Counts are labelled against the latest send-row window; a run longer than those windows can omit older activity.
- The `.git` directory is read-only in this environment, preventing the requested small commits. No source engine, runtime, deployment, restart, wallet, key, `.env`, `CONTROL_STATE.json`, or network order action was performed.

## Coordinator verification (2026-11-27)

HEAD: 2e3c748c

Command: `python -m pytest -q -p no:cacheprovider _archive/hl_stage2/test_live_copy_ui_run_truth.py`
Result: 5 passed.


## Lane g3/ui-truth-tests checkout verification (2026-11-27)

- Branch: `lane-g3/ui-truth-tests`; HEAD before this log update: `f42144e17a5a24daa516d20f3e6ef00212589609`.
- The requested implementation and regression tests are already present in ancestor commit `2e3c748c` (`fix(ui): live copy run-truth counters, skip reasons, latency, health`). Review found no further source defect. No upstream service/scout files were changed.
- Prior recorded verification: `python -m pytest -q -p no:cacheprovider _archive/hl_stage2/test_live_copy_ui_run_truth.py` - 5 passed (coordinator record dated 2026-11-27).
- This checkout attempt: `python -m pytest -q -p no:cacheprovider _archive/hl_stage2/test_live_copy_ui_run_truth.py` - process failed before collection because `python.exe` launch was denied; no test result or pass/fail counts were emitted.
- Interpreter fallback: `py 'C:/Users/wigmore/WINAGENT-HERMES BRIDGE/graphify_query.py' --help` - blocked: `No installed Python found!`; `graphify query --help` and `graphify explain --help` also failed because the graphify launcher could not invoke Python. The checked-in graph report was read first and identifies the UI model, health builder, and live-copy service as relevant areas.
- Root causes already fixed in `2e3c748c`: UI activity counters were not scoped to `started_at_ms`; skips/reasons and send latency percentiles were absent from the UI; stale websocket health could remain fresh; unresolved active-red outcomes could appear healthy; persistent positions needed to remain visible after restart while run counters reset.
- Blocker: no runnable Python interpreter in this environment, preventing fresh test execution.

## Clean-restart health regression test (2026-11-27)

- Added `test_clean_restart_ui_reads_zeroed_activity_and_health` to `_archive/hl_stage2/test_live_copy_ui_run_truth.py`. It feeds prior-run trade and close-failure rows alongside a fresh engine start and zero active-red integrity state through the real activity and UI status builders; it asserts zero trades/skips/latency and a Healthy UI health payload.
- Before edit: `python -m pytest -q -p no:cacheprovider _archive/hl_stage2/test_live_copy_ui_run_truth.py` — 0 collected; command stopped before collection with `No module named pytest`. Historical coordinator run above reports 5 passed before this test was added.
- After edit: same command — 0 collected; same missing-`pytest` failure. `uv --cache-dir .uv-cache run --offline --with pytest python -m pytest -q -p no:cacheprovider _archive/hl_stage2/test_live_copy_ui_run_truth.py` also failed before collection because pytest is not cached and network access is disabled.
- Syntax check: `python -m py_compile _archive/hl_stage2/test_live_copy_ui_run_truth.py` — passed. Assertion pass/fail count after edit is unavailable because pytest could not start.
- Root cause covered: the previous clean-restart regression checked run counters and durable positions, but did not assert zeroed run activity together with the health object delivered by the UI status builder; stale close failures must not make the new run unhealthy.
- Blocker: pytest is absent from the available Python runtime and unavailable in the offline uv cache. No production files or protected services were changed.
