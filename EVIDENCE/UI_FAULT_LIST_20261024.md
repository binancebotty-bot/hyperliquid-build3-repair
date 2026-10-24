# UI cell-by-cell fault list - HL Live Copy Command Centre

**Date:** 2026-10-24
**Author:** Hermes
**Read from:** `C:/tmp/v31_bf40a9d-clean-20261024/_archive/hl_stage2/HL_Copy_App_SSOT.py` (HEAD bf40a9d, clean tree, read-only) plus `run7/state_20261023` audit files.
**Live verification:** NOT POSSIBLE. `:8031` is not listening (engine down, run8 not created). Every cell is VERIFIED-BY-CODE, none VERIFIED-LIVE.

## How the page is built

`GET /live-copy` (line 7935) returns a shell embedding `render_live_copy_control_panel()` (line 6998). Values are filled by JS from `lcAudit`, from `GET /live-copy.json` -> `_live_audit_summary()` (7952). Global Controls form reads `GET /api/global-controls` (7962) and writes `POST /api/global-controls` (7973).

## Cell inventory

| # | Region | Cell (element id) | Source | State |
|---|---|---|---|---|
| 1 | Header pill | lcWalletCount | computed client-side | CODE |
| 2 | Header pill | lcModeCounts | live_top_status | CODE |
| 3 | Header pill | lcWsOverall | live_top_status.ws_status | CODE |
| 4 | Banner | lcBannerAcct | status_banner.account_value | CODE |
| 5 | Banner | lcBannerSending | master_real_orders_enabled | CODE |
| 6 | Banner | lcBannerHealth | status_banner.health | CODE |
| 7 | Banner | lcBannerPnl | status_banner.net_pnl_since_start | CODE |
| 8 | Banner | lcBannerOpen | status_banner.open_positions | CODE |
| 9 | Banner | lcBannerResting (hidden unless non-null) | status_banner.resting_orders | CODE |
| 10 | Detail | lcHealthTechBody | health.technical[] | CODE |
| 11 | Panel | lcTally (7 rows) | pnl_tally | CODE |
| 12 | Status strip | 8 statusCards + conditional ENGINE ALERT | live_top_status | CODE |
| 13 | Real Account | 5 cards in lcRealCards | exchange_account_snapshot + manual_live_summary + follower_account + pnl_tally | CODE |
| 14 | Graph | lcExchangePath/Fill, lcRealizedPath, lcDrawdownPath, lcYMax/YMid/YMin | exchange_account_snapshot series | CODE |
| 15 | Graph subtitle | lcGraphSubtitle | computed | CODE |
| 16 | Safety strip | lcRestartNote (hidden unless ws_restart_needed) | live_top_status | CODE |
| 17 | Popover | gcMaxTotal, gcMaxDir, gcMaxDailyLoss, gcMaxWallet, gcMaxOrder, gcMktPct, gcCloseAdv, gcAllowlist, gcBlocklist | GET/POST /api/global-controls | CODE |
| 18 | Popover | gcNetworks | networks | CODE |
| 19 | Popover | lcGcStatus | POST response | CODE |

All 19 cells: UNVERIFIED-LIVE.

## Faults

### F1 - Wallet cap hardcoded twice (MEDIUM, display-only lie)
Line 7004 ships `0 / 10`; line 7670 rewrites as `${tracked} / 10`. The denominator is a literal, not the configured limit. Raise or lower the cap and the header states a wrong capacity.

### F2 - "Live Exposure" shows a false $0.00 when unknown (MEDIUM, false-green)
In `renderCards()`: `const expVal=manual.manual_live_exposure_estimate||0;` then `'$'+Number(expVal)`. A missing key renders $0.00, indistinguishable from genuinely no exposure. Every sibling card uses `dash(why)` for unknown. Fix: `manual.manual_live_exposure_estimate != null ? moneyFmt(...) : dash('exposure estimate unavailable')`.

### F3 - Three Real Account cells put an HTML fragment in a value slot (LOW, fragile)
`unified`, `rpnl`, `exPos` are each either a number or a pre-built `<span class="lc-grey" title="...">-</span>`, interpolated into a template that also sets `class="value ..."`. Nothing breaks today, but the tooltip lives only on the inner span, and any future escaping would print the HTML as text. Prefer `{text, cls, title}` and render once.

### F4 - Global Controls save failure is uninformative (MEDIUM, operability)
`POST /api/global-controls` catches every exception and returns only `_live_config_error(type(exc).__name__)` (~7982). The operator sees HTTPError or KeyError with no field name and no reason. This is the only write path on the page; a type-only failure is exactly how a cap looks set but is not.

### F5 - The five ordered run8 caps are not visible as a set (MEDIUM, certification risk)
Ruling 6383199382(d) requires, once sends go ON: order 250 / wallet 400 / per-asset 300 / total 900 / daily loss 100. The popover lists five independent numbers with no expected value and no PASS/FAIL. `ops/testnet_launch_spec.json` still carries 0.0 (uncapped) with sends OFF. An auditor cannot tell from the screen whether the ordered caps are in force.

### F6 - Sending banner depends on strict === true (LOW, false-OFF risk)
`renderBanner()` uses `const armed = lcAudit.master_real_orders_enabled === true;`. If the backend ever serialises the flag as "ON", "true" or 1, the banner shows OFF while the engine is armed. It fails safe (can only under-report sending) but would mislead a certification read.

### F7 - Nothing on the page proves which build it is (HIGH, certification)
Confirmed by reading `/api/state`: the provenance fields (`engine_process_id`, `engine_alive`, `engine_build_sha`, `audit_dir`) are exposed on `/api/state`, NOT on `/live-copy`. The Command Centre cannot be used to prove the running SHA or PID. The `/api/state` work is the foundation; the render is still missing.

### F8 - Resting-orders cell invisible when null (LOW, ambiguity)
Line 7042 ships `hidden`, and `renderBanner()` only unhides when `b.resting_orders != null`. A null is indistinguishable from "no resting orders" - same class as F2 but hiding instead of falsifying.

## Could not verify, and why

- Any cell rendering the run8 state: `run8/state_20261024` does not exist; engine down.
- Any behaviour with sends ON: sends are OFF by ruling until run8 starts.
- Graph paths (cell 14) with live series: no live audit dir.
- F4 and F5 behaviourally: they are write paths; exercising them mutates the live config, which is Codex's alone.

## Owner split

- F1, F2, F3, F6, F8 - UI rendering only, no engine dependency. Safe to fix on a branch, review, re-pin. Not fixed here: the running checkout is read-only by RULE 1 of `ops/REPO_MAP.md`, and the UI file lives inside it.
- F4, F5 - need a decision on the failure payload and the expected-cap display. Controller ruling required.
- F7 - my lane (identity card on `hermes/ui-identity-card`), blocked only by the same read-only rule; the change must be staged on a branch against a clean checkout.
