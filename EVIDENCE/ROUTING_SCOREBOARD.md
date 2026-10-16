# ROUTING SCOREBOARD — live lane scoring for Build-3 worker dispatch

Owner: coordinator (Hermes). Purpose: route each task to the compute most likely to *complete* it.
This file is the durable scoreboard; update it from measurement, never from impression.

**How to score (the discipline):**
- A lane's score is set by OUTCOMES (artifacts committed / cards done), not by "it ran".
- Never score from a card's summary — read the actual artifact (`git ls-files`, hash the blob).
- Re-measure after any provider change; free windows expire silently.
- Only the coordinator edits this file. Workers report evidence; they do not set scores.

## Scoring axes

| axis | meaning |
|---|---|
| **COMPLETE** | does a dispatched card on this lane actually reach a committed artifact? (the only axis that matters) |
| **SUSTAIN** | does one worker turn survive many tool calls, or die after 1–3? |
| **THRPT** | observed log growth per card per interval (bytes/interval) when healthy |
| **CEIL** | how many concurrent cards before the lane degrades (429s / stalls) |
| **FIT** | task shapes it suits (long agentic loop vs short mechanical) |
| **COST** | free / subscription / paid |

## Current matrix (measured 2026-10-16)

| lane | provider:model | COMPLETE | SUSTAIN | THRPT | CEIL | FIT | COST |
|---|---|---|---|---|---|---|---|
| **Luna** | `openai-codex:gpt-6-luna` | ✅ proven — completed `t_1941b50c` (committed a UI delta to an isolated branch) | ✅ strong | high | testing at 3 | long agentic, precise git/edit work | ChatGPT subscription (included) |
| **Gemini** | `gemini:gemini-2.5-flash` | ⏳ no artifact yet (but best bulk progress: sustained ~4.8 KB/50 s/card) | ✅ multi-minute turns, proper tool-calls | high | ~9 measured, untested beyond | bulk evidence/analysis | free |
| **Free DeepSeek** | `custom-deepseek-free:deepseek-v4-flash-thinking-nosearch` | ⏳ no artifact yet this session (but the ONLY lane to complete a card earlier: `t_e9241c2e`) | ✅ | med | ~5 | general | free proxy — BOUNDED load (also the harness's own inference path) |
| **nous** | `nous:*:free` (longcat / laguna-xs / laguna-s) | ❌ none | ❌ dies after 1–3 tool calls under load | low | ~3–4 (50 req/min ACCOUNT-wide, shared) | nothing long; only low-concurrency fill | free |
| **groq** | `groq:openai/gpt-oss-120b` | ❌ none | ⚠️ | low | 1 | tiny jobs | free tier (small) |
| **local ollama** | `local-zimablueai:gpt-oss:20b` | ❌ none | ❌ invents tools (`manage_kanban`), exits without a board call | n/a | 1 (serial) | non-tool auxiliaries ONLY | free/local |
| **OpenCode/Zen** | — | ❌ 100% `no_result_written` | ❌ | n/a | n/a | **RETIRED — do not retry** | retired |
| **Cerebras** | — | ❌ | ❌ | n/a | n/a | no free quota (HTTP 402) | n/a |

Legend: ✅ proven · ⏳ partial signal · ⚠️ weak · ❌ fails · **COMPLETE is the only axis that earns a lane the primary queue.**

## Concurrency probing (operator directive 2026-10-16)

There is **no imposed concurrency cap** — the only real limits are *available models* and *available
tasks* (`kanban.max_in_progress_per_profile` is set high on purpose). So concurrency is found by
**probing each provider upward until it actually breaks**, then recording the ceiling and the refill.

Protocol:
1. Run a provider at its current proven level N.
2. If it completes/holds with all workers alive → **raise N by 1** next wave.
3. Record the failure mode at the breaking point (429? stall? cooldown? account starvation?).
4. Record the refill schedule — when the provider tops back up (free windows and daily buckets
   silently refresh; many refresh at **00:00 UTC**).
5. Update the lane's CEIL row. Never lower a lane's proven ceiling without evidence.

Distinguish failure modes when a probe breaks: **provider-limited** (429 / fair-share / cooldown →
real ceiling) vs **harness-limited** (protocol violation, invented tool, EOL churn → not a provider
signal; fix the task shape, not the concurrency).

### Probe log

| date | lane | level tried | result | next |
|---|---|---|---|---|
| 2026-10-16 | **custom-deepseek-free** | 6 | ⚠️ **CORRECTED — NOT a real 6.** README: *"Real parallelism is the number of idle logins"*; `DEEPSEEK_MAX_CONCURRENT=24` is only the process cap. We have **3 logins** → true ceiling **3**. At 6, cards queue behind busy logins (`DEEPSEEK_ACCOUNT_LOCK_WAIT_MS` 120s) and a login can enter cooldown (`DEEPSEEK_ACCOUNT_COOLDOWN_MS` 600s). 429 modes: `concurrent_chat_blocked` (lock wait ran out), `rate_limit` (all logins cooling). **Effective ceiling = 3** (raise by adding logins, not cards). | hold at 3; add a login to go higher |
| 2026-10-16 | openai-codex (luna) | 3 | ✅ held | probe 4 |
| 2026-10-16 | gemini | 8 | ✅ held | probe 9 |
| 2026-10-16 | nous | 7 then 4 | ❌ broke at both — account-wide fair-share 429 | ceiling ~3 |

**LESSON (false green):** "N cards are running and the lane looks healthy" is NOT proof of N-way parallelism. Check the PROVIDER's own documented parallelism (logins / accounts / concurrency knob) and its in-flight vs lock counts. A queue that drains slowly looks identical to concurrency until you read the provider's internals.

## Lane-specific blockers (measured, not assumed)

| class | blocker | evidence |
|---|---|---|
| **UI rows** | need **rendered-DOM capture + an independent oracle**; workers have **no browser route**, and must not drive the operator's Edge. HTTP probes cannot produce a DOM proof — workers correctly record `NOT_TESTED` rather than substitute. | 4 cards (UILCC5/6, UISSM/UISSM2) all completed with per-row `"HTML source text alone is not render proof"`. This is a CAPABILITY gap: the fix is a worker browser route or re-scoping rows to HTTP-verifiable ones. |
| **NETWORK / SETTLE / ORDER / ENGINE-FAIL rows** | need the live **testnet transport runtime + captured request/packet oracle**; absent on this machine. | Every worker blocked with the missing runtime NAMED; none mocked. On Codex's list per controller. |
| ~~`/api/live-audit-summary` broken~~ | **CORRECTED**: it is NOT broken. Measured `HTTP 200`, 5,847,300 bytes, 138,730 rows, **3.9–6.8s** by two independent cards. Slow, but it responds. | Do not re-assert "endpoint down" — my original claim came from a single observation and was wrong. |

**LESSON:** do not call a surface "broken" off one timeout. Measure it directly (status + bytes + elapsed) before carding a fix — a slow endpoint and a dead endpoint need different work.

## Standing routing rules (derived from the above)

0. **FILL EVERY LANE, EVERY CYCLE.** An idle lane with a card available to run is a routing failure. Enumerate
   the lanes, set each one a target, and keep them fed from the runnable pool: deepseek-proxy 3 (its 3-login
   ceiling), luna 4 (paid cap), nous ~2-3, gemini as much as it holds. Do not leave a lane dark because the
   board "looks busy" elsewhere. (Learned: sitting at 2 running while four lanes were idle drew a well-earned
   correction.)
1. **A CARD'S SCOPE MUST BE STATED, NEVER INFERABLE.** If a card covers N rows, ENUMERATE the ids in the body.
   A worker given "18 rows" with no list will (correctly) refuse, block, and — after two identical blocks —
   land in TRIAGE, where it loops. Triage is a terminal state for repeat-offenders, not a queue: it drains
   only when the underlying cause is fixed. (Learned: two cards looped purely because the coordinator omitted
   ids, and the count was wrong — 17, not 18.)
Token budget: state the ids; a shorter card is not cheaper if it loops.
2. **Route by COMPLETE evidence, not by capability claims.** A lane with one proven completion outranks a lane with nine impressive-looking running cards.
2. **Luna (subscription) and Gemini (free) are the primary lanes.** Put the highest-value and longest tasks there.
3. **Free DeepSeek is bounded** (a few cards) — it doubles as the harness's own inference path; flooding it risks the orchestration loop.
4. **nous cannot hold a long card.** Use it only for short fill or when nothing better is available; a 60-row card on nous is a guaranteed zero.
5. **Never route to OpenCode, Cerebras, or paid DeepSeek.** Paid DeepSeek needs separate per-instance authority; the free DeepSeek proxy is authorised but bounded.
6. **Spread across providers, not across models inside one provider.** OpenRouter's free cap is account-wide; nous's ceiling is account-wide.
7. **Task-size the lane:** tasks that exceed one context/quota window die — decompose to 3–6 rows, or route to a lane that sustains a long turn (Luna/Gemini).
8. **Re-score on evidence:** after every completion or repeated failure, update the owning lane's row here.

## Score updates (append-only log)

| date | lane | change | evidence |
|---|---|---|---|
| 2026-10-16 | Luna | new lane, scored ✅ COMPLETE | `t_1941b50c` done; branch `hermes/ui-delta-landing` @ `5223ce25`; blob EOL-normalised SHA256 `f5af3eb5…` matches source; shared checkout untouched |
| 2026-10-16 | nous | downgraded to ❌ | fair-share 429 collapses at 4 and 7 workers; cards died after 1–3 tool calls |
| 2026-10-16 | local ollama | scored ❌ | real worker loop: invented `manage_kanban`, no board call, exit rc=0 |
| 2026-10-16 | OpenCode/Zen | RETIRED | docs 404; ~30 jobs 100% `no_result_written` |
| 2026-10-16 | Cerebras | scored ❌ | HTTP 402 payment_required on real call |
