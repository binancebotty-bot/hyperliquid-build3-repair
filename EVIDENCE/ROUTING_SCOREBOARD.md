# Routing scoreboard

**Derived:** 2026-10-18 19:09 UTC — regenerate with `python tools/cert/routing_scoreboard.py --write`

Ranked by **proven completions**, not by health. A lane that is 'up' has proven nothing.

---

## Outcomes by lane (completed cards)

| lane | PASS | FAIL | NOT_TESTED | other | total | pass rate |
|---|---:|---:|---:|---:|---:|---:|
| `?` | 44 | 0 | 5 | 22 | 71 | 62% |
| `custom-deepseek-free` | 30 | 1 | 29 | 25 | 85 | 35% |
| `openai-codex` | 21 | 20 | 65 | 16 | 122 | 17% |
| `gemini` | 7 | 0 | 9 | 3 | 19 | 37% |
| `openrouter` | 5 | 1 | 1 | 3 | 10 | 50% |
| `nous` | 2 | 1 | 9 | 2 | 14 | 14% |
| `local-zimablueai` | 0 | 0 | 0 | 1 | 1 | 0% |
| `groq` | 0 | 0 | 1 | 0 | 1 | 0% |

## Live state

| lane | running | ready | ceiling |
|---|---:|---:|---:|
| `custom-deepseek-free` | 6 | 8 | 3 |
| `openai-codex` | 2 | 9 | 4 |
| `gemini` | 5 | 8 | 4 |
| `openrouter` | 1 | 7 | 2 |
| `nous` | 2 | 5 | 3 |

## How to read this

- **PASS rate is per lane, not per model.** The provider a card ran on is the lane setting at completion; it is not a controlled experiment.

- **NOT_TESTED is not a lane failure.** It usually means the evidence did not exist, not that the worker could not do the job. Judge lanes on FAIL and on whether they finished at all.

- **A high PASS count with a low pass *rate*** means the lane took a lot of work and returned little.

- **Never rank on health checks.** 'It responded' and 'it delivered' are different claims.

## Important caveat: reviewer cards inflate the FAIL column

A lane that runs many **review** cards will show many FAILs — because a reviewer rejecting work is the gate
**succeeding**, not the lane failing. `openai-codex` shows 20 FAIL in 122; most are verdicts, not delivery failures.

**Read FAIL rate per card TYPE, not per lane.** For routing decisions the useful split is:
worker cards (did it finish and produce evidence) vs reviewer cards (did it reject something it should have).

A lane's health is also not its competence. Every lane on this board has responded to a probe; far fewer have
produced a certified row.
