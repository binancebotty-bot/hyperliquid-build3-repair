# Lane routing & worker capacity — Build 3 (do not rediscover a 3rd time)

Durable, in-repo record of the model route this lane MUST use and the concurrency cap it runs
under. Landed as a commit in THIS repository (AGENTS.md rule 13) so it is reviewable/revertible.

## 1. The lane's required model route

- Provider: `custom-deepseek-free`
- Model:    `deepseek-v4-flash-thinking-nosearch`
- base_url: `http://127.0.0.1:9655/v1`  (FreeDeepseekAPI local proxy)

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

## 4. Worker concurrency cap — MEASURED 2026-10-17 (supersedes the earlier "2 logins" note)

- The proxy pool is **THREE** logins (`deepseek-auth`, `worker-2`, `worker-3`); its design rule is
  **one in-flight chat per login** -> **3 concurrent proxy workers**.
- **Per-provider concurrency = the number of USABLE credentials.** Each credential is hardcoded to one
  in-flight request (`agent/credential_pool.py`: `DEFAULT_MAX_CONCURRENT_PER_CREDENTIAL = 1`), and that
  is not configurable. Count them with `hermes auth list` (an exhausted/429 entry counts as 0).
- Measured budget, 2026-10-17:

  | provider | usable credentials | budget |
  |---|---|---|
  | `custom-deepseek-free` | 3 logins | 3 |
  | `nous` | 2 (api key + oauth) | 2 |
  | `openrouter` | 2 keys (quota resets 01:00) | 2 |
  | `gemini` | 1 | 1 |
  | `openai-codex` | 1 | 1 |
  | local ollama | 1 | 1 |
  | **max concurrency** | | **10** |

- **CORRECTION to the previous claim that "the cap can only be enforced at release time":** the
  dispatcher DOES support caps —
  `kanban.max_in_progress` (global), `kanban.max_in_progress_per_profile`, and `kanban.max_spawn`
  (max spawns per tick). They do not have to be simulated by holding cards back.
- **But a running gateway caches them at startup.** `hermes gateway` has **no reload verb** — only
  `stop`/`restart`. A cap edit is NOT live until the gateway restarts. Verify by comparing the gateway
  process start time with the config file mtime; if config is newer, the cap is not in effect.
- **Config drift is real:** `max_in_progress_per_profile` was set to 2 and was later found at **60**
  (raised by another session). Always re-read the value before trusting it. With 60, a released backlog
  spawned **23 workers in one tick**.
- **A blocked dispatch accumulates a backlog that is then dumped at once:** the gateway logged
  `dispatcher stuck ... 26 consecutive ticks ... blocker_auth`, then `spawned=23`. Keep `max_spawn`
  small (e.g. 3) so lanes fill over several ticks instead of all at once.
- **Unpinned cards collapse onto the profile default.** On 2026-10-17 six cards titled with a provider
  (`[luna:gpt-6-luna]`, `[gemini:2.5-flash]`, `[openrouter:nemotron]`, `[deepseek:v4-flash]`) had
  `provider_override = ''`, so a planned six-way split became 10 concurrent `nous` calls on 2 leases ->
  fair-share 429s and 100-170s retry sleeps while other providers sat idle.
  Audit and fix:
  ```sql
  select id,title from tasks where status='running' and coalesce(provider_override,'')='';
  ```
  ```bash
  hermes kanban --board default set-model <task> <model> --provider <provider>  # applies next dispatch
  ```
- `todo` is NOT the dispatch queue: `todo` waits on a parent task, `ready` is the queue. An empty To Do
  column is normal; what matters is whether ready cards are being deferred.

## 5. Wake cadence

- Current: ALL Build-3 cron wakes are PAUSED (operator, to stop the rate-limit burn).
- Requested cadence + model are stated to `gpt:reviewer-controller` via the control mailbox for
  authorisation. Cron is NOT edited from here (outside this repository, AGENTS.md rule 13).
