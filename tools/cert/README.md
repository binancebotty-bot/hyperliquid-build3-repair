# tools/cert — offline halves of the J4 certification gaps (task K2)

These scripts turn the J4 run-script specs (`process/PC_RUN_SCRIPTS_2026-10-11.md`
@ `60017c1` and `process/PC_RUN_SPECS_2026-10-11.md` @ `681b62f`, branch
`hermes/j4-matrix`) into **real, runnable, testable** checks for every part of the
five gaps that needs **no live engine**: classifiers over copies of the audit CSVs,
the memory read-cost measurement, the liquidation-parity arithmetic, and the
audit-append failure path.

Every script is one command, prints a single verdict line as its LAST stdout line,
and exits non-zero on FAIL:

```
<TAG>:: PASS <detail>          exit 0
<TAG>:: FAIL <detail>          exit 1
<TAG>:: INCONCLUSIVE <why>     exit 3
```

`<TAG>` is the tag the J4 spec names for that gap (`GAP1_RESULT`, `GAP2_RESULT`, …),
so a PC batch can grep the output exactly as the spec's verdict blocks do.

## Safety (all scripts)

Offline. Read-only inputs. Nothing here touches the running engine, the live
checkout `hl-build3-testnet-cert` (except reading copies of its audit CSVs),
ports 8012/8014/8031, the Wallet Finder, keys, `.env`, or the exchange. No orders,
no WebSocket subscriptions, no console window is spawned (subprocesses use
`CREATE_NO_WINDOW`).

## Scripts

| script | gap | what it proves offline | one command |
|---|---|---|---|
| `cert_outage_classify.py` | 1 outage recovery | every leader fill in an outage window ends in exactly one engine row and no leader order was sent twice (the run5 classifier, on FILES) | `python cert_outage_classify.py --audit-dir <copy> --leader-fills fills.json --stop-ms N --restart-ms N --blocked-coins SOL` |
| `cert_memory_scan.py` | 2 memory flat | the audit-CSV read cost: bounded tail read vs whole-file read, using the engine's OWN readers (`read_csv_rows` / `read_csv_tail_rows`) | `python cert_memory_scan.py --audit-dir <copy> --core-dir <checkout>/_archive/hl_stage2` |
| `cert_liq_parity_offline.py` | 3 liquidation parity | for every open follower position, `follower_dist >= safest_leader_dist` on the **exchange-reported** `liquidationPx`; plus the `liquidation_px_by_coin` wiring finding | `python cert_liq_parity_offline.py --audit-dir <copy>` |
| `cert_disk_guard.py` | 5 disk-full | an audit append that cannot be written **raises loudly**, is recorded in `errors.csv`, writes nothing partial, and recovers after the ACL is restored — through the engine's own `append_csv` / `log_error` | `python cert_disk_guard.py --audit-dir <copy> --core-dir <checkout>/_archive/hl_stage2` |
| `export_leader_fills.py` | 1 (input) | the ONE network step: read-only `userFillsByTime` export of a window's leader fills to JSON, so the classifier runs offline afterwards | `python export_leader_fills.py --config <copy of live_config.json> --start-ms N --end-ms N --out fills.json` |

Run the whole set's tests (fixtures + gates, 18 checks; the exporter is tested for its
wallet selection and JSON shape — its HTTP call is the operator's read-only step):

```
env -u PYTHONPATH <PY311> -u tools/cert/tests/test_cert_scripts.py     # -> TOTAL=18 FAILED=0
```

Scrub `PYTHON*` for every offline run: under an inherited `PYTHONPATH` the repo's
`tools/` package shadows the release namespace (F2 two-run control) and 13 of 43
repo tests abort — an instrument failure, not a product failure.

## Which J4 gaps still need the live engine

