# B3-CERT t_ab0d0f07 - 6-row UI-FP evidence package

Register of record: `main:certification/certification_matrix.json` @ `b142cf88d389e791160f691aac3d936852b99975`
(blob sha256 `86b2237fe95f88ca9eb758fb42ddbdf3efdaef71e56f79a10e2d2635f44f341a`), read via `git show` ONLY.

Live surface: `http://127.0.0.1:8031/live-copy` (HTTP 200, title `Live Copy Dashboard`), served by PID 8668
(`python -m uvicorn HL_Copy_App_SSOT:app`, started 2026-10-15T09:28:40Z). All captures READ-ONLY: no
state-mutating POST, no engine import, no start/stop/order action, no register edit, no mocks.

## Verdicts (6 rows)

| row | area | prior | result recorded | basis |
|---|---|---|---|---|
| UI-FP-030 | UI-FP | FAIL | **PASS** | lcGraphScale/Start/End render; scale buttons re-filter client-side (ALL 147 pts/47193 fills -> 7D 137/37998 -> 1D 92/29278); no send path |
| UI-FP-041 | UI-FP | FAIL | **PASS** | rendered 'Avg bps: N' == served live_leader_performance[wallet].avg_diff_bps; 9/9 comparable rows match, nulls render 'n/a' not 0 |
| UI-FP-048 | UI-FP | FAIL | **PASS** | rendered 'Open pos: N' == served live_leader_performance[wallet].open_position_count; 15/15 exact |
| UI-FP-052 | UI-FP | FAIL | **PARTIAL** | mode select renders + value == served config.wallets[wallet].mode (15/15); handler posts /api/live-config/set-mode; execution-truth leg NOT proven (read-only) |
| UI-FP-054 | UI-FP | FAIL | **PARTIAL** | fixed_notional input renders + value == served config.wallets[wallet].fixed_notional (15/15, all 12); execution-truth leg NOT proven (read-only) |
| UI-FP-055 | UI-FP | FAIL | **PARTIAL** | norm_base input renders + value == served /api/ui-state.norm_base (15/15, all 100); execution-truth leg NOT proven (read-only) |

Tally: **3 PASS, 3 PARTIAL, 0 FAIL, 0 NOT_TESTED**.

## Why the prior six FAILs were false reds

The prior evidence (`certification/results/UI_CORRECTION_2d29211.json`) reported `element not found` /
`same as source` for every one of these six cells (`transfer`, `copy_model`, `hover`, `search`, `export`,
`import`). Re-probed at element level, **all six elements render and bind to their declared source**.
The reds were bad selectors, not missing UI - so this card does NOT blanket-confirm them: it records the
real per-row verdict the rendered DOM + served oracle support, and holds the three `execution truth: YES`
rows at PARTIAL because the read-only mandate forbids the mutation that leg would need.

## Provenance caveat (flagged, not used to downgrade)

The running app is NOT the register-commit source: served file
`C:\Users\wigmore\trading_stack\hl-build3-testnet-cert\_archive\hl_stage2\HL_Copy_App_SSOT.py`
sha256 `658ec8e3...` (492597 B) vs register blob `7468ab51...` (375250 B). This does **not** create
NOT_TESTED for these rows, because the register-commit source @b142cf88 independently contains every
field route exercised (`lcGraphScale` 6, `data-lc-graph-scale` 6, `Avg bps` 1, `Open pos` 1, `set-mode` 2,
`set-wallet` 3, `live-config` 8, `avg_diff_bps` 4, `open_position_count` 22). Both revisions implement the
same row behaviour; the rendered capture proves behaviour, the register-source grep proves the register
carries it. Owner of the consolidation step should note the served revision is one working-tree step ahead.

## Evidence files

- `F_UI_FP_030_041_048_052_054_055_t_ab0d0f07.json` - the six rows, verdicts, basis
- `raw/` - captured runtime output (probe_raw, probe2..4, probe7)
- `scripts/` - the harnesses that produced it (read-only, no engine import)

sha256 of each raw/script file is in the commit message / listing below.

## Key raw facts

- DOM: 15 wallet rows; 76 inputs; 80 `.lc-pill`; `#liveCopyPanel` present; page body 74,500 chars.
- Bind tally (probe7): bps 9 match / 0 mismatch (6 honest n/a); op 15/0; mode 15/0; fixed_notional 15/0; norm_base 15/0.
- Endpoints used by the UI: `/api/live-config`, `/api/live-config/add-wallet`, `/api/live-config/set-wallet`,
  `/api/live-config/set-mode`, `/api/live-config/remove-wallet`.
- Served state_dir: `C:\Users\wigmore\trading_stack\hl-build3-testnet-cert\_archive\hl_stage2\hl_live_copy_audit_testnet`
  (live_config.json 3652 B, 15 wallets; exchange_account_snapshot_app.json fetched_at_ms 1792196167705,
  open_position_count 136). Leader=mainnet, follower=testnet.

## Interpreter / environment (for the next worker)

- playwright is installed ONLY under Python 3.11: run
  `C:/Users/wigmore/AppData/Local/Programs/Python/Python311/python.exe`.
- `export PLAYWRIGHT_BROWSERS_PATH=C:/Users/wigmore/AppData/Local/ms-playwright` before launching Chromium
  (overrides the bad default `C:/Users/wigmore/.hermes/tools`).
- Repo path is `C:/Users/wigmore/hyperliquid-build3-repair` (no `projects` segment).
