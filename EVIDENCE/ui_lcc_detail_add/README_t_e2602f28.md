# UI-LCC certification evidence — t_e2602f28

Re-proof of **six** certification-matrix rows against the **live** Hyperliquid
copy-trading surface (`http://127.0.0.1:8031/live-copy`) using the proven
read-only DOM route (`36d1c52`). This run supersedes the prior NOP attempt on
branch `hermes/ui-lcc-detail02-04-add06-07-10` (tip `b21e75e`), which TCP-probed
the wrong port (8000, timed out) and wrote `NOT_TESTED` with no DOM/API capture.

* Register of record: `git show b142cf88:certification/certification_matrix.json`
  (`b142cf88d389e791160f691aac3d936852b99975` == `main`).
* Register blob SHA-256: `86b2237fe9f88ca9eb758fb42ddbdf3efdaef71e56f79a10e2d2635f44f341a`
* Engine SHA-256 (register truth used as the rendering source, read-only reference):
  `7468ab5188750617b090b56c3e719d73e91f5b4241f4782382ccac1a22989276`
* Tested at (UTC): `2026-10-17T01:12:49.690384+00:00`
* Branch: `hermes/ui-lcc-detail02-04-add06-07-10-t_e2602f28` (from `b142cf88`)
* Matrix was **NOT edited** (scoped NOP-style re-proof); register rows remain `NOT_TESTED`.

## Route (read-only, identical provenance to `36d1c52`)

playwright Chromium (headless, Python 3.11) renders
`http://127.0.0.1:8031/live-copy`. The independent oracle is:

1. `urllib` served JSON from the live surface: `/api/live-copy-summary`,
   `/api/live-config`, `/api/live-ws-health`.
2. On-disk `exchange_account_snapshot_app.json` (app-owned snapshot).

Constraints honoured: **no** `:8031` start/stop, **no** engine import, **no**
import of `HL_Copy_App_SSOT.py` (independence preserved), **no** UI-control
interaction (no clicks), **no** API writes (no POST), **no** touch of the
operator Edge/Chrome/CDP 9223. Python toolchain:
`C:/Users/wigmore/AppData/Local/Programs/Python/Python311/python.exe` with
`PLAYWRIGHT_BROWSERS_PATH=C:/Users/wigmore/AppData/Local/ms-playwright`.

## Two-run control (instrument does not alter findings)

Per `EVIDENCE_DISCIPLINE`/`evidence-trace-investigation`: run twice — run 1
normal env, run 2 scrubbed (`env -u PYTHONPATH -u PYTHONHOME -u PYTHONSTARTUP`)
— to prove no same-named namespace package (e.g. `tools/`) shadows the
instrument.

| check            | run 1 (normal)                         | run 2 (scrubbed PYTHON*)              |
|------------------|----------------------------------------|----------------------------------------|
| route            | ROUTE_AVAILABLE                        | ROUTE_AVAILABLE                        |
| http             | 200                                    | 200                                    |
| `#liveCopyPanel` | present (18,937 elements)              | present (18,971 elements)              |
| keyword-true set | 23 keywords (see rows below)           | 23 keywords — IDENTICAL                |
| served snap age  | 9,944 ms (fresh)                       | 13,067 ms (fresh)                      |
| on-disk oracle   | 44,463,999 ms (~12.4 h, stale)          | 44,661,462 ms (~12.4 h, stale)         |

The stable booleans (route / http / panel / keyword-true set / freshness
class) are **identical** across both runs. The only differences are live-surface
counters (element count 18,937 vs 18,971; open position count 409 vs 414;
served-snapshot age 4s vs 13s) — these change because the surface is a *live*
trading panel updating between the two runs (seconds apart), not because the
instrument is contaminated. **Verdict: INSTRUMENT_CLEAN.**

## Captured evidence (this commit)

* `scripts/ui_lcc_detail_add_probe.py` — canonical read-only probe (reproducible).
* `scripts/emit_results.py` — emits the results JSON from the raw capture
  (programmatic; committed verdicts cite the exact captured values).
* `raw/ui_lcc_detail_add_probe.json` — full raw capture from run 2 (scrubbed),
  51,701 bytes, SHA-256 `1c835ee51696f764093bc519baa14b8c2d08ca2c67bbe74cc02c5367e5422bd7`.
