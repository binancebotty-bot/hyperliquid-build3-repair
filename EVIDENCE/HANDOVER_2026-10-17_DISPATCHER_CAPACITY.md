# HANDOVER — dispatcher capacity & provider lanes (2026-10-17)

**To the other session working this task:** the operator reports two sessions were pointed at this same
task by mistake. This note records exactly what has ALREADY been applied so you do not redo or
contradict it. Read this before editing config, caps, or cards.

## What was already applied (by the other session — do not repeat)

**Hermes config (global, already written to `~/.hermes/config.yaml`):**

| key | value | note |
|---|---|---|
| `kanban.max_in_progress` | `10` | global cap = measured max concurrency |
| `kanban.max_in_progress_per_profile` | `10` | was **60** (raised by another lane after being set to 2) |
| `kanban.max_spawn` | `3` | max spawns per tick; prevents backlog dumps |

**Cards re-pinned to the provider each title names** (all had `provider_override = ''` before, which
collapsed a 6-way split onto `nous`):

| card | provider | model |
|---|---|---|
| `t_c770a37a` | `custom-deepseek-free` | `deepseek-v4-flash-thinking-nosearch` |
| `t_a37f86f8` | `openai-codex` | `gpt-6-luna` |
| `t_8a3a1ba3` | `gemini` | `gemini-2.5-flash` |
| `t_ac721a85` | `gemini` | `gemini-2.5-flash` |
| `t_15fbacb9` | `openrouter` | `nvidia/nemotron-3-ultra-550b-a55b:free` |
| `t_310e6820` | `openrouter` | `nvidia/nemotron-3-ultra-550b-a55b:free` |

**Card moved off the free proxy:** `t_b9a1f729` was reclaimed and re-pinned to
`nous/meituan/longcat-2.5-preview:free` (it was saturating the 3 proxy logins).

**Card unblocked:** `t_cc9094a9` (transient block) — returned to the queue.

**Aux-helper config fixed** (this was freezing long sessions, unrelated to the board): the compression,
vision, `kanban_decomposer`, `curator` and `session_search` helpers were each sending a model id to the
WRONG service (nous/local ids to Google's endpoint -> HTTP 404), and compression was authenticating with
an exhausted pool OAuth credential. All five now resolve correctly; compression is proven end-to-end
(returned a real summary) and `context_length` is pinned to 1,000,000.

## THE ONE REMAINING BLOCKER — needs an operator decision

**The above caps are NOT live yet.** The running gateway (pid 7752) started **2026-10-15 10:22** and
caches `kanban.*` dispatcher settings at startup. `hermes gateway` has **no reload verb** — only
`stop`/`restart`, which interrupts every live session.

Evidence: with cap=3 and max_spawn=3 in config, the fresh CLI honours them
(`dispatch --dry-run` reports `skipped_per_profile_capped`), while the live gateway still logged
`spawned=7` in one tick.

**Do not restart the gateway without the operator's explicit go-ahead.** Until that restart happens,
the board can still exceed 10 concurrent workers.

## Measured capacity (why 10)

Per-provider concurrency = number of USABLE credentials, because
`agent/credential_pool.py` hardcodes `DEFAULT_MAX_CONCURRENT_PER_CREDENTIAL = 1` (not configurable).

| provider | usable credentials | budget |
|---|---|---|
| `custom-deepseek-free` | 3 logins (1 in-flight chat each) | 3 |
| `nous` | 2 (api key + oauth) | 2 |
| `openrouter` | 2 keys (quota resets 01:00) | 2 |
| `gemini` | 1 | 1 |
| `openai-codex` | 1 | 1 |
| local ollama | 1 | 1 |
| **max concurrency** | | **10** |

Re-verify with `hermes auth list` before trusting this — an exhausted/429 credential contributes 0.

## Queue state at handover

Ready/queued: `t_c1bf8ec5` (openrouter), `t_cc9094a9` (nous). Everything else parked is blocked on REAL
prerequisites, not on dispatch — do not force-promote these:

- missing/unauthorised testnet proof environment (TN rows; mock substitution explicitly forbidden)
- open human decisions awaiting rulings (OD-02/05/13, D-002, ENG rows needing authorised testnet execution)
- `t_16f0cd6b`: browser render route broken — `browser-use` has no registered plugin
- `t_99d9a92c`: expects the repo at `C:/Users/wigmore/projects/hyperliquid-build3-repair`, which does
  NOT exist; the real repo is `C:/Users/wigmore/hyperliquid-build3-repair`
- `t_91e9c7f2`: needs a task-specific clean worktree (shared checkout is dirty at a different HEAD)

## Audit commands

```sql
-- cards running with no provider pin (the collapse-to-default trap)
select id,title from tasks where status='running' and coalesce(provider_override,'')='';

-- status distribution on the default board
select status, coalesce(nullif(provider_override,''),'(none)') p, count(*)
from tasks group by status,p order by status;
```

```bash
hermes kanban boards                                   # boards are SEPARATE DBs
hermes kanban --board default set-model <task> <model> --provider <provider>
hermes kanban --board default reclaim <task> --reason "..."
grep -a "kanban dispatcher" ~/.hermes/logs/gateway.log | tail -5
```

## Coordination note

If you need to change the caps, change the SAME three keys above (do not introduce a second mechanism).
If you believe a different number is right, state the evidence in a comment on the card rather than
editing config — two sessions editing global config is exactly how the cap drifted to 60.
