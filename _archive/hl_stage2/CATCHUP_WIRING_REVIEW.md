# CATCHUP_WIRING_REVIEW — where `catchup_plan.plan_catchup` would plug into the Core, what it touches, risks, go/no-go

Job J3 (`PARALLEL_JOBS.md`). Repo `binancebotty-bot/hyperliquid-build3-repair`, fresh clone
`C:/Users/wigmore/trading_stack/hl-build3-hermes-J3` (core.autocrlf=false), main `5e88e89`.
Doc + test only. No Core edit, no network, no orders, no keys, no ports 8012/8014/8031, nothing under
`hl-build3-testnet-cert`.

## 0. What was read (evidence base)

- `_archive/hl_stage2/catchup_plan.py` (prototype, pure, 138 lines) and `CATCHUP_PLAN_COMPARISON.md`.
- `_archive/hl_stage2/HL_Live_Copy_Service_Core.py` (the Core), specific regions:
  - `already_closed_late_entries` L291–316 (the engine's *existing* catch-up skip pass)
  - `mergeable_fills` L2460 / `merge_leader_fills` L2471–2487 (`merged_fill_ids` L2482)
  - `LiveCopyCore.leader_cursor_next` L8359–8366; `_plan_batch` L8326–8357
  - `run_cycle` catch-up window: cursor/overlap L9390–9400, cursor write-back L9415–9454,
    `closed_late` pass L9462–9473, dedupe L9474–9476, dispatch L9477–9484, sync plan L9486–9487
  - `_dispatch_fill` L8259–8316, `_is_close_fill` L8318–8324 (EXIT-first routing)
  - `_already_handled` L8674–8677, `_guard_key` L8670–8672, pre-send idempotency `_process_leader_fill` L8707–8727
  - `_pre_send_ownership_gate` L4395–4464
  - `ManualLedger.sleeve`/`sleeve_id` L2873–2897, `classify_leader_side_for_wallet` L2925–2933
  - `stale_snapshot_replay_reason` L778–788
- `_archive/hl_stage2/test_core_outage_replay.py` (the RE3 outage fixture this job replays).

Confirmed by graph and by search: `plan_catchup` is **imported by nothing** in the engine — its only callers
are `test_catchup_plan.py`, the new `test_catchup_re3_fixture.py`, and the comparison doc. It is a prototype.

## 1. What the net planner is

`plan_catchup(fills, held_before) -> {steps, net, leader_after, netting, notes}` for ONE (wallet, coin)
window: it emits at most one CLOSE (of the engine's sleeve, first) and/or one ENTRY = the signed **net** of the
whole window, and SKIPs late entries whose leader position returned to flat later in the same batch.
`net` is the signed sum over **all** window fills (including skipped); the emitted ENTRY/CLOSE sizes are derived
from that same `net`.

**Position-preservation (proven, see §5):** `held_before + Σ emitted step sizes == held_before + Σ raw fill sizes`
in every branch. Netting/skipping never moves the copy relative to honest per-fill replay. That is the property
that makes the prototype *safe in principle*; it is **not** the property that makes it *wirable* (see §4 R1–R3).

## 2. Where it would plug in

The engine already has the exact seam: `run_cycle` builds a catch-up window
(`_start = max(cursor-overlap, now - catchup_ms)`, L9390–9400), sorts the fills, and then runs its **own**
net-ish reduce: `closed_late = already_closed_late_entries(fills, utc_now_ms())` (L9462) → skip late entries →
drop already-handled → dispatch per fill (async workers, L9477–9484) or `_plan_batch` (sync, L9486).

The natural insertion point is **L9462–9487**, as a per-(wallet, coin) pre-pass replacing (behind a flag) the
`already_closed_late_entries` + `_plan_batch` pair:

1. group the window's fills by `(leader_wallet, canonical_coin_key)` (same key as `_plan_batch` L8338);
2. for each group call `plan_catchup(group, held_before=ledger.sleeve(wallet, coin)["signed_size"])`;
3. translate steps into Core work: CLOSE → an EXIT/REDUCE intent for that sleeve (routed via the priority lane,
   `_is_close_fill` L8318), ENTRY → an entry intent at the newest price; SKIP → a terminal reconciliation row
   (`MISSED_ENTRY_LEADER_ALREADY_CLOSED`-style, as L9468 already does);
4. carry **every** window fill id (plus `merged_fill_ids`) on the single emitted fill so idempotency absorbs them.

CLOSE-before-ENTRY ordering is already the engine's rule (`_plan_batch` sorts EXIT groups first, L8355;
`_is_close_fill` sends closes on the priority queue), so the planner's "CLOSE first" matches.

## 3. Invariants the Core imposes on any net planner

**(a) Idempotency.** Dedup is per fill id: `_guard_key` (L8670) → `_idem_accepted`, and a merged copy additionally
absorbs `merged_fill_ids` at L8726–8727. A net order is 1 copy for N fills, so the planner **must** stamp the copy
with the ids of *all* window fills it consumed (not just the first, as the prototype's `fill_ids` are informational
only). Miss this → next poll re-offers the un-absorbed fills and they are counted a second time.
The existing `merge_leader_fills` (L2482) is the pattern to reuse.

**(b) Cursor.** `leader_cursor_next` (L8359–8366) refuses to move past the oldest fill still queued/in-flight
(`_pending_ts`). The net order is **one** queue entry covering N fills, so the planner must keep the cursor
floored at the oldest fill of the window until that single entry is released, or a restart replays the whole
window (harmless only if (a) is airtight) — and worse, `run_cycle` L9421–9428 advances the durable cursor to
`now` on `POLL_OK`, so an un-absorbed window fill is silently lost after a restart.

**(c) Pre-send ownership gate.** `_pre_send_ownership_gate` (L4395) compares the **exchange** coin net with the
engine sleeve net and blocks entries when the exchange holds more than the sleeves explain
(`OWNERSHIP_GATE_UNEXPLAINED_EXCHANGE_POSITION`), and blocks closes into unexplained positions. A net planner
changes *when* the exchange and the ledger agree (one order instead of a sequence), so the gate's mid-sequence
states (e.g. CLOSE applied, ENTRY not yet) must not be read as a residual. CLOSE+ENTRY of a flip are two orders;
they must not be allowed to interleave with the gate's snapshot read.

**(d) Sleeve attribution.** Everything is keyed by `sleeve_id = wallet::coin` and `position_id` (L2873–2897).
The planner's single ENTRY for a window can both close and open (flip). The emitted ENTRY must land in the
**same** sleeve and not silently create a new `position_id` while the old sleeve's CLOSE is unlinked. `held_before`
must be read from that sleeve, not reconstructed.

## 4. Exact risks (with severity)

- **R1 — the plan is RELATIVE; it ignores the leader's own startPosition. (HIGH)**
  `net` is a *delta*; the plan returns `held_before + net`. It never checks `held_before` against the leader's
  `startPosition` on the window's first fill. Verified at runtime: leader window `0 → +3 → +5` (true end +5.0),
  `plan_catchup(..., held_before=0/5/-2)` returns leader_after `5/10/3` — off by exactly the mismatch.
  If the engine's sleeve is mis-tracked, the net planner **faithfully reproduces the error** instead of correcting
  to the leader's true position. The engine's per-fill path already keys its skip rule off the leader's
  `startPosition` (`already_closed_late_entries`, L305–311) — so wiring the net plan *without* reconciling
  `held_before` from `startPosition[0]` is a behaviour regression. Mitigation: refuse to net when
  `|held_before − startPosition(first fill)| > eps`, or net to the leader's absolute end instead of a delta.
- **R2 — idempotency granularity. (HIGH)** See §3(a): one copy for N fills; every window fill id + merged ids must
  be absorbed, or double-send / lost-close on re-read.
- **R3 — cursor boundary. (HIGH)** See §3(b): one queue entry, N fills, durable cursor advances to `now` on
  `POLL_OK`. Without adaptation a crash between queueing and sending loses the window.
- **R4 — no per-order notional cap. (MEDIUM)** `_plan_batch` caps each merged run at `max_order_notional`
  (L8334–8342); the net plan has **no cap**. A big catch-up window nets to one order larger than the cap. Must be
  re-checked (and split, or the window netted in cap-sized tranches) before wiring.
- **R5 — skip rule differs from the engine's. (MEDIUM)** The prototype skips a late entry when the leader returns
  to flat **inside the batch** (pure batch timeline). The engine skips only when the entry is *older than* 60 s
  (`HL_LIVE_CATCHUP_NET_AGE_MS`) AND startPosition is known on every fill (L297–315). So the net plan would skip a
  **fresh** open+close that the engine would copy today — a different trade outcome, not just a different order count.
- **R6 — sizing-mode translation. (MEDIUM)** Step `size` is a *leader unit* quantity; fixed-mode copies a fixed
  notional **once per merged fill** (L2460–2468), proportional sums it. The emitted net size must go through
  `intent_builder._copy_notional`, not onto the wire.
- **R7 — staleness / source. (LOW)** Net fills would be synthetic; they must carry a source the
  `stale_snapshot_replay_reason` (L778–788) and the REBUILD source boundary (L10176–10187) treat correctly, and
  must not be mistaken for fresh WS fills.
- **R8 — partial-window / history gap. (MEDIUM)** When only part of the outage window is readable the planner
  still nets what it has. The engine already emits `LEADER_HISTORY_GAP` (L9395) — the planner must run **only**
  on a window it can prove is complete, else it nets a truncated window (compounding R1).
- **R9 — audit trail. (LOW)** One net order replaces N per-fill rows; the audit must still record one terminal row
  per raw fill (the RE3 invariant) or the integrity checker will see "missing" fills.

## 5. Test evidence (this job's deliverable)

New file `_archive/hl_stage2/test_catchup_re3_fixture.py` (no Core change) replays the **RE3 outage fixture**
(reproduced verbatim from `test_core_outage_replay.py`: 300 fills / 20 coins / 0–120 s old / alternating
`Open Long`/`Close Long` / 5 seeded sleeves of 5.0) through `catchup_plan`, and compares the final net position to
honest per-fill replay, per (wallet, coin) and in aggregate.

- Variant A — exactly as RE3 builds it (no `startPosition`): planner must fall back to per-fill; final position
  **equal** to per-fill replay.
- Variant B — same fills with the exchange's `startPosition` present: planner **nets** (20/20 groups netting,
  order steps 20 vs 300 fills); final position **still equal** to per-fill replay.