* `results/ui_lcc_detail_add_results.json` — structured 6-row verdicts.
* `README_t_e2602f28.md` — this file.

## DOM / API / oracle facts (from the capture)

* Landing renders `#liveCopyPanel` and the wallet-TABLE summary:
  `OPEN POSITIONS 131`, per-wallet coin position list
  (e.g. `shared 0G  shared AAO...  shared AAVE...`), per-wallet
  LEAD<->COPY DIFF + avg/worst bps, `Execution` / `Last Fill` / `Last latency
  warning` (`severity=CRITICAL delay_ms=6947`), a status banner, and an
  `Add wallet` button.
* Status banner: account value **583.35 USDC**, follower network **testnet**,
  sending **OFF**, live wallets **10**, health **RED**
  ("Action needed: a close is failing").
* Served `/api/live-copy-summary` is **FRESH** (HTTP 200, updated
  `2026-10-17T01:12:58Z`, ~13 s old): `tracked_wallet_count=15`,
  `owned_copy_positions_count=414` with `coin/side/signed_size/avg_entry_px/mark_px`
  per `leader_wallet`; clearinghouse `account_value=553.10`.
* Served `/api/live-config` is **FRESH** (HTTP 200): 15 wallets,
  `auto_send_enabled=false` (wallets disabled), `global_controls` present
  (`max_exposure_usd`, `symbol_blocklist=[HYPE,PENGU,RESOLV]`).
* `/api/live-ws-health` is **FRESH** (HTTP 200): wallets `stale=False`.
* **Independent on-disk oracle is STALE**:
  `_archive/hl_stage2/hl_live_copy_audit_testnet/exchange_account_snapshot_app.json`
  — `updated_at=2026-10-16T12:48:43`, age **44,661,462 ms (~12.4 h)**,
  SHA-256 `60dbbe31...`. Cannot establish same-time equality with the landing.
* On-disk `live_config.json` is a **stale 13-day fixture**
  (`mtime=2026-10-14T10:34`, SHA-256 `c4b5c7c8...`, wallet `0xdddddddddddddddddddddddddddddddddddddddddddd`)
  — it is NOT the live engine config (the live config is served fresh via
  `/api/live-config` with 15 real wallets; `WALLES_ENABLED=0` while OFF).

### DOM keyword truth table

True on the landing (summary-level render): `Open Positions`, `Add wallet`,
`Detail`, `Coin`, `Side`, `Size`, `Entry`, `Mark`, `Exposure`, `Unrealized`,
`PnL`, `Live`, `Action needed`, `Reconciliation`, `WALLET`, `LIVE`, `CLOSE`,
`OFF`, `LEAD`, `Execution`, `Last Fill`, `Latency`, `Technical detail` (23).

**Absent from the landing** (these live in the per-wallet DETAIL modal /
add-wallet modal, which require a click): `Lead vs Copy`, `Friction`,
`Execution Audit`, `Leader equity`, `Max diff`, `Submit`, `uPnL`, plus the
error/edge terms `Stale`, `Unavailable`, `Error`.

## Verdicts (6 rows)

All six remain `NOT_TESTED` under this route. None were fabricated as PASS;
the live surface was not mutated. Each row below names the **exact** route that
would convert it to a real verdict.

