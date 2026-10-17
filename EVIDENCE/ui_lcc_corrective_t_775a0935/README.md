# UI-LCC CORRECTIVE - t_775a0935

Rows: UI-LCC-WTBL-10..14 + UI-LCC-DETAIL-01 (6 rows)
Register of record: b142cf88d389e791160f691aac3d936852b99975 (read-only; NO matrix edit)

## Route (clears reviewer defect 1)
Probed the LIVE rendered DOM at http://127.0.0.1:8031/live-copy directly in headless
Chromium (Playwright, py3.11). No synthetic ui-cert.local page, no captured-fixture
serving. The page made its own real fetch to /api/live-config, /api/live-ws-health,
/api/live-audit-summary, /api/global-controls (all HTTP 200) and rendered 15 wallet rows.

## Oracle (clears reviewer defect 2)
Independent recompute from engine-written on-disk files - manual_live_positions.json,
live_config.json, append_only/live_fills.csv, append_only/send_attempts.csv - by a script
that does NOT import HL_Copy_App_SSOT.py. Config truth: 15/15 mode, 15/15 copy_mode,
15/15 fixed_notional. Fees rule mirrors _replay_wallet_ledger_pnl (sum of fee column).

## Time-alignment (removes the earlier apparent staleness)
probe4.py freezes the on-disk engine files on the exact /api/live-audit-summary response
instant, so DOM/API/disk are compared at one time T. The earlier probes showed DOM stale vs a
later disk read purely because the engine appends fills continuously.

## Verdicts
- UI-LCC-WTBL-10 = NOT_TESTED - F/N render correctly, but the served surface has NO B
  (leader_equity_base) input (0/15 rows), and the negative test fails: ??10/??100 renders
  defaults rather than n/a. Matches the prior NOT_TESTED, now re-confirmed.
- UI-LCC-WTBL-11..14 = NOT_TESTED - Save/CLO/OFF/Archive buttons exist on all 15 rows and the
  served JS wires them to the real live endpoints, but verifying a write's ACTUAL effect
  requires POSTing to the live service, which is forbidden (read-only). Honest NOT_TESTED,
  never the withdrawn stub {ok:true} PASS.
- UI-LCC-DETAIL-01 = PASS - per-wallet correctness for 0x0104...c703a: rendered B-section
  shows 96 open positions == API list (96/96 coins); fees DOM 89.86 == API 89.8602 ==
  independent disk sum 89.8602; attribution ENGINE_LEDGER_SLEEVES_PARTIAL shown. The only disk
deltas (JTO, USELESS) are the live append race - the API shows the same deltas, so it is
  movement, not a render error.

## Live-surface binding finding (reported, not fixed - outside this card)
The live /live-copy surface is served by the hl-build3-testnet-cert lineage
(.../hl-build3-testnet-cert/_archive/hl_stage2/HL_Copy_App_SSOT.py, HEAD b5e6d61), NOT the
register blob 7468ab51... . b142cf88 has no /live-copy route; its liveCopyPanel is embedded in
the home render. The served rowPayload lacks leader_equity_base/max_diff_pct/daily_loss_limit
and renderWallets differs. Row verdicts are recorded against the LIVE surface as the task
requires, with this divergence flagged.

## Read-only
No POST to the live service. Register untouched. Shared main checkout not written. Isolated
branch hermes/ui-lcc-corrective-t_775a0935.