- Branch coverage the RE3 fixture cannot reach (it emits only ENTRY+SKIP): four fixture-shaped windows force
  CLOSE-only and flip (CLOSE then ENTRY); each also position-preserved.

`HL_LIVE_ENV_FILE=/nonexistent python -u test_catchup_re3_fixture.py` → **TOTAL=28 FAILED=0, exit 0.**
Mutation controls (prove the test can fail): ignoring the CLOSE step → exit 1; letting SKIP steps contribute
their size → exit 1. Existing `test_catchup_plan.py` still 11/11.

## 6. GO / NO-GO

**NO-GO to wire `catchup_plan` into the Core as-is.**

It is *position-preserving* (proven over the RE3 fixture and the targeted branches) but **not gated for a live
engine**: R1 (relative target — silently reproduces a mis-tracked sleeve), R2/R3 (idempotency + cursor
granularity — one order for N fills against per-fill dedup and a durable `now` cursor), and R4 (no notional cap)
are each sufficient to cause a wrong order or a lost window in production.

**GO only as a bounded, flag-gated pilot** once all of the following land (engine thread owns the Core change;
this job wrote the test + this review and made no Core edit):
1. Reconcile `held_before` from the window's `startPosition[0]`; refuse to net on mismatch (R1).
2. Stamp the emitted copy with every window fill id + `merged_fill_ids` so idempotency absorbs the window (R2).
3. Keep `leader_cursor_next` floored at the oldest window fill until the net entry is released (R3).
4. Apply the `_plan_batch` notional cap (and tranche) to the net order (R4).
5. Run only on a provably complete window, behind a flag, dry-run/audit first, with one terminal row per raw
   fill retained (R5, R8, R9).