| Row | Subject | Result | Why NOT_TESTED (exact) |
|-----|---------|--------|------------------------|
| UI-LCC-DETAIL-02 | B Open Positions (Coin/Side/Size/Entry/Mark/uPnL/Exposure/Exchange match) per wallet | NOT_TESTED | Landing renders only the wallet-table open-positions SUMMARY (`OPEN POSITIONS 131`, coin list, Exposure, Last Fill). The per-wallet DETAIL B=Open Positions table is opened by clicking a wallet row; `uPnL` is ABSENT from the landing, so the full detail table is not rendered. Served `owned_copy_positions` lacks uPnL/Exchange-match (`unrealized_pnl=None`, `position_value=None`) and is the engine copy-ledger, not an independent exchange oracle; on-disk oracle ~12.4 h stale. |
| UI-LCC-DETAIL-03 | C Lead vs Copy / Friction per wallet | NOT_TESTED | Landing renders only aggregate LEAD<->COPY DIFF + avg/worst bps; the per-wallet DETAIL C-section (`Lead vs Copy`/`Friction`) is in the modal behind a click, and both keywords are ABSENT from the landing. Independent oracle stale. |
| UI-LCC-DETAIL-04 | D Execution Audit per wallet | NOT_TESTED | Landing renders only summary `Execution`/`Last Fill`/`Last rejection`/`Last latency` aggregates; the per-wallet DETAIL D-section (`Execution Audit`) is in the modal behind a click, and the keyword is ABSENT from the landing. Independent oracle stale. |
| UI-LCC-ADD-06 | Add-wallet modal: Leader equity base | NOT_TESTED | `Add wallet` button only; `Leader equity` ABSENT. Per register UI source @ `b142cf88` the leader_equity_base input is `type=hidden` (source line 5780). Persistence to `live_config.json` requires POST `/api/live-config/add-wallet` (mutation, forbidden). On-disk `live_config.json` is a 13-day stale fixture (0xdddddd placeholder), not the live config. |
| UI-LCC-ADD-07 | Add-wallet modal: Max diff % | NOT_TESTED | `Add wallet` button only; `Max diff` ABSENT. Opening the modal + persisting requires POST `/api/live-config/add-wallet` (mutation, forbidden). |
| UI-LCC-ADD-10 | Add-wallet modal: Submit add-wallet | NOT_TESTED | `Submit` ABSENT. Submit == POST `/api/live-config/add-wallet` (mutation), forbidden by the fully-READ-ONLY route, the `CERT_ENVIRONMENT` (no served-config write), `OD-07`/`OD-10`, and wallets disabled (`auto_send_enabled=false`, `WALLES_ENABLED=0`). |

## Exact missing routes (to advance the NOT_TESTED rows)

* **DETAIL-02 / -03 / -04:** the certified **read-only detail-capture harness**
  proven for the sibling DETAIL-01 row (`t_0ff26004`: wallet-row click -> DETAIL
  sections A-E -> matched `Open Positions` count to served
  `current_open_positions`). That route renders the same `b142cf88` engine
  truth but reaches the per-wallet modal cells and matches them field-for-field
  to the served (fresh) API. It is **not** the `36d1c52` landing-render route
  this task specifies, so it is named here rather than executed. A fresh
  independent per-wallet exchange position/fill/attribution oracle is also
  required (the on-disk snapshot is ~12.4 h stale).
* **ADD-06 / -07 / -10:** a sanctioned (non-mutating-to-live) **write-wire
  capture** — intercept `POST /api/live-config/add-wallet` via
  `page.route`, replay captured payloads, and verify (a) field ->
  `live_config.json` persistence and (b) invalid-input -> visible error. This
  is forbidden under the current fully-READ-ONLY contract, `OD-07`/`OD-10`, and
  `wallets disabled`; it needs explicit authorisation before the write leg is
  attempted. The on-disk `live_config.json` fixture must first be replaced with
  the live served config (15 wallets) so persistence can be asserted at all.

## Negative-test legs (register-defined) — NOT EXECUTED

Register `negative_tests` for these rows: `["source unavailable shows n/a/Unavailable not 0", "stale source flagged", "API error surfaced"]`. The landing-render route has no read-only way to trigger an unavailable/stale/API-error state (it would require fault injection / control interaction / mutation). These legs are therefore `NOT EXECUTED`, recorded as part of each row's verdict (not hidden).

## Notes / non-negotiables observed

* No PASS was self-reported for any row.
* The live surface was not started, stopped, written, clicked, or otherwise
  mutated. The operator Edge/Chrome/CDP 9223 was never touched.
* No `HL_Copy_App_SSOT.py` import; the independent oracle is served JSON +
  on-disk snapshot only.
* `python3.14` (terminal default) vs `python3.11` mismatch: the engine/SDK is
  py3.11-only — this probe deliberately pins `C:/Users/wigmore/AppData/Local/
  Programs/Python/Python311/python.exe` for the same reason the Build-3 runtime
  does (Hermes shell python lacks the SDK / playwright pin).
* The two prior branches for these six rows (`hermes/ui-lcc-detail02-04-add06-07-10`
  @ `b21e75e`) are a documented NOP and are **not** referenced as evidence.
