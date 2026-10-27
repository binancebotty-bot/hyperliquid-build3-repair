# Runtime + UI audit — 27 Oct 2026 19:49Z

Read-only. Nothing was started, stopped, clicked or written during the audit.

## Identity
| Item | Value | Evidence |
|---|---|---|
| Live engine | PID 54528, `HL_Live_Copy_Service_Core.py --ws --loop --interval 10 --poll-live --poll-copy`, build a1acc28, started 09:01:43Z | run19/state_20261027/core_start_record.json |
| Live UI | PID 40424, uvicorn `HL_Copy_App_SSOT:app` on 127.0.0.1:8031, started 09:01:49Z | ui_launch.log, netstat |
| State dir | trading_stack/hl-build3-testnet-cert-evidence/run19/state_20261027 | CURRENT_AUDIT_DIR |
| build4 :8767 | DEAD - no listener; PIDs 28420/28008/28340 absent; state frozen 9 Oct | curl :8767 = 000 |

## Send flags - ARMED
`send_mode:"ON"`, `auto_send_enabled:true`, `master_real_orders_enabled:true`, `effective_real_orders_enabled:true`, `send_block_reason:""` (live_config.json -> global_controls.send_mode). Leader mainnet / follower testnet.

## Caps and filter
max_total_live_exposure_usd 3000; max_asset_directional_exposure_usd 900; max_daily_loss_usd 100; max_wallet_exposure_usd 1200; max_order_notional_usd 250; marketable_bps 20; min_24h_notional_usd 3000; allow/blocklists empty; sizing $12/wallet. 19 configured / 16 active / 10 subscribed.

## Wallet roster
19 leaders: 10 LIVE, 6 CLO, 3 OFF (incl. placeholder 0xaaaaaaaa). Copy account 0x7ae3...9205 value $933.97. 15 positions ACCOUNT_LEVEL_ONLY / external-orphan-unowned.

## UI state
health.level = red: "Action needed: a close is failing - check the Reconciliation tab". hard_copy_active_red 990; missed_entry 1067; missed_add 1079; rejected_missing_terminal_state 11; close_reject_or_recovery_required 4; audit_write_failures 1. Reconciliation: 5 OWNED_LEDGER_UNSUPPORTED_BY_EXCHANGE, 14 EXTERNAL_FLAT_PENDING_RECONCILIATION, SHARED_SYMBOL_NET_DIFF -1107/+1373. Send warnings: insufficient margin asset=12/0/179.

## Graph and tiles
Graph current (630 points, 09:01-19:49:47Z). exchange_account_snapshot.updated_at 16:11:02Z (3.65 h old) while status "OK" and available true - Account value/PnL tiles stale, no age field exposed. model_portfolio {}, portfolio_history [], live_wallet_derived {} (empty by this build).

## Rate limiting
No literal HTTP 429 observable. Self-imposed budget: RATE_BUDGET_SKIP 70930, POLL_DEFERRED_RATE_BUDGET 21880, rate_budget_skipped_fill_fetches 7195. available_weight_per_min 150 vs total_weight_per_sweep 1296.

## Defects, ranked
1. Sending ON with 2461 ORDER_REJECTED vs 1539 fills; margin_used 894.6 of account_value 933.97 (96%), open_notional 2696.
2. Account truth 3.65 h stale published as OK; no age_seconds field.
3. RED integrity gate suppresses nothing while armed.
4. 15 ACCOUNT_LEVEL_ONLY positions, engine_can_close false, excluded from exposure accounting.
5. 17372 rows "no owned sleeve; leader close fill cannot open reverse position".
6. 16 active leaders vs max_wallets 10 -> 6 produce no feed, no warning.
7. Rate starvation: theoretical min cycle 518 s; drift recovery 3998/4044 failed; drift_unresolved 19250.
8. Orphan side labels contradict signed size (DOGE "NET LONG" with -1373).
9. WS staleness detector blind: 1.9 h old messages report stale:false.
10. False authority records: dead build4 PID files, watchdog asserts dead PID alive, launch_authority.json bound to 28420.
11. Config hygiene: placeholder wallet, 3 .bak configs in live state dir, hip3_fence_proof_unavailable 3199.

One-line fixes where obvious: (2) expose exchange_age_seconds and gate on it; (8) derive side from signed size; (9) stale when stale_ms > ws_data_stale_ms.