Given the aggregate safety result, a flag-gated dry-run pilot is low-risk; the un-gated wiring is not.

---
_Model used for this job: deepseek-flash (the answering deepseek route); one independent verification worker on
`deepseek-v4-flash` via the local FreeDeepSeek proxy, which produced the R1 lead (verified at runtime above)._


---

## Addendum (J3 re-run): the §5 test file was MISSING from the repo - it is written now

§5 named `_archive/hl_stage2/test_catchup_re3_fixture.py`, but that file was **not in the repo** at main `5e88e89`
(`test_*catchup*` matched only `test_catchup_plan.py`). It is written now, exactly to the shape §5 describes, and
green: **TOTAL=29 FAILED=0, exit 0**. No Core edit; the review above is unchanged and stands.

What the test proves (all on the RE3 fixture: 300 fills / 20 coins / 0-120 s / alternating BUY / size 0.1 @ 100.0 /
first 5 coins carrying an owned sleeve of 5.0):

- **Variant A** (exactly as RE3 builds it - no `startPosition`): `netting is False`, 300 `FILL` steps, no SKIP and no
  net order, and the end position equals honest per-fill replay for **every** group and in aggregate.
- **Variant B** (a coherent `startPosition` on every fill - seeded coins stand at +5.0, the rest at +1.0, so no coin
  returns to flat inside the window): `netting is True` for **20/20** groups, exactly **20 order steps for 300 fills**,
  positions still equal per group and in aggregate, and each group's `net` equals that window's raw signed sum.
