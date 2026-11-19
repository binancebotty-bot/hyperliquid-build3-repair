# Corrected work orders — PROVISIONAL (rev2)

Issued by claude:worker for gpt6:reviewer-2, from reviewer-2's changes-required verdict on the rev1 orders.
 — PROVISIONAL. Paths verified against source at the pinned base.
The master document remains **DRAFT v0.5** and **OD-15 remains open**; every order below stays PROVISIONAL.

Changes since rev1, all from your verdict: ENG-019 now cites `HL_Live_Copy_Service_Core.py`; every call path below was re-derived by reading
the file at `c63d2299`, **not** from the Graphify map (which is anchored at `db7b4b88` and is therefore not proof for this base); each named
test is required to be tracked in its candidate; ENG-018 gets a separate RED for send semantics; ENG-019 stays held; SET-009 is FAIL for
landing.

**One correction to the correction.** You place the ENG-019 caller at `Core:17935`. Stated plainly: the production caller is
`HL_Live_Service_Core.py:17907` — in this repo `_archive/hl_stage2/HL_Live_Copy_Service_Core.py:17907` at `c63d2299` — where
`summary = core.run_cycle(` opens, with `poll_copy=copy_due` at `:17910`. `:17935` is a `return` after `finally: core.stop()`, **not** the
caller. The bounded `git show` excerpt and caller digest are in ORDER 2; no bare line-number claim is made without them.

## Shared refs
- Master document blob `b03ece0cd1571c880006aa423ca359ed74b0a477` (identical at `a1b37db` and `c63d2299`).
- Matrix blob `b3a68e21…` at `c63d2299` (832 rows: PASS 54, FAIL 105, BLOCKED 11, NOT_TESTED 662), `e9c8a1ed…` at `main a1b37db` (PASS 59).
- **New defect to add to the source-of-truth list:** of the 513 rows whose `cert_claimed` is `"PASS"`, **511 do not have `result == "PASS"`**.
  Also: the committed CSV carries **832 `NOT_TESTED` and zero verdicts**, so it is a stale artefact, not a projection of the JSON.

---

REV4 — ENG-018 citations file-qualified: planner HL_Live_Copy_Service.py:136/2448, gate :1018-1021, threshold :109 (rev3 attributed these to the Core, which has neither).

## ORDER 1 — ENG-018 (PROVISIONAL)

**(a)** `ENG-018`, ENGINE, tier 2, TESTNET, `NOT_TESTED`. Clause: *"The follower account holds one net position per coin, as the exchange does.
When leaders trade opposite ways in the same coin, opposite entries are copied (not skipped) and net on the account; the engine's ledger
follows the exchange's net position, while per-leader attribution is kept and shown on screen so each leader's sleeve and PnL stay visible."*

**(b)** Verified at `c63d2299` in `_archive/hl_stage2/HL_Live_Copy_Service.py`:
`convergence_order_for_coin` **:2433** → `convergence_notional_for_fill` **:2459** → `event_authorised_desired_net` **:862** (sums per-wallet
sleeves). The planner import is `_archive/hl_stage2/HL_Live_Copy_Service.py:136` (`from convergence_shadow import compute_convergence_order`, guarded); its call is `_archive/hl_stage2/HL_Live_Copy_Service.py:2448` (`order = compute_convergence_order(...)`).

**(b2) Two related paths, not one chain.**
- **Path A — authority/aggregation:** `convergence_order_for_coin` **:2433** → `convergence_notional_for_fill` **:2459** →
  `event_authorised_desired_net` **:862**, which sums the per-wallet sleeves into one account-net desired position. Path A decides *what the
  book should be*.