| gap | offline coverage (this dir) | still needs the live engine |
|---|---|---|
| 1 outage recovery | classifier + replay counters (missed / duplicates / replay lag) over captured fills and audit copies | the outage itself: a real stop/armed-restart, and the leader burst that produces the fills |
| 2 memory flat | read-cost + gate on copies, incl. the unfixed whole-file driver | 60–120 min of live RSS at the real file sizes a busy day produces (the headline number) |
| 3 liquidation parity | parity arithmetic + wiring check on captured `clearinghouseState` snapshots | an open follower position and the per-dex/leader exchange reads |
| 4 realistic-load latency (Phase R) | **nothing by design** — the gap IS the missing live measurement | the whole gap: armed run with the E1 3-leader cohort, `lat_stamps.py` p50s, RSS sampler |
| 5 disk-full | deny-ACE append-failure invariant on a copy, through the engine's own append path | the real ENOSPC run on a bounded VHD (elevated) — the J4 spec forbids filling C: |

So the live-engine work left for the PC operator is: GAP-4 end to end, the live
halves of GAP-1/2/3, and GAP-5 part B (bounded VHD, elevated).

## Input layouts

`cert_outage_classify.py --audit-dir` and `cert_memory_scan.py --audit-dir` accept
either the engine state dir (`<dir>/append_only/*.csv`) or the `append_only` dir
itself. Rotated copies (`reconciliation.20261010.1.csv`) are picked up too.

`cert_liq_parity_offline.py --audit-dir` needs five files side by side:
`mids.json`, `leader_states.json`, `follower_states.json`,
`exchange_account_snapshot.json`, `reconciliation.csv` — see
`tests/fixtures/liq_ok/` for the exact schemas (copies of the exchange payloads).

`cert_disk_guard.py` copies `<audit-dir>` into a scratch dir before it touches
anything; never point it at the live checkout.

## Evidence from building this (2026-10-11, offline, on this host)

* 18/18 tests pass (`tools/cert/tests/test_cert_scripts.py`).
* GAP-5, through the engine's own `append_csv`: baseline append ok → `icacls /deny USER:(WD,AD)`
  → `PermissionError(13)` raised → `log_error` row landed in `errors.csv` → ACL restored →
  clean append, exact row counts. (The Core's sender already returns
  `SEND_NOT_ATTEMPTED_AUDIT_WRITE_FAILED` when that write raises, `HL_Live_Copy_Service_Core.py`
  L5480-5488, so the "no order without a record" invariant is guarded at the source.)
* GAP-2 on a **20.2 MB copy built from the real** `reconciliation.csv` (2,000 real rows
  repeated; 44,000 rows): whole-file `read_csv_rows` retained **169 MB** (~8× the file) and
  moved RSS by ~70 MB, while the bounded tail retained ~9× its slice
  (2 MiB → 18.9 MB, 1 MiB → 9.5 MB, 512 KiB → 4.8 MB). Scaling the whole-file figure to the
  real 235 MB rotated file is ~2 GB — the same order as the M1 profile (3.25 GB at 200 MB).
  The whole-file reader is the remaining GAP-2 driver; the offline gate therefore FAILs until
  that call site moves to the tail/streaming reader. At the default 2 MiB slice pass
  `--tail-bytes 1048576` to keep the tail inside the 10 MB gate.
* GAP-3: the wiring finding reproduces offline — `exchange_account_snapshot.json` carries only
  `created_at, created_at_ms, raw, positions_by_coin`, so `exchange_reported_liquidation_px_used=False`
  and the gate falls through to the internal projection.

## Model split

`cert_liq_parity_offline.py` was written by a free local worker
(`deepseek-v4-flash-nosearch` via the FreeDeepseek proxy on 127.0.0.1:9655, probed with a
tiny prompt first) from a fixed spec; it was reviewed here (an unused `math` import and
per-position lines leaking into `--json` were fixed) and is covered by 5 tests. Everything
else was written in-session by `deepseek-flash`. The retired `local_offload_router.py` still
reports `blocked: no preferred local Ollama model is installed or reachable`.
