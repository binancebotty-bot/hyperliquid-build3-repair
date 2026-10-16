# HEALTH area cert report — rows HEALTH-001, HEALTH-005, INC-11

Register of record: `git show main:certification/certification_matrix.json`
(ref `main` = `b142cf88d389e791160f691aac3d936852b99975`). The working-tree matrix was NOT read
(AUTHORITY_INDEX.md §Register of record). Checkout `HEAD` = `31e599c5f58de686c9e74357079a85f03e23213a`
(`wt/t_6f66f7d1`); `main` is NOT an ancestor of this branch.

Oracle: the live HTTP surface `http://127.0.0.1:8031` (EVIDENCE/CERT_ENVIRONMENT.md) plus wall-clock
timestamps. Source reads are labelled `SRC:` and are never counted as runtime proof.

## Row verdicts

| row | register status (main) | this card |
|---|---|---|
| HEALTH-001 | NOT_TESTED | **FAIL** |
| HEALTH-005 | NOT_TESTED | NOT_TESTED |
| INC-11 | NOT_TESTED (APPLIES_PROPOSED, OD-20) | NOT_TESTED |

Harness: `HEALTH_harness_b142cf88d3.py` — 24 checks, 18 pass, 6 fail. Matrix NOT edited.

## HEALTH-001 — WS health visible — **FAIL** (genuine defect found)

Declared behaviour (register): *WS per-wallet state, staleness and reconnects visible; stale >
HL_LIVE_WS_STALE_MS (30000) flagged.*

Observed on the live surface, same run:

* `GET /api/live-ws-health` → 200. Per-wallet state IS published: 10 wallets, each with
  `last_error`, `last_message_ms`, `stale`, `stale_ms`. `ws_summary` carries `ws_status=WS_OK`,
  `worst_health_grade=OK`, `stale_count=0`, `total_reconnect_count=0`.
* Against the row's OWN declared 30000 ms bound the published flag is wrong: in one sample **4 of 10
  wallets exceeded 30000 ms of silence and 0 were flagged `stale:true`**, including
  `0x1b232b41b0e75550c59288b99874e4a8142fbe21` silent for **2,540,339 ms (~42 min) with `stale=false`**.
  A 45 s re-sample showed the silence still advancing (2,540,339 → 2,580,361 ms) and still unflagged, so
  this is persistent, not a transient.
* Threshold mismatch in the live core: `HL_Live_Copy_Service_Core.py` at HEAD uses
  `HL_LIVE_WS_WALLET_STALE_MS` default **120000** and `HL_LIVE_WS_SUBSCRIBED_STALE_MS` default **4 h** —
  not the declared 30000. The declared `LIVE_WS_STALE_MS = int(os.getenv("HL_LIVE_WS_STALE_MS", "30000"))`
  exists only in the legacy `HL_Live_Copy_Service.py` (main:5109 lines, sha `e2f04fa82695`).
* Per-wallet reconnect count is not exposed per wallet (only a global `ws_summary.total_reconnect_count`).

Also recorded (not the row's stated concern, but it is a provenance break this card must report):
the register pins the engine as `HL_Live_Copy_Service_Core.py (7,705-line, sha256 5bda57be)`, and that
object does **not resolve in this repo** (`git cat-file -t 5bda57be` → *Not a valid object name*). The
blob at `main:` is `b171ec8fef01`/8042 lines; at `HEAD:` it is `c5a40384e9a3`/13026 lines.

**Owning lane — outside this repo.** The live state dir is
`C:/Users/wigmore/trading_stack/hl-build3-testnet-cert/_archive/hl_stage2` (reported by
`/api/global-controls`), which is a different tree from `hyperliquid-build3-repair`. Per the lane
boundary rule this card does not fix, edit, or card that tree — it reports the defect and the exact
first failed edge (`stale > 30000` never fires because the runtime threshold is 120000).

## HEALTH-005 — Diagnostics never block — NOT_TESTED

Declared proof is an *induced* condition (WS drop / stale truth / API error) → engine state → UI
indicator within a stated latency, with the fault's wall-clock as oracle. No induced fault and no
engine-under-test are available to this card, so it cannot be non-vacuously tested. Named missing
surfaces: an engine-under-test whose WS/stale/error state may be induced without touching the live
lane, and a rendered-DOM oracle.

Source-read context only (NOT counted as proof): `_model_cache_snapshot_nonblocking()` acquires
`_MODEL_BUILD_LOCK` with `blocking=False`; `/api/live-audit-summary` is documented read-only with a 2 s
cache. Measured diagnostic cost: `/api/live-audit-summary` → 200 in 7.02 s (`build_seconds=6.86`) — a
statement about the diagnostic, not about engine execution.

## INC-11 — Engine death is visible — NOT_TESTED

Proving "status cards never show OK while no engine process exists" requires withholding/stopping the
engine and reading the rendered card. The live engine may not be killed (process-hygiene hard stops),
there is no engine-under-test, and no rendered-DOM oracle is available to this card.

Source-read context only: `_build_health_summary()` sets red *"Stopped: the engine is not running (no
engine status found)"* on an empty service state and red *"the engine has not reported for N min"* past
`ENGINE_STALE_SEC`, and publishes `engine_heartbeat_ms`. The row is APPLIES_PROPOSED with open decision
OD-20 (at-a-glance system health), so its applicability is not settled and even a PASS could not be
recorded unilaterally.

## Discipline notes

* Register status was read from the committed object, and the ref is quoted above.
* No widened accept sets, no mocks, no substitution: rows whose proof needs an induced fault were left
  NOT_TESTED with the missing surface NAMED.
* `certification_matrix.json` and `apply_verified_results.py` were NOT edited.