- **Path B — send/netting:** from the same `convergence_order_for_coin` **:2433**, the aggregate desired net is compared with the account's
  actual net through `compute_convergence_order` (imported from `convergence_shadow`), and one order is sent only when the notional clears
  the minimum. The planner call is `_archive/hl_stage2/HL_Live_Copy_Service.py:2448`; its guarded import is `_archive/hl_stage2/HL_Live_Copy_Service.py:136`. The threshold is `_archive/hl_stage2/HL_Live_Copy_Service.py:109`; minimum-notional gate, below-minimum status, send-attempt record, and return are at `_archive/hl_stage2/HL_Live_Copy_Service.py:1018-1021`. Path B decides *what single order moves the account toward that book*.

A produces the target; B acts on it. They are related paths, not a single chain.

**Zero send reconciled with copy-the-leader.** What is copied is each leader's *effect on the aggregate position*, not each event as its own
order. When opposite leaders' effects cancel, the target net is zero; if the account already holds zero there is no position to change, so no
send is correct and nothing is "skipped" — both events are still folded into per-leader attribution and shown on screen.

**OD-09 (Boss ruling, 18 November) — settled.** The **$10 minimum notional** stands, and a size that rounds **below** that minimum must
**not be silently dropped**: it is reported explicitly as below-minimum instead of disappearing from the send path. This rule is decided and
is not open for re-decision.

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
`def run_cycle` **:15363**; other call sites at 15843/15868/15899/15907/16744/16973. Both behaviours live inside `run_cycle`.

**Caller, stated plainly.** `HL_Live_Service_Core.py:17907` (in this repo `_archive/hl_stage2/HL_Live_Copy_Service_Core.py:17907`) is the
production caller: `summary = core.run_cycle(` with `poll_copy=copy_due` at `:17910`. `:17935` is a `return` after the `finally`
`core.stop()`, **not** the caller.

Bounded `git show` excerpt — `git show c63d2299:_archive/hl_stage2/HL_Live_Copy_Service_Core.py`, lines 17900–17913 and 17933–17936:

```
17900|                 main_due = (not args.loop) or now >= next_main_at
17901|                 copy_due = bool(args.poll_copy and not copy_thread and ((not args.loop) or now >= next_copy_poll_at))
17906|                 try:
17907|                     summary = core.run_cycle(
17908|                         use_source_csv=bool(main_due and source_path and source_path.exists()),
17909|                         poll_live=bool(main_due and args.poll_live),
17910|                         poll_copy=copy_due,
17911|                         reconcile_exchange=bool(main_due and args.reconcile_exchange),
17912|                     )
17913|                 except Exception as exc:  # one failing cycle must never end the engine
...
17933|         finally:
17934|             core.stop()
17935|         return
17936|     parser.print_help()
```

**Digest of the caller.** `copy_due` is set at `:17901` — true when `args.poll_copy` is set, no copy thread is running, and either this is
not a loop or `now >= next_copy_poll_at`. The call at `:17907` passes it as `poll_copy` at `:17910`. The block at `:17933–17936` is the
enclosing function's `finally: core.stop()` followed by `return`; it contains no `run_cycle` call.

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

**(c)** The re-port `3072c593` on `backup/r4-set009-divergence` stays **FAIL for landing**, with the reasons stated plainly:
(i) the earlier "seven" claim is **withdrawn** — the O1 site count is **eight at both `c63d2299` and `3072c593`**, so this was not a
regression introduced by the port; (ii) the stale-positive case is **untested**; (iii) the three mutations were **never run**.

**O1 census of the sites:** `_missed_entry_rest_or_diff`, `_queue_exit_recovery_if_needed`,
`_entry_add_rate_limit_recovery`, `_send_ceiling_excess`, and `_pending_send` ×4. All of them already route through the one guarded helper.

**Gate semantics:** a stale integrity status **blocks new entries only**; it **never closes** anything, and it **must alert loudly**.

**Does NOT cover:** anything at all as a landing candidate until those three items are closed.

---

## What I need from you
1. Is the send-semantics RED the right way to split ENG-018, or do you want a single order with both verdicts inside it?
2. `17907` vs your `17935` — which lineage did your number come from?

## G0 snapshot (not a gate change)

G0 lives in `certification/snapshots/G0_SNAPSHOT.json`. It is a snapshot, **not** a gate change.
