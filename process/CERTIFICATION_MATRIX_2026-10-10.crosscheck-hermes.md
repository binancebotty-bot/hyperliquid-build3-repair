# Cross-check of CERTIFICATION_MATRIX_2026-10-10.md (independent reproduction, hermes)

The matrix at `process/CERTIFICATION_MATRIX_2026-10-10.md` was already on this branch when my F2 turn started
(commit be0ddee, the parallel lane working the same round). I did NOT overwrite it. This file records my independent
verification plus three deltas. Offline only: the engine, the cert dir, ports 8012/8014/8031, the Wallet Finder and
any key/.env were untouched.

## Independently reproduced
- Same method: from `_archive/hl_stage2`, `HL_LIVE_ENV_FILE=/nonexistent python -u <test>.py`, PY311, scrubbed
  `PYTHON*` (the inherited PYTHONPATH shadows a broken `pydantic_core` and aborts 13 files before their first check -
  the peer's two-run control is correct).
- 43 test files on 626efd1: **all pass except `test_hotpath_replay_bench.py` (7 checks, 3 FAIL)** - the same finding
  the peer recorded (`BENCH_40PCT_REACHED_THE_EXCHANGE` sent=0 of 8 expected, `BENCH_60PCT_BLOCKED_LOCALLY` blocked=20
  of 12 expected, `BENCH_STAGE_STAMPS_PRESENT_AND_ORDERED` rows=0). Ran twice, identical.
- **Root cause added:** the bench wires a symbol blocklist but NO `account_net_provider`, while the engine requires
  authoritative account-net truth before any entry. `test_g2_copy_correctness` proves both halves and PASSES:
  "account_net_actual -> ACCOUNT_NET_TRUTH_UNAVAILABLE" and "unavailable account-net -> ZERO order authority". So all
  20 fills are correctly held and none reaches the exchange; the bench's `expected_sent=8` is stale. The fix belongs
  to the bench, not the engine; the bench's timing checks (queue-wait p90, fill-to-ack p90) PASS.
- Spot-checked the peer's cited check ids against my own runs: `test_core_liq_parity` L5/L6/L7/L9 (10/0),
  `test_core_liq_projection` 3x (6/0), `test_core_memory_bounds` rotation (16/0), `test_core_switch_states` (11/0),
  `test_core_poll_fallback` (11/0), `test_t1b_startup_orphan` / `test_t1c_stop_cancel` (10/0 each),
  `test_g3_exchange_truth` (48/0), `test_g2_copy_correctness` (41/0), `test_core_network_and_global_controls` (62/0).

## Deltas to the matrix
1. **Row 9 (dust) "does not exist in this branch" -> it now exists on `hermes/f1`.** I wrote `test_core_dust_rules.py`
   (11 checks, 11/0) on branch `hermes/f1` (commit 55430af): (a) sub-min entry never sent + recorded as a diff;
   (b) sub-min reduce that is not the whole position not sent + recorded; (c) sub-min close of the WHOLE account
   position sent reduce-only, and the round-up-to-min branch is ENTRY/ADD-only; (d) $10.00 exactly sent, $9.99
   blocked; (e) with the account short 1.0 across two 0.5 sleeves, closing 0.5 is blocked and closing the whole
   account 1.0 is sent. `run5_converge` D1/D4 also pass (23/0). Remaining honest gap unchanged: a sub-min whole close
   on a DIVERGED ledger stays blocked (the exception requires ledger == exchange - fail-closed).
2. **Row 8 (liquidation parity):** agreed, mock-only; the two files are the head commit's own feature (PR #41) and
   total 16 checks (liq_parity 10 + liq_projection 6), all passing offline.
3. **Gaps:** my independent ranking matches the peer's #1 (mainnet slippage) and #2 (liquidation parity). Adding the
   stale bench as a process gap: a bench whose expectations predate the account-net authority rule keeps failing and
   would mask a real hot-path regression, so fix it before using it as a gate.

Model: Hermes deepseek-flash (this session), all parts. No worker used (the only reachable delegation route is the
config delegation model nous/poolside, which the round excludes; config.yaml must not be changed).
