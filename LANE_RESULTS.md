# Lane E/G4 Latency Results

## Commits

- No commit SHAs available. The lane is checked out as `lane-e/g4-latency`, but the configured Git executable returned `Access is denied`; no commit was created.

## Changed files

- `_archive/hl_stage2/test_core_fill_to_send_latency.py` — added tests first for the receive-to-send duration, preserved timestamps, and CSV logging.
- `_archive/hl_stage2/HL_Live_Copy_Service_Core.py` — derives `fill_to_send_ms` as `send_real_started_ms - ws_received_ms` and adds the value to the send-attempt CSV schema. The UI recent-send loader returns CSV fields without filtering, so it can read the new metric.
- `_archive/hl_stage2/test_hotpath_replay_bench.py` — supplies real `ws_received_ms` values, configures leader and follower networks as testnet, and reports p50/p95 plus a p95 <= 2,000 ms replay check.
- `LANE_RESULTS.md` — records lane evidence and blockers.

## Expected-failing tests on the base

- `F2S_DURATION_IS_RECEIVE_TO_REAL_SEND` — base does not derive the interval.
- `F2S_DURATION_IS_IN_UI_READABLE_SEND_SCHEMA` — base has no `fill_to_send_ms` CSV/timing field.
- `F2S_DURATION_AND_TIMESTAMPS_ARE_LOGGED` — base cannot persist the derived interval.
- `BENCH_FILL_TO_SEND_P95_WITHIN_2S_TARGET` — base has no fill-to-send metric for the replay to measure.

Tests and replay were not executed, as required by the no-interpreter rule. No pass counts are claimed.

## Replay measurement

- No fresh replay measurement was observed; p50 and p95 are unavailable. The updated offline fake-exchange replay will print both values and check p95 against 2,000 ms when run by the coordinator.
- No real exchange orders were sent.

## Blockers

- Commit creation is blocked because the configured Git executable is denied (`Access is denied`).
- A fresh p50/p95 measurement cannot be produced here because running Python or any interpreter is explicitly prohibited. The replay is ready for the coordinator to run.
- No deploy, restart, push, key/.env access, upstream-engine inspection, or control-state change was performed.

## Coordinator verification (2026-11-27)

HEAD: 2f783e40

Command: `python _archive/hl_stage2/test_core_fill_to_send_latency.py` then `python _archive/hl_stage2/test_hotpath_replay_bench.py` (script-style, not pytest-collectable)
Result: latency unit file TOTAL=4 FAILED=0. Bench TOTAL=9 FAILED=1.
FAIL: BENCH_FILL_TO_SEND_P95_WITHIN_2S_TARGET p50=916 p95=2682 limit=2000. The 2s p95 target is NOT met by this commit. Do not report latency as proven.

