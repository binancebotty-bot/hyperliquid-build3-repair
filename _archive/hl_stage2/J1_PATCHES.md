# J1 — disk-full robustness: findings and proposed patch

Runner: `test_core_disk_full.py` (22 checks). Two-run control on this branch:

    HL_LIVE_ENV_FILE=/nonexistent python -u test_core_disk_full.py
    main (5e88e89)                       -> TOTAL=22 FAILED=8
    main + J1_PATCH_disk_full_robustness -> TOTAL=22 FAILED=0

The patch is **not applied** here (engine code is the engine thread's). Apply from the repo root:

    git apply _archive/hl_stage2/J1_PATCH_disk_full_robustness.diff

`HL_Live_Copy_Service_Core.py` has a BOM and mixed CRLF/LF: apply the diff byte-exactly (git apply), never
through an editor that normalises line endings.

This diff supersedes the earlier `DISK_FULL_PATCH_PROPOSAL.diff` on this branch (see the SUPERSEDED banner in
`DISK_FULL_FINDINGS.md`): it keeps the same `log_error` fix and protects the same failure points without changing
the send-path semantics (no `return`-instead-of-raise at the intent append), and adds short-write detection, temp
cleanup, the engine-loop guard and the integrity counter.

## What already holds on main (no change needed)

* Order intents are appended **before** any send: a failing intent append sends nothing (A1) and the worker
  boundary contains it and logs `ws_hot_send` (A2, A3); the next fill is still processed (A4).
* A failing `pending_send` row is fail-closed: no exchange call, status `SEND_NOT_ATTEMPTED_AUDIT_WRITE_FAILED`
  (B1, B2).
* The final send row failing after the exchange accepted the order still sends exactly one order and the
  pre-written `pending_send` row (with the deterministic cloid) keeps the order named (B3); the per-fill caller
  contains it (B3B).
* A sent order is engine-owned and its cloid is deterministic, so a retry reuses the same client order id and the
  exchange rejects the duplicate (C1, C3).
* `write_live_integrity_status` is already guarded in its per-cycle caller and a later call still runs (D1, D2, D3).

## Findings (FAILS on main) and the fix in the patch

| # | Check(s) | Observed on main | Fix in the diff |
|---|----------|------------------|-----------------|
| 1 | A5, B4 | With **every** audit write failing (a real full disk), `log_error()` is itself an `append_csv()` write, so the error path throws: `_run_plan` propagates `OSError(28)` — the worker dies (and a failed `log_error` inside `run_cycle`'s `except` would end the engine). | `log_error` never raises (falls back to stderr); `append_csv` records the failure in a plain-text journal and re-raises. |
| 2 | C4 | A reconciliation append that fails **after** an order was sent leaves no trace: `build_live_integrity_status().counts` has no audit-write key. | `note_audit_write_failure()` + `counts["audit_write_failures"]` (durable via `audit_write_failures.log`, survives a restart). |
| 3 | D4 | `run_cycle`'s `finally` calls `self.state_writer.write(summary, ...)` unguarded; a state/runtime json write failure escapes `run_cycle` (behavioural: `run_cycle` raised `OSError(28)`). | guard the state write with `except Exception -> log_error("cycle_state_write", ...)`. |
| 4 | D5 | `main()`'s `summary = core.run_cycle(...)` sits under a `try:` whose only handler is `finally: core.stop()` — one failing cycle ends the process. | wrap the loop's `run_cycle` call with `except -> log_error("run_cycle_loop", ...)`, keep looping. |
| 5 | E1 | `append_csv` ignores `f.write()`'s return value: a short write (fewer bytes stored, **no exception**) appends a truncated row (observed `notes='MARKER-NOT'`). | compare `written` to `len(payload)`; on a short write raise `OSError` after journalling. |
| 6 | E2 | `atomic_write_json` ignores the temp write's returned length: a short write publishes a truncated JSON; the next `load_json` silently falls back to defaults (silent state loss). | compare `written` to `len(text)`; raise on a short write. |
| 7 | E3 | A failed `os.replace` leaves the `*.tmp` behind (observed) — a full disk accumulates orphans and gets worse. | unlink the temp on **any** failure before re-raising. |

## Note on the harness (a corrected false finding)

The intent-append containment is asserted at `_run_plan` (the production worker boundary), not at
`_process_leader_fill` itself: every production call to `_process_leader_fill` is wrapped by `_run_plan._one`
(`log_error "ws_hot_send"`) or by `run_cycle`'s outer `try`. An earlier draft asserted containment on the bare
method and reported A2/A3 as gaps that the caller already closes. Every single-file case is also paired with a
whole-disk case (A5, B4), because a containment path that logs through the same broken disk is not a containment
path — that pairing is what surfaced finding #1.
