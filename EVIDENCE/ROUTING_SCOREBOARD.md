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

## Standing routing rules (derived from the above)

1. **Route by COMPLETE evidence, not by capability claims.** A lane with one proven completion outranks a lane with nine impressive-looking running cards.
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
