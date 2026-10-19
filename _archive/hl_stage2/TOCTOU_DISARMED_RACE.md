# OFF-to-ON TOCTOU in the disarmed fill fast path

Branch fix/toctou-disarmed-race-t_eadaf921, cut from 89b3bc7, carrying eb91d9a (fast path) plus one fix commit.
Offline only: no engine armed/disarmed/restarted/reconfigured, live_config.json untouched, no network I/O (test raises on requests.post).

## 1. The race, at file:line

Baseline eb91d9a:_archive/hl_stage2/HL_Live_Copy_Service_Core.py.

Disarmed check - _process_leader_fill_inner line 10372 (second read at 10375):
    if self.cfg.send_mode_now() == "OFF":
        return self._process_disarmed_leader_fill(fill, summary, merged_ids)

Point after which the fill is unrecoverable - _process_disarmed_leader_fill lines 10301-10304:
    with self.dedupe._lock:
        self.dedupe.processed.add(fill.leader_fill_id)
        self.dedupe.processed.update(merged_ids)

    terminal_state = classify_terminal_state(
        "MASTER_REAL_ORDERS_OFF", "MASTER_REAL_ORDERS_OFF", lifecycle, False)

Nothing re-reads the arm state between 10372 and 10304. If send_mode=ON is written in that window the fill is already
in dedupe.processed (a replay is dropped as duplicate) and an SEND_NOT_ATTEMPTED_AUTO_SEND_DISABLED row claims it was
skipped on purpose: no order, no retry, audit trail says intentional. Reachable for an engine that booted armed, was
disarmed from the config file, then re-armed (send_mode_now latches OFF only for an engine that booted disarmed).

## 2. The fix, and why

Re-read the arm state atomically at the decision point AND record a racy fill as deferred - both halves.

- _arm_generation() (line 10267): ('ON'|'CLOSE', 0) when armed, ('OFF', config mtime) when disarmed. Any arm change moves it.
- Token is read where the OFF decision is taken (lines 10438-10441, 10446-10449) and passed in as arm_decision.
- _process_disarmed_leader_fill re-reads it under _arm_decision_lock at the last moment (10360-10366); if it moved, the
  fill is not terminalised: _hold_deferred_disarmed_fill (10278) rolls back the dedupe/idempotency bookkeeping, writes one
  REPLAY_DEFERRED_DISARMED_RACE row naming the leader fill id and reason, and queues it on the existing deferred
  scheduler (kind 'disarmed'). The scheduler re-offers it to the armed path; a later pass that still sees OFF writes the
  real terminal row.

Why the lock-only alternative is worse: holding a lock across decision and send would serialise every fill behind one
lock (the throughput regression the fast path exists to avoid) and still would not cover the state moving after release.
The token re-read is an mtime compare, never spans a network call. Deferring without a token check cannot distinguish a
racy fill from a genuine skip. Performance win preserved: genuinely disarmed engine still takes the fast path with zero
network calls.

## 3. Proof: fails before, passes after

test_core_toctou_disarmed_race.py, 18 checks. Boots armed, disarms from config, hooks _invalidate_disarmed_fill_caches to
re-arm exactly between the OFF decision and the dedupe marking (injected, not hoped for).

- Pre-fix eb91d9a, same test file: TOTAL=18 FAILED=10. Fill terminalised MASTER_REAL_ORDERS_OFF /
  SEND_NOT_ATTEMPTED_AUTO_SEND_DISABLED, never held, never re-offered, never sent.
- Fixed core: TOTAL=18 FAILED=0.

Regression on fixed core: test_core_disarmed_fast_path.py 18/18, test_core_missed_entry_rule.py 93/93,
test_core_toctou_disarmed_race.py 18/18.

## 4. Second finding: a fast-pathed fill still resolves

Demonstrated: after the held fill is re-offered to the armed path the engine's own writer produces a real
send_attempts.csv row for that leader fill id (RACED_FILL_RESOLVED_WITH_A_SEND_ROW), and outage_classify.py over that
audit dir returns a resolved outcome - not MISSING, not DEFERRED_OPEN (CLASSIFIER_UNRESOLVED_ZERO_FOR_RACED_FILL). The
deferred phase leaves exactly one audit row with reason and leader fill id
(ONE_AUDIT_ROW_WITH_REASON_AND_LEADER_FILL_ID) and no disarmed terminal row for the raced fill
(NO_DISARMED_TERMINAL_ROW_FOR_RACED_FILL).

## 5. Reproduce

    cd _archive/hl_stage2
    python test_core_toctou_disarmed_race.py   # 18/18
    python test_core_disarmed_fast_path.py     # 18/18
    python test_core_missed_entry_rule.py      # 93/93

Check out eb91d9a, drop the same test file beside it and run it: 10 checks fail.
