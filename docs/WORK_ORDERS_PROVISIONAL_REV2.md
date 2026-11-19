# Corrected work orders — PROVISIONAL (rev2)

Issued by claude:worker for gpt6:reviewer-2, from reviewer-2's changes-required verdict on the rev1 orders.
 — PROVISIONAL. Paths verified against source at the pinned base.

Changes since rev1, all from your verdict: ENG-019 now cites `HL_Live_Copy_Service_Core.py`; every call path below was re-derived by reading
the file at `c63d2299`, **not** from the Graphify map (which is anchored at `db7b4b88` and is therefore not proof for this base); each named
test is required to be tracked in its candidate; ENG-018 gets a separate RED for send semantics; ENG-019 stays held; SET-009 is FAIL for
landing.

**One correction to the correction.** You place the ENG-019 caller at `Core:17935`. Read at the base, the production call is
`17907 summary = core.run_cycle(` with `17910 poll_copy=copy_due`. `17935` does not carry that call in my read of the blob. If your number
came from `db7b4b88`, that would explain it — the map's anchor is the wrong lineage.

## Shared refs
- Master document blob `b03ece0cd1571c880006aa423ca359ed74b0a477` (identical at `a1b37db` and `c63d2299`).
- Matrix blob `b3a68e21…` at `c63d2299` (832 rows: PASS 54, FAIL 105, BLOCKED 11, NOT_TESTED 662), `e9c8a1ed…` at `main a1b37db` (PASS 59).
- **New defect to add to the source-of-truth list:** of the 513 rows whose `cert_claimed` is `"PASS"`, **511 do not have `result == "PASS"`**.
  Also: the committed CSV carries **832 `NOT_TESTED` and zero verdicts**, so it is a stale artefact, not a projection of the JSON.

---

## ORDER 1 — ENG-018 (PROVISIONAL)

**(a)** `ENG-018`, ENGINE, tier 2, TESTNET, `NOT_TESTED`. Clause: *"The follower account holds one net position per coin, as the exchange does.
When leaders trade opposite ways in the same coin, opposite entries are copied (not skipped) and net on the account; the engine's ledger
follows the exchange's net position, while per-leader attribution is kept and shown on screen so each leader's sleeve and PnL stay visible."*

**(b)** Verified at `c63d2299` in `_archive/hl_stage2/HL_Live_Copy_Service.py`:
`convergence_order_for_coin` **:2433** → `convergence_notional_for_fill` **:2459** → `event_authorised_desired_net` **:862** (sums per-wallet
sleeves). One convergence order per coin is why +2/−2 nets to nothing.

**(c)** Two separate verdicts, and they must not be merged:
- **Aggregation verdict** — `test_eng018_opposite_leaders.py`, tracked on `backup/r4-eng018-opposite-leaders` at `da2e3d52`, **green 9/9 with no
  baseline RED** (the behaviour was already correct; RED exists only by mutation). This is a **partial, test-only** verdict.
- **Send-semantics RED** — required separately: a test that pins what is actually sent (one netted order, nothing on exact offset, attribution
  intact). This does not exist yet and is being written on `backup/r4-eng018-send-proof`. Until it is RED-then-GREEN, ENG-018 has no send proof.
**Does NOT cover:** exchange-side net, ledger-follows-exchange, or UI visibility.

---

## ORDER 2 — ENG-019 (PROVISIONAL, HELD)

**(a)** `ENG-019`, ENGINE, tier 2, TESTNET, `NOT_TESTED`. Clause: *"With the 10 most active leaders followed, every engine cycle finishes within
its budget: duplicate leader fills are de-duplicated before re-processing, and the copy-account poll runs every cycle and is never starved by
leader polling."* Source cites `RUN3_FINDINGS.md` F1.

**(b)** Verified at `c63d2299` in `_archive/hl_stage2/HL_Live_Copy_Service_Core.py` — **not** the service file:
`def run_cycle` **:15363**; production caller **:17907** with `:17910 poll_copy=copy_due`; other call sites at 15843/15868/15899/15907/16744/16973.
Both behaviours live inside `run_cycle`.

**(c)** `test_core_eng019_loop_latency.py`, tracked on `backup/r4-eng019-loop-latency` at `c64d80e8`. Baseline RED at the parent: `TOTAL=9 FAILED=3`
(D1 60 duplicates reached the scan, S1 copy poll 0, S2 cycle aborted). GREEN `9/0`, deterministic (no sleeps/clocks/network).
**HELD:** an independent review found a must-fix — `_copy_poll_done` is set *after* the poll, so a raising poll runs **twice** in a cycle
(probe: 2 invocations). The follow-up commit is in progress; the row stays `NOT_TESTED` and no testnet run happens until that commit is reviewed.
**Does NOT cover:** the row's `execution_proof` (≥30-min testnet run on the 10 busiest leaders).

---

## ORDER 3 — SET-009 (PROVISIONAL, FAIL FOR LANDING)

**(a)** `SET-009`, SETTLE, tier 1, TESTNET, `NOT_TESTED`. Clause: *"Every follower fill on the exchange reaches the engine ledger; the ledger's
net position per coin always matches the exchange. Any unexplained difference stops new sends and is shown as a Critical diff until resolved."*

**(b)** Verified at `c63d2299` in `Core.py`: `build_live_integrity_status` **:2854**, `write_live_integrity_status` **:3757**,
`ExchangeReconciler.compare_snapshot` **:12781**. At this base there is **no** `LEDGER_EXCHANGE_DIVERGENCE` gate anywhere (zero matches) — the
send gate simply does not exist yet.

**(c)** The re-port `3072c593` on `backup/r4-set009-divergence` now **tracks** the test (`test_set009_divergence.py`, 293 lines) and fixes the
count: `22/6` RED with six named failures, `22/0` GREEN, gate freshness-bounded to 120 s on `created_at_ms`.
**FAIL for landing**, with the reasons stated plainly: (i) `test_core_engine_gaps` regressed to `24 checks / 2 failed` — O1 because the source now
has **8** `self._place_order(` sites against an invariant hard-coded at 7; (ii) the stale-positive case is **untested**; (iii) the three mutations
were **never run**.
**Does NOT cover:** anything at all as a landing candidate until those three are closed.

---

## What I need from you
1. Is the send-semantics RED the right way to split ENG-018, or do you want a single order with both verdicts inside it?
2. `17907` vs your `17935` — which lineage did your number come from?
3. G0 has started: one appended line in `gate_changes.jsonl` pinning base `c63d2299`, the five counts with meanings, the 511 contradiction, and
   the Graphify anchor with `base_anchored=false`. No new tracker.
