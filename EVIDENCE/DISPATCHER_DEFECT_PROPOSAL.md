# PROPOSAL FOR THE EXTERNAL AGENT — three defects in the Kanban dispatcher

**Status: PROPOSAL ONLY. Not applied. Hermes install not modified.**
Prepared by Hermes (project `hyperliquid-build3-repair`) at the controller's direction (comment `6270961056`), because
editing `~/.hermes/hermes-agent` is outside this project's authority.

    target:  NousResearch/hermes-agent   release 0.22.2 (d923a5eb)
    file:    hermes_cli/kanban_db_dispatch.py   (139,166 bytes)

Every measurement below was taken on the operator's machine on 2026-10-19.

---

## DEFECT 1 — `blocker_auth` never expires; one 429 poisons a card permanently

**Severity: highest. This stops the board entirely after a few hours of work.**

### Observed

When a worker exits on a provider rate limit, the task is released to `ready` with a stamp:

    last_failure_error = "pid 48404 exited rate-limited (quota wall) - requeued without counting a failure"

`_respawn_guard` then matches that text via `_RESPAWN_BLOCKER_RE` and returns `"blocker_auth"`, so the card is **skipped on
every subsequent tick, forever**. The text is never aged out.

Measured state at the stall:

    ready cards carrying that stamp:   18 of 18   (100%)
    dispatcher log:                    "kanban dispatcher stuck: ready queue non-empty for 21 consecutive ticks but
                                        0 workers spawned. Check profile health (venv, PATH, credentials)"
    actual cause:                      none of the 18 were eligible; credentials were fine

Clearing the 18 stamps by hand restored spawning on the very next tick (`spawned=1` at 16:16:28, then 16:18:13,
16:19:57, 16:22:45). On this host roughly half of all spawn attempts return `exit_code 75`, so the queue re-poisons faster
than it drains, and the operator is dependent on manual clearing.

### Why the existing exemption does not fire

The rate-limit exemption in `_respawn_guard` requires **both**:

1. the latest run's `outcome == "rate_limited"`, **and**
2. `rl_cooldown > 0`

A run recorded as `spawn_failed` (which is what an infrastructure/quota refusal produces in some paths) leaves
`outcome != "rate_limited"`, so the exemption is bypassed and the stamp matches `blocker_auth` instead.

### Proposed change

Either, or both:

- **Age the stamp.** In `_respawn_guard`, before matching `_RESPAWN_BLOCKER_RE`, ignore `last_failure_error` when the most
  recent `task_runs.ended_at` for that task is older than a configurable `blocker_auth_max_age_seconds` (default 600).
  A quota condition is transient by nature; a ten-minute-old quota message is not evidence of anything.
- **Match the outcome, not only the text.** Extend the rate-limit exemption to `outcome == "spawn_failed"` when the
  metadata carries `exit_code == 75` (the `EX_TEMPFAIL` sentinel), so both representations of the same condition take the
  cooldown path.

### Failing case to test with

    ready task with last_failure_error = "... exited rate-limited (quota wall) ..."
    latest task_runs.outcome = "spawn_failed", ended 30 minutes ago
    EXPECT today:       skipped forever as blocker_auth
    EXPECT after fix:   eligible to spawn (stamp aged out)

---

## DEFECT 2 — a tick aborts on the first failed spawn instead of trying the next ready card

**Severity: high. Converts a partial provider outage into a total stall.**

### Observed

With 18 ready cards and free capacity on three permitted lanes, ticks produced `spawned=0` because the **queue head** sat
on a lane that was refusing. Cards behind it on healthy lanes were never attempted.

    running: 5   ready: 18   lanes with headroom: luna 1/6, nous uncapped, openrouter uncapped
    tick:    "spawned=0" repeatedly, with the head card rate-limited

### Proposed change

On a rate-limit / quota failure for the head card, **advance to the next ready card within the same tick** rather than
ending the tick. Optionally record a short per-provider cooldown so the same walled provider is not retried immediately,
but the tick must continue.

### Failing case to test with

    ready queue ordered: [card A on provider P (P returns 429), card B on provider Q (Q healthy)]
    EXPECT today:       tick ends after A, B never spawned
    EXPECT after fix:   A skipped for this tick, B spawned

---

## DEFECT 3 — `triage` cards count toward `max_in_progress`

**Severity: medium. Silently consumes capacity and misreports the cause.**

### Observed

Two auto-escalated `triage` cards plus 16 running cards made the dispatcher refuse to spawn while reporting capacity
exhaustion, with the same misleading "check profile health (venv, PATH, credentials)" message. Clearing the triage cards
to `ready` immediately produced `spawned=3`, then `spawned=12` on the following tick.

### Proposed change

Either exclude `triage` from the `max_in_progress` count, or name triage in the warning text:
`max_in_progress reached (16 running + 2 triage of 18)`.

### Failing case to test with

    16 running + 2 triage, max_in_progress = 18, one ready card
    EXPECT today:       0 spawned, warning blames credentials
    EXPECT after fix:   0 spawned with a message naming triage, or 1 spawned if triage is excluded

---

## What Hermes is doing meanwhile (no install changes)

- `tools/cert/clear_stamps.py` — clears `blocker_auth` stamps only when the card's latest run ended more than 10 minutes
  ago, logs each clear to `~/.hermes/state/blocker_auth_clears.log`, and exits non-zero if the DB cannot be read.
- Concurrency capped at **7** per the controller's instruction.
- `tools/cert/provider_guard.py` — refuses any card assigned to a provider the operator has not authorised, and treats
  `provider_override = NULL` as a violation because it silently resolves to the forbidden profile default.

Neither script modifies the Hermes install; both only read and write the Kanban database.
