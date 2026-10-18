# RETRACTIONS — claims we stopped believing

**Append-only. Never edit or delete an entry.** Each entry states what was claimed, what replaced it, and why.
If a number appears here, it must not appear anywhere as current.

This file exists because a withdrawn claim that is merely *superseded in conversation* looks identical to a live
claim to anyone reading the thread. The 579 figure was corrected five times in comments and still circulated as
current.

---

## R-001 — "579 of 790 rows PASS"

- **Claimed:** the register shows 579 PASS, substantiated.
- **Replaced by:** **74 audit-verified PASS**; 301 demoted; 201 never audited. The 579 was the *claimed* count, not
  the verified count.
- **Why:** audits showed most UI PASS evidence was not row-bound — the checks would pass for any row.

## R-002 — "302 / 432 / 380 PASS"

- **Claimed:** various intermediate union totals.
- **Replaced by:** R-001. All superseded.
- **Why:** union arithmetic defects (missed commit-based audits; double-counted nested per-check verdicts).

## R-003 — "UI certification is partially complete"

- **Claimed:** ~27 UI rows had been re-earned.
- **Replaced by:** **zero UI rows certified.** All 87 rows citing `UI_CORRECTION_2d29211.json` demote under one
  standard: the check does not assert anything specific to that row's own `execution_proof`.
- **Why:** the 27 "keeps" flip when the same standard is applied uniformly.

## R-004 — "571 ms + 250 ms + 250 ms explains the 1121 ms order"

- **Claimed:** a three-component decomposition of order latency.
- **Replaced by:** **"one round trip plus an unmeasured engine-side remainder."** Component sizes withdrawn.
- **Why:** the components were inferred magnitudes, not measurements. No captured real order interval was
  correlated to them, and the `/exchange` probe used an invalid signature deliberately. What survives: transport
  ~46 ms measured; 571 ms is `/info` answer time (p50 570.5, n=12); POST reuses a pooled session. The
  *two-round-trip* premise remains falsified on measurement.

## R-005 — Two UI artifacts reported as PASS

- **Claimed:** `t_775a0935` (citing `b5e6d613`) and `t_f262b6dc` (citing `6cf5dcf6`) passed.
- **Replaced by:** **both withdrawn.** `:8031` PID 8668 started `2026-10-15T09:28:40Z` — *before* both cited
  commits, so neither commit can have been what the process served.
- **Why:** a checkout's HEAD is not the serving build. This produced the PROCESS RULE: bind to what the running
  process serves, and the cited commit must predate process start.

## R-006 — "Gemini lane has 11+ concurrent with no ceiling"

- **Claimed:** untested headroom.
- **Replaced by:** **~4.** Pushing to 5–6 produced rate limits.
- **Why:** reported from a single observation, not a measured ceiling.

## R-007 — "DeepSeek can run 24 concurrent"

- **Claimed:** `MAX_CONCURRENT = 24` in the proxy config.
- **Replaced by:** **3** — one in-flight chat per account × 3 accounts. `MAX_CONCURRENT` is not the ceiling.
- **Why:** the account count is the ceiling; pacing is not the limit.

## R-008 — "OpenRouter is credit-bound"

- **Claimed:** credits were the constraint.
- **Replaced by:** **free tier, 1000 requests per DAY.** A daily allowance, not a concurrency or credit limit.
- **Why:** operator correction. Consequences: don't send long agentic cards to this lane, and its cap is about
  *budget*, so over-filling it burns the day rather than queueing.

## R-009 — "`origin/main` holds the register"

- **Claimed:** the register of record is `main`.
- **Replaced by:** **`main` is a stub** — 832 rows, all `NOT_TESTED`, **zero** `evidence_ref`. The real register is
  `origin/cert/local-main-b142cf8`: 790 rows, 579 PASS / 76 FAIL / 13 BLOCKED / 122 NOT_TESTED, 668 with refs.
- **Why:** measured on 2026-10-18. Any gate reading `main` reports everything outstanding forever.
