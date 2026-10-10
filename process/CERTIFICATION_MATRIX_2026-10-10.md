# Build 3 Repair — Certification Matrix (Boss invariants / controls)

**Task:** round F, task F2 (spec: `HERMES_ROUND_F.md` §F2).
**Repo / commit under test:** `binancebotty-bot/hyperliquid-build3-repair`, fresh clone of `main` @
`626efd10009d189175ddaad875c12dcf98109621` (the "626efd1 or later" requested; **PR #41**, cross-margin 3x +
liquidation-parity gate).
**Produced by:** hermes:implementation-owner, offline, 2026-10-10. Model per part: **deepseek (Hermes
session, `deepseek-flash`)** — see *Models used* at the end.
**Scope:** certify the Boss invariants/controls listed in the F2 spec against (a) the repo's own offline
mock tests and (b) the issued testnet-run history. Everything offline: no engine start, no orders, no
WebSocket, no keys, the running cert dir / ports 8012/8014/8031 / Wallet Finder untouched.

**Columns:** invariant **|** test file + check ids **|** mock-proven (Y/N) **|** testnet-proven
(Y/N, evidence path) **|** gap.

A "mock-proven Y" means the named offline test exercises the invariant and **passes on 626efd1** (see how
the suite was run). A "testnet-proven Y" means an issued testnet run observed the invariant against the
real exchange **and** the evidence file records it; where a run *disproved* the invariant the cell says so.
The current `main` (626efd1) has **never been run on testnet**: every testnet result below is from an
earlier commit (run1 `9eb2d40`, run3a/3b `ab7f2b0`, run4 `3c03099`, run5 `e51e047…cff92fa`). That is the
dominant, honest gap across the board.

---

## Matrix