- **Branches the RE3 shape cannot reach** - CLOSE-only (one `CLOSE` sized to the sleeve), a flip (`CLOSE` then `ENTRY`
  with the remainder), a partial reduce (one `ENTRY`), and the flat-return window (no order): all position-preserved.
- **Mutation controls** (the comparison must be able to fail): ignoring the `CLOSE` step is detected; a wrong flip
  sign is detected; letting `SKIP` steps contribute is detected.
  **Instrument finding:** that third control is only meaningful on a window whose *skipped subset does not net to
  zero*. On a flat-return window the skipped sizes sum to zero by construction, so counting them is a no-op and a
  control there can never fail (my first run failed exactly there - the control, not the planner). It is pinned on an
  unbalanced window instead: open +2, flat, re-open +3, reduce 1 (SKIP +2 then ENTRY +2; the mutant reads +4).
- **R1, pinned as a check** (not just prose): the window `0 -> +3 -> +5` with `held_before` 0/5/-2 returns
  `leader_after` 5/10/3 - the plan is relative and will faithfully reproduce a mis-tracked sleeve. Matches §4 R1.

Line refs re-verified against main when writing the test (the counts in the review body drifted slightly):

| claim | verified at |
|---|---|
| every window fill id + `merged_fill_ids` must be absorbed by idempotency | `merged_fill_ids` stamped L2482, absorbed L8726-8727 |
| the cursor never passes an unprocessed fill | `leader_cursor_next` L8359-8366 (floored at the oldest queued/in-flight fill) |
| the merged notion is capped, the net plan is not | `LiveConfigManager.max_order_notional` L2727, applied to intents L3495 (L8334-8342 is the merge site, not the cap) |
| the engine's own skip rule is age-based, not batch-shape | `already_closed_late_entries` L291-316, `HL_LIVE_CATCHUP_NET_AGE_MS` default 60 s |

Verdict unchanged: **NO-GO to wire as-is; GO only as a flag-gated, dry-run pilot once R1-R4 are closed.** The
position-preservation result is now backed by an executable test as well as by the doc. Neighbours still green:
`test_catchup_plan.py` 11/0, `test_core_outage_replay.py` 17/0.

_Model used for this addendum: deepseek-flash (Hermes session). No worker, no Core edit, offline only._
