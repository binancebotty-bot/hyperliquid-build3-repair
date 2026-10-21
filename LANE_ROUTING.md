# Lane routing & worker capacity — Build 3 (do not rediscover a 3rd time)

Durable, in-repo record of the model route this lane MUST use and the concurrency cap it runs
under. Landed as a commit in THIS repository (AGENTS.md rule 13) so it is reviewable/revertible.

## 1. The lane's required model route

- Provider: `custom-deepseek-free`
- Model:    `deepseek-v4-flash-thinking-nosearch`
- base_url: `http://127.0.0.1:9655/v1`  (FreeDeepseekAPI local proxy)

**Model id and provider are DIFFERENT fields — never put a provider name in the model field.**
`set-model <task> <model> --provider <provider>`; the first argument must be a real model id. A card
written with `model_override = custom-deepseek-free` makes every call return
`400 invalid_model: Unknown model: custom-deepseek-free` in **0 ms** (no DeepSeek call happens), and
Hermes then treats the route as dead and cascades down the fallback chain — which looks exactly like a
rate limit but is a config bug. Observed 2026-10-21; it repeated on every respawn.

Audit after ANY batch of model/provider edits — must return 0:
```sql
select count(*) from tasks
where model_override in ('custom-deepseek-free','nous','gemini','openrouter','openai-codex');
```
Distinguish the two failure shapes before "fixing" anything: **0 ms / `invalid_model`** = wrong model id
(local config bug); **429 with `Слишком частые сообщения` or fair-share** = a real provider cap.

Every Build-3 Kanban card must be pinned to this (its `provider_override` + `model_override`).
Do NOT re-pin cards to a cloud free-tier route — those are capped (section 2).

## 2. Why — the free-tier cloud routes are CAPPED (evidence)

- `nous` route: HTTP 429 `You've reached this model's current fair-share rate limit`
  (`~/.hermes/logs/agent.log`, 2026-10-14 14:06). A capacity cap — retrying does not clear it.
- `opencode-free` route: HTTP 403 `FreeTierError`.
- Result: workers pinned to those routes exit `rc=75` and requeue in a loop (the "churn").

## 3. The local proxy IS live (verified 2026-10-14)

- `GET http://127.0.0.1:9655/readyz`  ->  `{"ready":true,"ready_accounts":2,"total_accounts":2}`
- `GET http://127.0.0.1:9655/health`  ->  `status:ok`; accounts `deepseek-auth` + `worker-2`, both `cooldown:false`.
- `GET http://127.0.0.1:9655/admin/requests?limit=8` -> HTTP **200** on
  `deepseek-v4-flash-thinking-nosearch` seconds before this note was written.

So the route is correct and healthy. Do not go hunting for a "dead proxy" — there is not one.

## 4. CRITICAL — worker concurrency cap (this is the real fix)

- The proxy pool is **TWO** DeepSeek logins; its design rule is **one in-flight chat per login**.
- Safe concurrency = **2 workers at most**; serialise beyond that.
- A burst of **7 ready cards** -> the dispatcher spawns all 7 at once -> DeepSeek message-FREQUENCY
  limit ("Слишком частые сообщения") -> each worker exits **75 (rate-limited)** and requeues.
- **Therefore: never release more than 2 cards to `ready` at the same time.** Keep the remainder
  `blocked` and release as slots free. The dispatcher spawns EVERY ready card, so the cap can only
  be enforced at release time — not after.

## 5. Wake cadence

- Current: ALL Build-3 cron wakes are PAUSED (operator, to stop the rate-limit burn).
- Requested cadence + model are stated to `gpt:reviewer-controller` via the control mailbox for
  authorisation. Cron is NOT edited from here (outside this repository, AGENTS.md rule 13).
