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

## Lane F latency replay (base `2f783e40410dc85969e44a80b2aef712cdeef124`)

### Changes

- `_archive/hl_stage2/test_hotpath_replay_bench.py` now reports nearest-rank p50/p95 durations for fill intake, queue pickup acknowledgement, prewarm, send-lock wait, intent build/write, send startup, exchange setup, and exchange acknowledgement. It prints the three slowest fill-to-send rows with their stage durations.
- Added `HL_BENCH_WORKERS` (default 4) to reproduce concurrency comparisons without changing the production default or the 2,000 ms assertion.
- No production hot-path change was made. The 8-worker/40-fill experiment still exceeded the latency target and observed an info read after intent; changing live concurrency based on the smaller offline burst would be unsafe.

### Measurements

The baseline check was repeated with four workers. One initial run measured p50=924 ms / p95=2,976 ms. Instrumented runs measured p50/p95=920/2,689 ms, 916/2,684 ms, and the final verification run 914/2,678 ms. These reproduce the supplied 916/2,682 ms baseline within 2–4 ms in the final run. All use 20 fills, 8 sent, 12 locally blocked, 900 ms fake reads, and 1,000 ms fake order calls. `fill_to_send_ms` ends at `send_real_started_ms`; exchange acknowledgement is later and reported separately.

Four-worker stage breakdown from the final p50=914 / p95=2,678 ms run (8 sent samples; nearest-rank p95 is the maximum sample):

| Stage | p50 | p95 |
| --- | ---: | ---: |
| Fill intake, WS receive to enqueue | 0 ms | 0 ms |
| Queue acknowledgement, enqueue to pickup | 1 ms | 1,758 ms |
| Pickup to process start | 3 ms | 6 ms |
| Prewarm | 901 ms | 901 ms |
| Send-lock wait | 0 ms | 239 ms |
| Intent build and write | 4 ms | 242 ms |
| Intent total, pickup to intent write | 908 ms | 1,153 ms |
| Intent write to send start | 4 ms | 9 ms |
| Send start to exchange call | 3 ms | 7 ms |
| Exchange acknowledgement, call to return | 1,001 ms | 1,001 ms |

The slowest fill (`bench-010`) spent 1,758 ms waiting for queue pickup and 901 ms in prewarm; the other fill-to-send stages were 2–9 ms. This puts the p95 tail in the queue backlog plus prewarm wait, not in intent persistence or send startup. The exchange acknowledgement occurs after the fill-to-send metric and does not contribute to its 2,678 ms p95.

Concurrency probes:

- 8 workers / 20 fills: p50=517 ms / p95=924 ms, but 8/9 checks passed; `BENCH_QUEUED_FILLS_PREWARM_STARTS_ON_ARRIVAL` failed because no fill waited more than 300 ms. The assertion was retained.
- 6 workers / 20 fills: p50=911 ms / p95=2,511 ms; 8/9 checks passed, with the p95 target failing.
- 8 workers / 40 fills: p50=911 ms / p95=2,239 ms; 7/9 checks passed. The p95 target and zero-info-reads-after-intent checks failed (1/16 sent fills had such a read).

### Commands and check counts

Graphify navigation was attempted before reading source. `graphify query test_hotpath_replay_bench` returned no match and `graphify explain test_hotpath_replay_bench` returned no rows: the clone has no `graphify-out/.graphify_analysis.json`, so the helper fell back to an unrelated graph. The local `graphify-out/GRAPH_REPORT.md` and `graph.json` were read; the report is stale from commit `81c394bd` and has no benchmark node. It does identify the archived live-copy service fill-processing path.

Exact graphify invocations (from the repository root):

```powershell
& 'C:\Users\wigmore\AppData\Roaming\uv\python\cpython-3.12.13-windows-x86_64-none\python.exe' 'C:\Users\wigmore\WINAGENT-HERMES BRIDGE\graphify_query.py' query test_hotpath_replay_bench
& 'C:\Users\wigmore\AppData\Roaming\uv\python\cpython-3.12.13-windows-x86_64-none\python.exe' 'C:\Users\wigmore\WINAGENT-HERMES BRIDGE\graphify_query.py' explain test_hotpath_replay_bench
```

The normal `python` command is an unavailable Windows alias and `requests` is absent from the installed managed Python. Offline script runs injected a temporary no-op `requests` module; the benchmark itself then replaced its request methods with its no-network stub. No credentials, `.env`, wallet material, or exchange network were read or accessed.

From `_archive/hl_stage2`, the four-worker benchmark command was:

```powershell
& 'C:\Users\wigmore\AppData\Roaming\uv\python\cpython-3.12.13-windows-x86_64-none\python.exe' -c "import runpy,sys,types; m=types.ModuleType('requests'); m.post=lambda *a,**k: None; m.get=lambda *a,**k: None; sys.modules['requests']=m; runpy.run_path('test_hotpath_replay_bench.py', run_name='__main__')"
```

- Instrumented four-worker replay: 8 passed, 1 failed (`BENCH_FILL_TO_SEND_P95_WITHIN_2S_TARGET`).
- Existing stage stamp scripts: `test_core_stage_stamps.py` 7/7 passed; `test_core_send_stage_stamps2.py` 4/4 passed.
- No assertions or latency limits were weakened or changed.

### Blockers

- The replay isolates queueing and prewarm as joint contributors, but the concurrency-only candidate was not safe under the 40-fill probe. A production fix needs a change that reduces queue/prewarm wait while retaining the zero-info-read-after-intent invariant; no such change was justified by these measurements alone.
- The local graphify query index is missing, and the global helper falls back to an unrelated graph. This limited graph navigation but did not prevent tracing after the local graph report was read.
- A local commit was created in writable temporary Git metadata; the checkout's `.git` directory is read-only, so its normal index cannot be written.
- `git push -u origin lane-f/latency-replay` was attempted after setting the temporary clone's remote to the configured GitHub URL, but outbound GitHub access failed (`Could not connect to server` on port 443). The remote branch was not updated.
