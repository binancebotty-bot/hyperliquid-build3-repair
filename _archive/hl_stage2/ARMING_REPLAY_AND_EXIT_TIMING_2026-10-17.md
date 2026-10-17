# Arming-replay collapse + EXIT timing stamps (offline analysis)

Task t_4363d795 - CLAUDE RULING (issue #81 comment 6234144390). Branch off 89b3bc7. NOT merged.
Author: Hermes (offline analysis). Reviewer rules.

Data (read-only, never modified):
C:/Users/wigmore/trading_stack/hl-build3-testnet-cert/_archive/hl_stage2/hl_live_copy_audit_testnet/append_only/
reconciliation.2026101{5,6,7}.*.csv + reconciliation.csv, order_intents.*.csv, send_attempts.csv - Oct 17 only.

---

## PART A - the arming-replay path

### A1. Why a fill older than 10 minutes traverses the full pipeline

Two independent reasons; only one is the 10-minute number.

(a) The 10-minute gate decides COLLAPSE only, and only for POLL fills.
HL_Live_Copy_Service_Core.py:438-456

    age_ms = max(0, int(fnum(os.getenv("HL_LIVE_CATCHUP_COLLAPSE_AGE_MS"), 600000)))   # 10 min
    for f in fills:
        if (f.source != "POLL" or now_ms - int(fnum(f.timestamp_ms, 0)) <= age_ms
                or (f.raw or {}).get("startPosition") in (None, "")
                or (handled is not None and handled(f))):
            keep.append(f)          # traverses the full pipeline

A fill is netted only if source == POLL AND older than 600000 ms AND has startPosition AND is not handled.
Everything else - every WS_CAPTURED fill, every fill younger than 10 min - passes through untouched into
_process_leader_fill.

(b) The full pre-send cost is paid BEFORE the engine learns it may not send.
_process_leader_fill (:10188-10269), in order, for every fill that reaches it:

    cancel_resting_entries_against(fill)   :10188   network (cancel round-trips)
    _read_fills_of_withdrawn_limits        :10189   network
    _prewarm_with_parity(fill, ...)        :10193 -> :9337-9350   network (leader read + prewarm)
    intent_builder.build(fill)             :10235   local
    audit.append_order_intent(intent)      :10251   CSV append under the shared file lock
    send_if_allowed(intent, ...)           :10269   HERE MASTER_REAL_ORDERS_OFF is finally returned (:5988-5989)

The disarmed test lives at the very end, inside send_if_allowed. A disarmed engine pays the whole network +
audit cost of an order it was never going to place. Constant but large per fill, spent on fills that cannot act.

### A2. What the blocks were - reason counts

Reasons ARE recorded: one reconciliation.csv row per leader fill carries terminal_state, same row holds the
leader fill id. Nothing missing.

Disarmed window 2026-10-17T03:48 -> 05:40, 36841 terminal rows, top 12:

    21534  58.5%  SEND_NOT_ATTEMPTED_AUTO_SEND_DISABLED
     7031  19.1%  NO_MANUAL_POSITION_TO_CLOSE
     4637  12.6%  (blank - non-terminal event rows: FILL_MERGED / GATE_WOULD_BLOCK etc.)
     2464   6.7%  ENTRY_BLOCKED_RISK
      930   2.5%  SEND_NOT_ATTEMPTED_SYMBOL_UNAVAILABLE
       97   0.3%  BLOCKED_DUPLICATE_DEDUPE_STORE
       59   0.2%  RESTING_ENTRY_ALREADY_GONE
       52   0.1%  MERGED_INTO_HEAD_COPY
       26   0.1%  RESTING_ENTRY_CANCELLED_SENDING_OFF
       10  <0.1%  STALE_WS_SNAPSHOT_IGNORED
        1  <0.1%  MISSED_ENTRY_EXCHANGE_REJECTED_UNKNOWN

Whole Oct 17, SEND_NOT_ATTEMPTED_AUTO_SEND_DISABLED = 57077 rows.

The ruling's 14549 cannot be reproduced from the CSVs. No field in reconciliation.csv or order_intents.csv
carries it, and no single terminal_state bucket equals it for the window or the day. Closest defensible: the
disarmed window wrote 21534 rows whose only reason was 'send is disabled'. If 14549 came from a dashboard backlog
gauge it counts a different unit (e.g. queued keys at one instant) and must be reconciled before being quoted
again. THIS is the instrumentation gap: nothing writes a per-cycle backlog high-water mark to disk, so the
backlog curve exists only in memory.

### A3. The premise is partly wrong - these were not stale fills

Three independent measurements; the second changes the diagnosis.

(i) Intent source during the disarmed span (order_intents, 03:48-05:10, 23290 intents / 23225 distinct fills):

    WS_CAPTURED   22852   98.1%
    POLL            386    1.7%
    WS_SNAPSHOT      52    0.2%

98% of what the pipeline chewed through was captured live off the websocket as it arrived. A stale replay would
be POLL (or WS_SNAPSHOT); POLL is 1.7%.

(ii) Almost no send_attempts rows exist in the disarmed span - 1 row, 03:48-05:40. Contrast the immediately
preceding 1h47m (02:00-03:47): 23987 rows. So the engine made essentially no exchange order calls while disarmed,
which is correct. But it DID write 23290 order_intents rows and 21534 SEND_NOT_ATTEMPTED_AUTO_SEND_DISABLED rows in
that span, and the block reasons prove network work happened anyway:

    1103  'no fresh follower-network (testnet) price to value the order'   <- a price read failed
     701  'SYMBOL_BLOCKED'                                                 <- symbol resolution ran
     728  'max wallet exposure exceeded'

The cost was prewarm/price/symbol reads plus a CSV append per fill, not exchange order calls. That is exactly the
cost A4 removes.

(iii) Fill age. send_attempts cannot answer this for the disarmed span because it holds one row - the age table a
first pass of this analysis attributed to the drain actually belongs to the 02:00-03:47 period (n = 23987, p50 3 s,
p90 9 s, 96.4% under one minute). It is reported only for that period and is not evidence about the drain. The
honest statement for the drain: fill age during the disarmed span is NOT recorded, because age is only stamped when
a send attempt row is written and none were. Same instrumentation gap as A2.

Conclusion stands, on (i) alone: the drain was not a replay of old fills. It was fresh live WS fills flowing
through a disarmed engine, each paying prewarm + audit. collapse_stale_runs could not have helped - its source gate
excludes WS_CAPTURED and its age gate would exclude fills arriving live. The 10-minute replay path exists but was
not the load.

### A4. Proposed cheap collapse

Not 'collapse old fills harder' - the cost is on fresh fills while sending is off. One early gate, O(1) per fill,
no network. In _process_leader_fill, right after the dedupe decision and BEFORE cancel_resting_entries_against
(:10188) and _prewarm_with_parity (:10193):

    if not self.cfg.master_switch_now() and not converge:
        intent = self.intent_builder.build(fill)        # local only, no prewarm
        self.audit.append_order_intent(intent)          # same row as today
        self.dedupe.processed.add(fill.leader_fill_id)
        self.audit.append_reconciliation(
            "SEND_TERMINAL", "SEND_NOT_ATTEMPTED_AUTO_SEND_DISABLED", ...same fields as :9847-9857...)
        return False, "AUTO_SEND_DISABLED", intent

Why the three conditions hold:
- O(1) per fill, no network: skips cancel_resting_entries_against, _read_fills_of_withdrawn_limits and
  _prewarm_with_parity - all three are the network calls. blocked_locally (:4092-4113) already makes no network
  call, so build without prewarm is local.
- One audit row per leader fill: the SAME SEND_NOT_ATTEMPTED_AUTO_SEND_DISABLED row written today by
  _append_send_terminal (:9843-9857) - same terminal_state, same leader_fill_id, same reject_category.
  Merged fills keep their FILL_MERGED rows (:10253-10260).
- UNRESOLVED 0: not a new outcome, it is the state the fill already reaches today. has_fill_row (:10290) still
  finds a row, so the BLOCKED_NO_TERMINAL_RECORDED fallback never fires.

Semantics unchanged because those fills are already burned today: dedupe.processed and _idem_accepted are updated
on the current blocked path, so re-arming does not retry them. The gate only removes work that provably cannot
produce an order.

Measured ceiling: in the disarmed window the three skipped calls were paid 23225 times; at a conservative 2
network round-trips each that is ~46k round-trips that produced nothing.

Deliberately NOT proposed: raising HL_LIVE_CATCHUP_COLLAPSE_AGE_MS or dropping the source == POLL filter. Both
risk netting live fills into synthetic orders - a behaviour change the ruling did not ask for.

---

## PART B - EXIT path timing

### B1. What was untimed, and why it was invisible

The EXIT branch of _send_real makes three network calls that had no stamp at all. The row jumped from
wire_validated_ms (:6425) straight to margin_mode_started_ms (:6439), so everything between was attributed to
nothing.

    1  _withdraw_standing_close(...)      :6435   cancels a resting recovery close - a cancel round-trip
    2  _close_wire_plan(...)              :6449   sizes the close from the follower account
    3  _fresh_exchange_net(...) inside 2  :5876   an HTTP read of the follower account on EVERY close

Why invisible: ENTRY/ADD never call (1) or (2), and the only existing liq_parity_* stamps (:6030-6032) are on
the ENTRY/ADD branch of send_if_allowed. EXIT rows had no interval that could account for their residual - the
724 ms p50 / 3.2 s p90 the ruling measured sat inside a gap with no columns.

### B2. The change (branch, not merged)

Six new columns in both SEND_ATTEMPT_FIELDS (:704) and SEND_TIMING_FIELDS (:718):

    standing_close_started_ms, standing_close_finished_ms,
    close_plan_started_ms, close_plan_finished_ms,
    exchange_net_started_ms, exchange_net_finished_ms

Stamped at :6434/:6436, :6448/:6451 and :5875/:5877. exchange_net_* nests inside close_plan_* on purpose: it is
the one network sub-step of the close plan, so close_plan_finished - close_plan_started - (exchange_net_finished -
exchange_net_started) is the plan's local cost.

No behaviour change: stamps only, no branch altered, no call added or removed.

### B3. Tests

test_core_exit_timing_stamps.py (same branch) - 16 checks, all pass:
- each of the 6 fields present in both field lists (12 checks)
- _close_wire_plan actually stamps exchange_net_started_ms/exchange_net_finished_ms, finished >= started > 0
- the source carries both stamp pairs at the standing-close and close-plan call sites

Run: HL_LIVE_ENV_FILE=/nonexistent python3 -u test_core_exit_timing_stamps.py -> ALL_EXIT_TIMING_STAMP_CHECKS_PASS

Regression, unchanged by this branch: test_core_close_to_target.py 21/21, test_core_engine_gaps.py 23/23.

---

## What the reviewer should rule on

1. Accept that the drain load was FRESH WS fills while disarmed, not stale replay - and therefore that the
   collapse belongs at the arming check, not in collapse_stale_runs.
2. Accept or reject the A4 early gate. It is PROPOSED, not implemented, in this branch.
3. The 14549 figure is not reproducible from the audit CSVs; state which surface produced it before it is used
   again in a soak criterion.
