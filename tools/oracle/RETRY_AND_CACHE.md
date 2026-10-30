# M3 oracle — paced retry and baseline-keyed fill cache

Branch `tools/oracle-429`, worktree off `8b45a4a`. Implements exactly the two remedies in
`docs/ORACLE_TRIAGE.md` ("The two remedies (described, not implemented)"). No engine import was added;
`hl_readonly.py` and `m3_oracle.py` remain stdlib-only and read-only (POST to `/info` only, no signing).

## 1. Paced retry with backoff (`hl_readonly.post`)

- HTTP 429 waits for the response's `Retry-After` header when it is present (clamped to 0.5–120 s).
- Otherwise exponential backoff from `BACKOFF_START_S = 0.5` doubling to `BACKOFF_CAP_S = 30.0` with
  ±20% jitter (`_jitter`), bounded to `POST_TRIES = 8` attempts. Transport errors and 5xx take the same path.
- Leaders are spaced apart in `m3_oracle.py` (`--leader-gap`, default `LEADER_GAP_S = 6.0` plus
  `LEADER_GAP_JITTER_S = 2.0` of jitter) so 14 page sequences are no longer fired back to back.
- Every leader entry in `meta.leader_fill_wallets` now records `attempts`, `last_status`,
  `rate_limited`, `pages_reused`. An unreadable leader's `missing_input` string gains an explicit class:
  `leader fills unreadable for 0x7717a7a2 [RATE_LIMITED, 8 attempt(s), last status 429]: …` versus
  `[HTTP_404…]` / `[TRANSPORT…]`. "Rate limited hard" is now distinguishable from "gone".

## 2. Per-leader fill cache

Pages are persisted under `tools/oracle/cache/leader_fills/<wallet>_<since_ms>.json`, one record per
completed page carrying its `cursor` (the `startTime` used) and `next_cursor`. A re-run replays the stored
pages and continues from the last `next_cursor`, so only the new tail is fetched. `--no-cache` disables it;
`--cache DIR` relocates it. Cache writes are atomic (`os.replace`), and each page is flushed as it lands so an
interrupted run keeps its progress. For a full walk this turns O(all pages) per run into O(1) requests per
leader once warm.

**Invalidation rule (one sentence):** a cache file is reused only when `FILL_CACHE_VERSION`, the wallet, and
`since_ms` all match exactly, so any change to the copy `baseline_ms` (or to the wallet/version key) discards
the file and the whole window is re-fetched from `baseline_ms + 1`.

## 3. Measured before/after (read-only re-runs, same audit and state inputs)

Comparable pair, both produced on this branch with the same inputs. "Before" is the pristine `8b45a4a`
behaviour (`git stash`-free copy of the unmodified oracle), "after" is this commit.

| run | file | UNRESOLVED | OK | LOST_OBLIGATION | rows whose cause names a fill-fetch 429 |
|---|---|---|---|---|---|
| before | `runs/prefix_before/m3_oracle_20261030T004231Z.json` | 340 | 16 | 55 | 13 |
| after | `runs/after/m3_oracle_20261030T005055Z.json` | 335 | 18 | 58 | 2 |

The 2 remaining "429" strings in the after run are not rate limits: they are the digits `429` inside coin
quantities (`42929.9`, `429362.0`) in `contradictory leader direction` causes. No fill fetch failed on 429 in
the after run.

### The leader that caused 261 of 371 baseline UNRESOLVED rows

`0x7717a7a245d9f950e586822b8c9b46863ed7bd7e`, in run `m3_oracle_20261029T224357Z`:
`pages: 0, fills: 0, error: 'HTTP 429 null'` — 261 rows forced UNRESOLVED by that one cause.

Same wallet, after the change: `pages: 11, fills: 21714, attempts: 11, last_status: 200,
rate_limited: false, error: null`.

**Confound, stated plainly.** That failure was intermittent, not deterministic. In the pre-change run taken
today (`runs/prefix_before/...004231Z`, unmodified code) the same wallet already read successfully. So the
change cannot be credited with recovering those 261 rows on this host today; the venue was not rate-limiting
that wallet at that moment. What the change guarantees is that when a 429 does arrive it is waited out with
Retry-After/backoff instead of five quick retries and abandonment, and the failure is labelled RATE_LIMITED
with an attempt count.

| | UNRESOLVED | LOST_OBLIGATION |
|---|---|---|
| `0x7717a7a2` rows, before (this branch, pre-change) | 226 | 35 |
| `0x7717a7a2` rows, after | 227 | 34 |

### Against the quoted 24

The `docs/ORACLE_TRIAGE.md` figure of 24 came from run `m3_oracle_20261029T224357Z`, where the one leader's
fills were unreadable and its 261 pairs carried no verdict. The comparable measurement above is **55 → 58
LOST_OBLIGATION (+3)**; against the quoted baseline **24 → 58 (+34)**. Both rises are partly venue movement
rather than purely code — the unmodified oracle also resolved many of those rows when re-run today. The honest
claim is narrower: **the 429 UNRESOLVED block is gone from the fill leg (13 rows before, 0 after), and the
remaining count is a floor for other reasons.** 335 rows remain UNRESOLVED, dominated by `contradictory
leader direction` (123) and `no follower fill on this pair` (208), neither of which is a rate-limit problem.

### Second (warm) run — cache hit

A second run immediately after (`runs/after_warm/m3_oracle_20261030T005707Z.json`) reused the cache:

| run | pages fetched | pages reused | elapsed | rate-limited wallets |
|---|---|---|---|---|
| cold (`runs/after/...005055Z`) | 96 | 0 | ~5 min | 1 (`0xf5d81a13`) |
| warm (`runs/after_warm/...005707Z`) | 14 | 95 | 147 s | 0 |

On a warm run `pages_fetched` is 14 = one tail poll per leader, not one full history. Warm counts differ from
cold (`LOST_OBLIGATION` 50, `PENDING` 7) because the live positions moved between runs; the comparison in
section 3 uses the cold run, which shares its wall-clock window with the before run.

## 4. Remaining work (not in scope here)

The residual 429s are on the **leader live-position** leg (`km: HTTP 429` on mainnet `read_positions`, 6
parallel workers), not the fill leg. That is a separate, smaller block (10 rows in the pre-change run, 0 in the
post-change run) and would need per-DEX pacing rather than a leader-level gap.

Also unchanged: the 123 `contradictory leader direction` rows and the 208 `no follower fill` rows are
data-quality inputs, not fetch failures. Any LOST_OBLIGATION count remains a floor until those are triaged.
