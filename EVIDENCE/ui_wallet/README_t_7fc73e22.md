# B3-CERT t_7fc73e22 — UI-WALLET/LCC 6-row evidence package

Register of record: `main:certification/certification_matrix.json` @
`b142cf88d389e791160f691aac3d936852b99975` (read via `git show b142cf88:...` ONLY;
the working-tree copy was never used).

UI source certified against: `_archive/hl_stage2/HL_Copy_App_SSOT.py` @ the register
commit, sha256 `7468ab5188750617b090b56c3e719d73e91f5b4241f4782382ccac1a22989276`
(375,250 bytes).

Live surface (READ-ONLY, untouched): `http://127.0.0.1:8031/live-copy` HTTP 200.
No start/stop/order action, no mocks, no served-config write, no Edge/Chrome/CDP-9223
touch, no edit to `certification_matrix.json` or `apply_verified_results.py`.

## Verdicts

| row | area | applicability | result | basis |
|---|---|---|---|---|
| UI-WALLET-002 | WALLET | OPEN_DECISION (OD-13) | **NOT_TESTED** | archive control + archive/restore exist; no tombstone concept exists |
| UI-WALLET-006 | WALLET | OPEN_DECISION (OD-02) | **NOT_TESTED** | copy_mode persists; no FIXED-MODE HOLD gate and no in-UI OD-02 disclosure |
| UI-WALLET-008 | WALLET | OPEN_DECISION (OD-02) | **NOT_TESTED** | `fixed_notional >= 0.01` clamp exists in source; semantics depend on OD-02 |
| UI-WALLET-014 | WALLET | OPEN_DECISION (OD-05) | **NOT_TESTED** | both mode writers exist; NO reconciliation guard and NO effective-mode display |
| UI-WALLET-015 | WALLET | OPEN_DECISION (OD-13) | **NOT_TESTED** | purge exists and removes the wallet unconditionally; no exposure-ownership guard |
| UI-LCC-CARD-02 | UI | APPLIES | **PARTIAL** | Unrealized PnL value leg PASS; stale-flag leg FAIL; Live-Exposure-truth leg FAIL; API-error leg NOT_TESTED |

The five WALLET rows carry `applicability=OPEN_DECISION` at the register, which the
register itself defines as *cannot be certified until ruled*. They were still probed:
every check that does not depend on the unruled decision was executed and is recorded,
so the ruling has the facts in front of it.

## Proven route used (copied, not rediscovered)

`EVIDENCE/ui_fp/README_t_d925c3dd.md` + `scripts/ui_fp_probe.py` @ `36d1c52`:
render the page in a NEW headless Chromium (playwright on **Python 3.11**) and cross-read
the truth with `urllib` from the served JSON API and the on-disk engine artefacts.
`HL_Copy_App_SSOT.py` is **never imported** (independence rule).

Two harness facts worth carrying forward:

1. `PLAYWRIGHT_BROWSERS_PATH=C:\Users\wigmore\.hermes\tools` points at a browser dir whose
   `chrome-headless-shell.exe` is MISSING. Launch fails until the variable is unset for the
   probe process (`unset PLAYWRIGHT_BROWSERS_PATH`), after which the real install under
   `%LOCALAPPDATA%\ms-playwright\chromium_headless_shell-1208` is used. The prior card's
   raw capture was taken with the variable still set and so has no DOM.
2. The :8031 service is **NOT running the register-commit build**. Its Real Account strip
   renders the labels `OPEN POSITIONS P&L (UNREALISED)` / `LIVE EXPOSURE` /
   `PORTFOLIO VALUE (TESTNET)`, none of which occur in the register blob (`OPEN POSITIONS
   P&L (UNREALISED)` = 0, `UNREALISED` = 0). Rendering the live page would therefore have
   certified a stale artifact. The probe renders the **certified renderer** (`renderCards`
   and its helpers, extracted verbatim from the register blob and executed in a real
   browser) fed by the **live served payload**.

## Evidence files

- `UI_WALLET_002_006_008_014_015_t_7fc73e22.json` — the five WALLET rows
- `UI_LCC_CARD_02_t_7fc73e22.json` — UI-LCC-CARD-02, with each executed check and its verdict
- `raw/ui_wallet_probe.json`, `raw/ui_lcc_card02_probe.json` — captures (served-API bodies
  replaced by sha256 + the fields the verdicts rest on; full 14 MB captures archived off-repo
  at `~/.hermes/cache/scratch/*.full.json`)
- `scripts/` — the harnesses that produced the captures, plus the two emitters

## Key raw facts

- UI-LCC-CARD-02, rendered DOM of the certified renderer on the live payload:
  `Unrealized PnL = $0.66` (`lc-pos`); independent oracle `exchange_account_snapshot` from
  `GET /api/live-audit-summary` gives `account_address 0x7ae3b08bb4e7b085c6db5d635b96bec9715e9205`
  (= MASTER), `available=true`, `unrealized_pnl=0.659395`,
  `unrealized_pnl_source=sum(assetPositions.position.unrealizedPnl)`,
  `updated_at 2026-10-16T23:12:20Z`; `$0.66 == round(0.659395, 2)`; capture age 9,665 ms.
- Negative leg: the same certified renderer with `available=false` / `unrealized_pnl=null`
  renders `Unrealized PnL = n/a` and `Portfolio Value = Unavailable` (not `0`).
- Live Exposure leg: label is plain `Live Exposure`, value `$9,390.04`, driven by
  `manual_live_summary.manual_live_exposure_estimate = 9390.043448`; no `estimated`/`manual`
  text anywhere in the strip.
- Source census @ register commit: `tombstone` 0, `effective_mode` 0, `OD-02` 0, `OD-05` 0,
  `OD-13` 0, `FIXED-MODE HOLD` 0, `contradict` 0; `/api/set-wallet-mode` 1,
  `/api/set-all-modes` 1, `/api/live-config/set-mode` 3, `/api/admin/purge-wallet` 2.
- `purge_wallet_everywhere()` guards only `CANNOT_PURGE_USER_WALLET`, then unconditionally
  removes the wallet from `ui_state.json`, `wallet_gate.json`, `live_config.json`,
  engine truth, baselines, CSVs and derived files — no exposure lookup in the body.
- Live divergence now visible: `GET /api/state` reports `send_mode=OFF` while
  `GET /api/live-config` reports every wallet `mode=LIVE`.
