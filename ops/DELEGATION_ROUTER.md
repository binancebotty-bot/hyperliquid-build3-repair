# Free-model delegation router (how any agent on this PC hands work to Hermes/OpenCode)

Plain scripts, no AI, no windows. Owner: PC operator thread. Update this file whenever the table or rules change.

## Use it (3 steps)
1. Write the job as a prompt file (absolute paths, SHELL NOTE for PowerShell 5.1: no `&&`, one deliverable, <= 15 tool calls, read-only unless it is a coding job in its own clone, never push, no keys/.env).
2. Append ONE JSON line (UTF-8 WITHOUT BOM) to `C:\Users\wigmore\trading_stack\_tools\queue.jsonl`:
   `{"id":"unique","title":"short","prompt_file":"C:\\...\\JOB.md","expect":"C:\\...\\result.csv","max_runtime":900,"models":[["opencode","space-bunny-free"],["openrouter","poolside/laguna-s-2.1:free"],["nous","meituan/longcat-2.5-preview:free"]]}`
   Provider `opencode` runs `opencode run -m opencode/<model>` headless; other providers run as Hermes kanban cards (`--assignee default --provider P --model M`).
   `expect` MUST be a file the job writes; no file = failed = automatic retry once on a different model from the list.
3. Read the result file. Do not poll; the supervisor (`_tools\supervisor.py`, one hidden pythonw) keeps `pump_max` jobs in flight, retries, logs to `supervisor.log`, `model_scores.csv`, `concurrency_log.csv`, acks the dashboard (http://127.0.0.1:8040).

## Rules that were learned the hard way
- ONE-LINE prompts to opencode.cmd: a multi-line argument is cut at the first newline (model sees an empty task). The supervisor sends "Read the file X and do it" for you; put the real task in the file.
- Small jobs: 1 deliverable, 1-2 rows/files. Big jobs (4-5 tests after reading a 12,600-line file) stall at the provider and hold a slot 40 min.
- Name files that exist. Check donor/test file names before putting them in a prompt.
- Max 2 concurrent per model, 4 on nous, 10 on openrouter (OpenRouter free = 1000 requests/day shared). First 429 seen at ~19 concurrent Hermes cards.
- Never use paid or the DeepSeek proxy (127.0.0.1:9655). Free models only. Secrets never go in prompts.
- Free models are advisory: verify results (run the test, check the diff). A PASS is not proof of strength; audit tests with a second model or a mutation check.
- Never `Start-Process` without `-WindowStyle Hidden`; CREATE_NO_WINDOW alone; no focus-stealing windows, ever.

## Model table (refresh with `python -I _tools\perf_report.py` -> `_tools\perf_report.md`)
| model | observed | use for |
|---|---|---|
| opencode/space-bunny-free | reliable, fast | audits, reviews, tests |
| opencode/step-5-preview-free, nemotron-3-ultra-free, longcat-2.5-preview-free, nemotron-3.5-lightning-free | working | general; ultra is slow (~30 min) |
| openrouter nvidia/nemotron-3-super-120b-a12b:free, nemotron-3-ultra-550b-a55b:free | 100% on small jobs | reviews, analysis |
| openrouter poolside/laguna-s-2.1:free | ~75% | tests, small code |
| nous meituan/longcat-2.5-preview:free | ~66% | tests, specs |
| openrouter cohere/north-mini-code:free | ~60%, breaks on shell/`&&` | tiny jobs |
| opencode/big-pickle, mimo-v2.6-flash-free; nous step-3.7-flash, longcat-2.0 | timeouts / free period ended | out of rotation |

## Failure classes (perf_report.py classifies from card logs)
rate_limited_429 -> retry later or other provider | provider_timeout -> retry, smaller job | shell_syntax -> add SHELL NOTE | context_overflow -> shrink prompt | no_result_written -> put the expect-file instruction first | free_period_ended/model_unavailable -> drop model.

## Safety boundaries (this system)
Testnet only; no mainnet orders; never touch Wallet Finder (8014)/scout (8012) except read-only; never change CONTROL_STATE.json gates; supervisor never starts/stops the copy engine or runner (alerts only). Stop it: create `_tools\supervisor_stop.txt`; ramp: edit `pump_max` in `_tools\supervisor.json`.

## Daily allowance cooldowns (free tiers refill about 00:00 UTC)
When a model is exhausted for the day, add it to _tools\model_cooldowns.json as {"model-substring": "ISO-UTC time it refills"} e.g. {"space-bunny": "2026-10-16T00:05:00Z"}. The supervisor (restart once to load) skips a model until that time, then uses it again automatically. Keep every queue entry's full model list: do NOT delete the exhausted model from queue lines.


## Correction (17:10 UTC): limits are often SHORT-TERM concurrency/rate limits, not daily
Space Bunny failed under load (own use + pump) and worked again ~15 min later. So: on failures set a SHORT cooldown (10-15 min) first, and only a refill-time cooldown (00:05 UTC) if it is still failing after 3 retries over 45 min. Per-model concurrency cap 2 stays; lower it to 1 for a model that returns errors under load.