| # | Invariant / control | Test file + check ids (626efd1) | mock-proven | testnet-proven (evidence path) | Gap |
|---|---|---|---|---|---|
| 1 | **Copy every market** — every leader market is copied across all perp DEXes incl. HIP-3 | `test_core_dex_scope_and_ui_truth.py`: `S2_LEADER_TRADE_ADDS_ITS_MARKET`, `S5_NEW_LEADER_MARKET_RESOLVES_ON_FIRST_TRADE`, `S6_SWEEP_READS_EVERY_DEX_OUTSIDE_SCOPE`, `S6_SWEEP_OF_268_DEXES_IS_FAST_OFFLINE`, `S8_UI_SHOWS_MARKETS_TRADED`. `test_g3_exchange_truth.py`: `G3_MULTIDEX_HIP3_AGGREGATE`. `test_core_network_and_global_controls.py`: `R3_HIP3_MIDS_FETCHED_PER_DEX`, `G1_TOTAL_CAP_COUNTS_EVERY_DEX_FROM_EXCHANGE` | **Y** | **N** — run1 **FAIL** ENG-006 (per-DEX sequential reads, ~0.52 s × 268; a `--once` cycle did not finish in 120 s). Evidence: `hl-build3-testnet-cert-evidence/RUN1_FINDINGS.md` §BLOCKER B1; `certification/run_results.json` (run1 ENG-006 FAIL) | DEX-scope/concurrent-sweep fix is **mock-only**; "every market" never exercised live on 626efd1. 268-DEX sweep unproven. |
| 2 | **Fresh follower mid ≤ 5 s** (OD-01) — ENT/INCREASE/FLIP priced from a follower mid ≤ 5 s old; no fresh mid ⇒ no order | `test_core_network_and_global_controls.py`: `F1_SAME_NETWORK_ENTRY_PRICED_FROM_FRESH_MID_NOT_LEADER_PRICE`, `F2_SAME_NETWORK_ENTRY_WITHOUT_FRESH_MID_NOT_SENT`, `F3_STALE_MID_BLOCKS_ENTRY_DECISION`, `R3_STALE_MIDS_COUNT_AS_NONE`, `R1_NO_FOLLOWER_PRICE_NO_ENTRY`. `test_core_dex_scope_and_ui_truth.py`: `S3_TEN_DEX_REFRESH_INSIDE_TTL`, `S3_SEQUENTIAL_READS_WOULD_MISS_BUDGET` | **Y** | **N** — run1 **FAIL** PRICE-001 (allMids refresh across all DEXes ~140 s, so every mid > 5 s and every entry unpriceable). Evidence: `RUN1_FINDINGS.md` B1; `run_results.json` (run1 PRICE-001 FAIL) | Rule never PASSED on any run; the DEX-scope fix that makes mids fresh is mock-only (`S3_*` are the mock of the measured testnet defect). |
| 3 | **Slippage 0.2 %** default (unset marketable slippage) | `test_core_network_and_global_controls.py`: `G10_MISSING_SLIPPAGE_IS_BOSS_DEFAULT_02PCT`, `G10_EXPLICIT_ZERO_SLIPPAGE_STAYS_ZERO`, `R1_SLIPPAGE_COUNTS_TOWARD_ORDER_VALUE`. `test_live_screen_truth.py`: `L1_DEFAULT_SLIPPAGE_IS_0_2_PCT`. `test_core_missed_entry_rule.py`: `M1_WITHIN_TOLERANCE_TAKEN_CAPPED_AT_LEADER_PLUS_TOL` | **Y** | **N (NEEDS_MAINNET)** — slippage/price quality is not judgeable on testnet (illiquid). `run4/RUN4_FINDINGS.md` line 6: "not meaningful on testnet — to be proven on mainnet". Contract marks it `proof_network = MAINNET` | PASS only from a **mainnet-follower** run; none has been done. The 0.2 % default is proven only as a config value, never as realised slippage. |
| 4 | **WS + poll catch-up** — WS primary, poll backstop catches missed trades of any age; re-subscribe on reconnect | `test_core_poll_fallback.py` (11): `feed_ok_30s`, `open_but_unacked_is_fast`, `socket_down_is_fast`, `wallets_without_feed_counted`. `test_core_r0_ws_resubscribe.py` (5): `R0_SUBSCRIBE_ALL_ENABLED_ON_OPEN`, `R0_RESUBSCRIBE_AFTER_RECONNECT_INCLUDES_NEW_WALLET`, `R0_STATUS_NOT_OK_WHEN_SILENT_OPEN_SOCKET`, `R0_STATUS_OK_AFTER_SUBSCRIPTION_ACK`. `test_core_run3_fixes.py`: `K6_LIVE_FEED_UP_POLL_IS_A_30_S_BACKSTOP`, `K6_LIVE_FEED_DOWN_POLL_EVERY_CYCLE` | **Y** | **N** — no testnet run exercised WS outage/resubscribe (R0 fix, PR #32) or poll-fallback on 626efd1. Evidence: `RUN_STATUS.md`/`run_results.json` have no WS-feed row | R0 re-subscribe + poll-fallback are **mock-only**; a silent-open-socket while trading has never been forced live. |
| 5 | **Missed-trade replay, in / out of tolerance** | `test_core_missed_entry_rule.py` (89): `M1_SAME_PRICE_TAKEN`, `M1_BEYOND_TOLERANCE_RESTS`, `M2_BEYOND_TOLERANCE_NO_CHASE_ONE_LIMIT_AT_LEADER_PRICE`, `M7_THREE_DAY_GAP_CAUGHT_UP_FROM_LAST_GOOD_POLL`, `M7_GAP_BEYOND_7_DAYS_REPORTED`, `M7_PAGES_RAN_OUT_SAYS_PARTIAL`, `R7_*`. `test_core_r1_cursor.py` (7): `crash_replay_rereads_all_unprocessed` | **Y** | **N** — run4 exposed the opposite: missed-entry GTC limits **flooded** the book (3,885 of 5,476 sends; 160–186 open) and bypassed caps. Evidence: `run4/RUN4_FINDINGS.md` R3 | The in/out-of-tolerance rule has never PASSED live. R1 gap-rebuild (PR #30/#32) is mock-only; no testnet run since. |
| 6 | **Idempotent replay** — restart/replay never double-sends or double-books | `test_core_r1_cursor.py`: `queued_fill_holds_cursor`, `crash_replay_rereads_all_unprocessed`. `test_g4_intake_sleeves.py`: `A_DUPLICATE_INTAKE_MINTS_ONCE`, `A_RESTART_AND_REPLAY_MINT_NOTHING`. `test_core_run4_fixes.py`: `Q2_MERGED_FILLS_STAY_HANDLED_AFTER_A_RESTART`. `test_t1a_cloid_pending_row.py`: `A3_ATTEMPT_ID_DETERMINISTIC`, `A5_UPDATE_IS_APPEND_ONLY`, `A11_CRASH_LEAVES_ONE_PENDING_ROW_WITH_CLOID` | **Y** | **Partial / Y on old commit** — run3b **PASS** ORD-005 "Exactly-once execution identity": no duplicate sends, 2,908 duplicate leader fills blocked pre-send. Evidence: `RUN_STATUS.md` ORD-005 PASS; `run3/RUN3_FINDINGS.md` | ORD-005 PASS is on `ab7f2b0` only, never re-run on 626efd1. No live replay-across-restart test on current main. |
| 7 | **Switch OFF / CLOSE / ON** (three-state) | `test_core_switch_states.py` (11): `S0_THREE_STATE_SWITCH_RECOGNISED`, `S2_SEND_MODE_OFF_SENDS_NOTHING`, `S3_SEND_MODE_OFF_STOPS_CONVERGENCE_CLOSE`, `S4_CLOSE_BLOCKS_ENTRY`, `S6_CLOSE_SENDS_REDUCTIONS_ONLY`, `S8_SEND_MODE_ON_SENDS_ALL`, `S9_RESTING_ENTRY_LIMITS_WITHDRAWN_ON_CLOSE`. `test_core_run4_fixes.py`: `D1_ARMED_SWITCH_READS_ON`, `D2_QUEUED_ORDER_AFTER_SWITCH_OFF_IS_NOT_SENT`. `test_core_run5_converge.py`: `C1_SENDING_OFF_NEVER_CLOSES` | **Y** | **Partial (FAIL on old commit)** — run4 R5: "Disarm is **not** immediate", 33 already-queued orders sent 22:13:21–22:13:55; resting entry limits stayed after disarm. Evidence: `run4/RUN4_FINDINGS.md` R5 | The three-state switch (PR #40) has **never** been exercised on testnet; disarm latency unresolved; switching OFF mid-burst was only added (not live-tested). |
| 8 | **Liquidation parity + cross 3×** (follower liq never worse than safest leader) | `test_core_liq_parity.py` (10): `L1_UPDATE_LEVERAGE_CROSS_ONCE_BEFORE_FIRST_ORDER`, `L1B_UPDATE_LEVERAGE_NOT_REPEATED_PER_ORDER`, `L2_FOLLOWER_LEVERAGE_CONTROL_DEFAULT_3_CONFIGURABLE`, `L5_LIQUIDATION_PROJECTION_PRESENT`, `L6_PARITY_BLOCKS_WORSE_THAN_SAFEST_LEADER`, `L7_PARITY_ALLOWS_SAME_OR_BETTER`, `L8_UNKNOWN_PROJECTION_FAILS_CLOSED`, `L9_CLOSES_NEVER_BLOCKED_BY_PARITY`. `test_core_liq_projection.py` (6). `test_core_liquidation.py` (9). `test_core_adl.py` (11) | **Y** | **N** — never run on testnet. Evidence: none (`run_results.json` has no liq-parity row) | **This is the head commit's own feature (PR #41)** and is proven only by mocks. Cross-margin + projected-liq gate has never touched a live account. |
| 9 | **Dust** — sub-$10 order only if it closes the WHOLE account position; else a diff | `test_core_run5_converge.py`: `D1_WHOLE_POSITION_DUST_CLOSE_REACHES_THE_EXCHANGE`, `D1_DUST_ENTRY_STILL_BLOCKED`, `D2_SWITCH_RESTORES_THE_OLD_BLOCK`, `D3_NON_REDUCE_ONLY_CLOSE_KEEPS_THE_MINIMUM`, `D4_SLIVER_OF_A_LARGER_ACCOUNT_POSITION_STAYS_BLOCKED` | **Y (partial)** | **Y (as a live defect)** — run5 L3 "Dust persists (4–10 positions under $10) at each sample"; run4 R4 "positions don't fully close / dust". Evidence: `run5/RUN5_FINDINGS.md` L3; `run4/RUN4_FINDINGS.md` R4 | The **F1** deliverable (`test_core_dust_rules.py`, whole-position-vs-sleeve rule) does **not exist** in this branch — the dust invariant is only partially mocked. Testnet still leaves dust. |
| 10 | **Orphan orders** — unmatched resting orders cancelled, matched adopted, fail-closed | `test_t1b_startup_orphan.py` (10): `B1_MATCHED_ADOPTED`, `B5_UNMATCHED_CANCELLED`, `B9_READ_FAILURE_FAILS_CLOSED`, `B10_MAINNET_UNCONFIRMED_SKIPPED`. `test_t1c_stop_cancel.py` (10): `C2_STOP_CANCELLED_BOTH_ON_THE_EXCHANGE`, `C4_FAILED_CANCEL_STILL_RESTING_WITH_CLOID`, `C9_STOP_NEVER_RAISES`. `test_core_adopt_oid.py` (18): `N1_ADOPTION_HAS_NO_EXCHANGE_WRITE`, `F5_ADOPTION_REFUSES_WITHOUT_THE_FLAG` | **Y** | **N** — PR #38 (T1) is mock-only; no testnet run. Evidence: `run_results.json`/`RUN_STATUS.md` — no row | Startup orphan adoption and stop-time cancel have never run against a live account; live orphan risk unproven. |
| 11 | **Audit rotation** — append-only logs rotate at a size limit, newest kept, no middle loss | `test_core_memory_bounds.py` (16): `ROTATED_AT_LIMIT`, `ONLY_KEEP_NEWEST_ROTATED`, `HISTORY_SPANS_ROTATED_FILES_IN_ORDER`, `OLDEST_PRUNED_NOT_LOST_MIDDLE`, `FRESH_FILE_HAS_HEADER_AFTER_ROTATE`, `TAIL_ROWS_WHOLE_AND_RECENT`, `SEND_ATTEMPTS_NOT_ROTATED` | **Y** | **N** — never exercised on testnet (PR #39 memory fix is mock-only). Evidence: none | Rotation under a real long run (multi-MB, hours) unproven; `send_attempts` deliberately not rotated — re-check under load. |
| 12 | **No mainnet orders** — a follower on testnet can never place a mainnet order | `test_core_run3_fixes.py`: `G1_MAINNET_FOLLOWER_REFUSED_WITHOUT_THE_FLAG`, `G1_NO_ENV_FILE_CAN_CONFIRM_MAINNET`, `G1_ORDER_CALL_ITSELF_REFUSES_UNCONFIRMED_MAINNET`. `test_core_network_and_global_controls.py`: `N1_DEFAULT_LEADER_MAINNET_FOLLOWER_TESTNET`, `N2_UNKNOWN_NETWORK_REFUSED`, `N3_LEGACY_URLS_ON_OTHER_NETWORK_REFUSED`, `N4_STATE_FOLDER_BOUND_TO_ONE_NETWORK_PAIR` | **Y** | **Y (on old commit)** — run3b **PASS** NET-004 "LIVE/mainnet activation gate": mainnet untouched, the 6 Build 4 leftover orders unchanged. run3a also held separation (mainnet signer refused on testnet). Evidence: `RUN_STATUS.md` NET-004 PASS; run3a/run3b in `run_results.json`; `run3/RUN3_FINDINGS.md` | PASS is on `ab7f2b0`. The order-call-level mainnet guard and the network-pair state-folder stamp have **not** been re-run on 626efd1. |
| 13 | **Mainnet leftovers untouched** — pre-existing orders/positions never touched (ENG-016) | `test_core_adopt_oid.py`: `P2_BTC_UNTOUCHED`, `F7_REFUSED_OIDS_UNTOUCHED`. `test_core_ledger_repair.py`: `F4_REFUSED_COINS_UNTOUCHED`, `T4_TIA_FLAT_AND_KAS_UNTOUCHED`, `T5_REFUSED_COIN_CREATES_NO_EMPTY_SLEEVE`. `test_core_liquidation.py`: `L6_COUNTERPARTY_OF_A_LIQUIDATION_IS_NOT_OURS`. `test_core_run3_fixes.py`: `G3_CLOSE_BLOCKED_WHEN_EXCHANGE_HOLDS_MORE` | **Y** | **Y (on old commit)** — run3b NET-004: "the 6 Build 4 leftover mainnet orders unchanged". Evidence: `RUN_STATUS.md` NET-004; `RUN1_FINDINGS.md` (7 leftover positions + 6 reduce-only orders recorded unchanged) | Same as row 12: proven on `ab7f2b0`, not on 626efd1. run5 shows inherited positions from an earlier lineage are carried (external/unowned) and left untouched — consistent, but on the run5 commit. |
| 14 | **Past-incident regressions** (run 1/3/4/5 incidents stay fixed) | `test_core_run3_fixes.py` (61), `test_core_run4_fixes.py` (54), `test_core_run5_converge.py` (23), `test_core_fill_lag.py` (15), `test_core_ledger_repair.py` (31), `test_core_adl.py` (11), `test_core_liquidation.py` (9), `test_core_engine_gaps.py` (23), `test_core_sender_key.py` (31), `test_core_dispatch_guards.py` (5), `test_screen_run4.py` (86) | **Y** (all pass on 626efd1) | **Mixed / FAIL on old commits** — recorded FAILs, since fixed on branches but not re-run: ENG-018 (netting), ENG-019 (loop keeps up), ORD-009 (signer network), ORD-010 (leader→send delay), SET-009 (ledger = exchange), PRICE-001, UI-TRUTH-001. Evidence: `RUN_STATUS.md` rows; `RUN1/run3/run4/run5 _FINDINGS.md` | Each incident's **fix** is mock-proven only. Confirming the whole regression set is closed needs one fresh testnet run on a single commit. |

---

## Test-suite health (how "mock-proven" was established)

Run from `_archive/hl_stage2`, per the spec:
`HL_LIVE_ENV_FILE=/nonexistent python -u <test>.py` (PY311), capturing `RESULT::` / `TOTAL=` lines.
**43 test files, ~1,000 checks; all pass on 626efd1 with two exceptions recorded below.**

**Two-run control (instrument, not product).** Under the agent's inherited environment, **13 of 43** tests
abort before their first check with
`ModuleNotFoundError: No module named 'pydantic_core._pydantic_core'` — a broken `pydantic_core` is being
imported from a Hermes venv on `PYTHONPATH`, shadowing the interpreter's own package. Re-run with a
**scrubbed env** (drop all `PYTHON*` vars) **all 13 pass, 0 failures**:

| env | 13 shadowed tests | result |
|---|---|---|
| inherited (`PYTHONPATH` set) | `test_core_dex_scope_and_ui_truth`, `test_core_engine_gaps`, `test_core_network_and_global_controls`, `test_core_sender_key`, `test_core_switch_states`, `test_g4_order_cap`, `test_g4_ui_controls`, `test_live_screen_truth`, `test_screen_run4`, `test_ui_audit_summary_size`, `test_ui_incremental_edges`, `test_ui_incremental_summary`, `test_ui_send_attempts_dedupe` | all abort, 0 checks |
| scrubbed (`env -u PYTHONPATH -u PYTHONHOME …`) | same 13 | **all PASS** (e.g. `test_core_network_and_global_controls` 62/62, `test_screen_run4` 86/86) |

⇒ Instrument finding; **do not** count those aborts as product failures. Any cert runner must scrub
`PYTHON*` (or use a clean interpreter) before running the suite.

**One genuine test failure (`test_hotpath_replay_bench.py`, FAILED=3/7, identical under both envs):**

```
MEASURE:: burst=20 fills, workers=4, read=900 ms, order=1000 ms, scale=1.00
MEASURE:: sent=0 (reached the exchange), blocked locally=20
MEASURE:: queue wait p90 = 565 ms (limit 500)      → BENCH_QUEUE_WAIT_P90_WITHIN_LIMIT PASS (non-strict 5000)
MEASURE:: fill-to-ack p90 = 725 ms (limit 2000)    → BENCH_FILL_TO_ACK_P90_WITHIN_LIMIT PASS
RESULT::BENCH_40PCT_REACHED_THE_EXCHANGE_FAIL | sent=0 expected=8
RESULT::BENCH_60PCT_BLOCKED_LOCALLY_FAIL | blocked=20 expected=12
RESULT::BENCH_STAGE_STAMPS_PRESENT_AND_ORDERED_FAIL | rows=0 bad=[]
```

All 20 replay fills write an order-intent row but **none reaches the fake exchange**; no `send_attempts`
rows are written. `BENCH_ZERO_INFO_READS_BETWEEN_INTENT_AND_ORDER` passes **vacuously** (0 sent fills).
This bench was merged by PR #26 as an "expected-to-fail" reproduction of the pre-PR-2 hot path; its two
latency checks are intentionally non-gating, but the 40/60 split and stage-stamp checks are structural and
**should** pass. They do not on 626efd1 ⇒ either the harness seams drifted after the dynamic-lane /
throughput PRs (#26–#34) or a send-path regression blocks all sendable fills. **Not root-caused here
(out of F2 scope); recorded as a finding and a top gap.** Command to reproduce:

```
cd _archive/hl_stage2
env -u PYTHONPATH HL_LIVE_ENV_FILE=/nonexistent <py311> -u test_hotpath_replay_bench.py
```

---

## Top 5 gaps ranked by risk

1. **No commit has ever been run on testnet since the run-4/run-5 fixes** (rows 1–14). Every testnet PASS
   is staler than the code it certifies; the head (626efd1) is **mock-only everywhere**. Highest risk
   because the whole point of certification is a live run per applicable control. *Mitigation:* one fresh
   testnet run on 626efd1, recording each control against the exchange.

2. **Liquidation parity + cross-3× (row 8) — the head commit's own feature, never live.** A wrong
   projected-liquidation gate fails in the direction that liquidates the account; it is proven only by
   mocks and only exists at 626efd1. *Mitigation:* run it on testnet with a leader whose margin differs,
   and check the follower's liq price against the exchange before/after.

3. **Hot-path bench failure (row above): sendable fills do not reach the exchange.** Either a stale
   harness masks a real regression or a real send-path defect is hidden behind three green-looking checks
   (two of which pass vacuously). *Mitigation:* re-point the bench to the current dispatch
   (`_dispatch_fill`/`_process_leader_fill` seams) and re-run; if it still sends 0, treat as a P0 send
   regression.

4. **Missed-entry limits blow the caps (rows 5, 2) and the 5 s mid rule has never passed (row 2).** run4
   showed GTC missed-entry limits bypassing caps and flooding the book; the fix is mock-only. A cap that
   a resting limit can bypass is an unbounded-exposure risk. *Mitigation:* testnet run re-checking total /
   per-asset / per-wallet caps **with** resting limits live.

5. **Dust is still open and only half-mocked (row 9).** run5 still sees 4–10 sub-$10 positions; the whole
   -position-vs-sleeve rule (F1's `test_core_dust_rules.py`) does not exist in this branch. Dust strands
   capital and enlarges the reconciliation diff. *Mitigation:* merge F1's dust tests, then verify on
   testnet that a whole-position close goes out and a sleeve sliver does not.

*(Runner-up: the three-state switch OFF/CLOSE/ON — row 7 — never exercised live; run4's "disarm is not
immediate" is unfixed at 626efd1.)*

---

## Models used (per part)

| Part | Model |
|---|---|
| Spec read, repo navigation (graphify), matrix assembly, evidence cross-referencing, gap ranking | **deepseek-flash** (this Hermes session, `hermes:implementation-owner`) |
| Offline mock-suite execution (43 tests, both envs) | repo's Python 3.11 (`PY311`) — no model |

The envelope's "split parts across your own workers on reliable free models" was attempted via the local
offload router (`python C:\Users\wigmore\.codex\local_offload_router.py --run "<tiny probe>"`), which
returned `OFFLOAD_NOT_RUN::no preferred local Ollama model is installed or reachable` — **no local/free
worker backend was available on this host at run time**, so no part could be delegated. All analysis was
therefore done in-session by **deepseek-flash**; F2 is also a single tight cross-reference where splitting
across weaker models would add transcription risk. No part was routed through the video/openrouter models
the coordinator flagged as unreliable (nemotron, opencode zen). If a worker backend is expected, it was not
reachable from this host — flagged as an environment gap, not an ACK.

## Reproduce

```
git -c core.autocrlf=false clone https://github.com/binancebotty-bot/hyperliquid-build3-repair <dir>
cd <dir>/_archive/hl_stage2
for f in test_*.py; do env -u PYTHONPATH HL_LIVE_ENV_FILE=/nonexistent <py311> -u "$f"; done   # expect 43/43 pass, except the bench
```
Testnet evidence: `hl-build3-testnet-cert-evidence/{RUN1_FINDINGS.md,run3/RUN3_FINDINGS.md,run4/RUN4_FINDINGS.md,run5/RUN5_FINDINGS.md}`
and the repo's own `certification/run_results.json` + `certification/RUN_STATUS.md`.
