# Testnet run 4 evidence (2026-10-09)

Follower: testnet 0x7AE3...9205. Engine main @ 3c03099, started 17:59:16Z, restarted 18:59:16Z (PID 16176) with
`python HL_Live_Copy_Service_Core.py --ws --loop --interval 10 --poll-live --poll-copy`; sending disarmed 22:13:20Z.
- `state/`: copy of the engine state folder at 22:11Z (reconciliation.csv and order_intents.csv gzipped). No keys or env files.
- `exchange/`: testnet info API responses at ~22:15Z (openOrders, frontendOpenOrders, clearinghouseState,
  spotClearinghouseState, userFunding and userFillsByTime since 17:59Z, portfolio).
- `RUN4_FINDINGS.md`: findings (latency run-away, caps breached, unledgered exit-recovery fills, P&L, UI review).
Checked: neither signing key appears anywhere in these files.
