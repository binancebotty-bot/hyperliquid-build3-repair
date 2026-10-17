# B3-CERT t_2b312d5c - UI-FP 6-row evidence package (012/013/014/017/025/029)

Register of record: `git show b142cf88:certification/certification_matrix.json` ONLY.
Matrix sha256 = 86b2237fe95f88ca9eb758fb42ddbdf3efdaef71e56f79a10e2d2635f44f341a

Route (PROVEN, read-only): playwright.chromium headless on Python 3.11 rendering
http://127.0.0.1:8031/live-copy (HTTP 200); independent oracle = served JSON API
(/api/live-copy-summary, /api/state, /api/ui-state) + on-disk snapshot. No engine import.
Never touched the Edge/CDP 9223 or the :8031 process.

## Verdicts

| row | feature | result | basis |
|---|---|---|---|
| UI-FP-012 | MASTER REAL ORDERS card | **FAIL** | status strip renders 8 cards (HEALTH, LEADER FEED, FOLLOWER ACCOUNT READ, WALLETS, LAST SEND, LAST FILL, LAST REJECT, LAST LATENCY WARNING); page-wide /MASTER REAL/i leaf scan = 0 hits; API has master_real_orders=OFF but it is NOT rendered |
| UI-FP-013 | Active/subscribed wallets | **PARTIAL** | WALLETS card "10 live / 10 followed" MATCHES API active=10/sub=10/live=10; but no discrete active_wallets/subscribed_wallets element; no negative-path proof |
| UI-FP-014 | Last send card | **PASS** | LAST SEND card live (probe4 DOM "BANANA pending_send" @1792196089946 vs API last_send status=pending_send @1792196088106); field+status match, sub-second advance skew |
| UI-FP-017 | Last latency warning card | **PASS** | LAST LATENCY WARNING card renders full SEND_LATENCY_WARN row; shape matches API exactly (severity/classification/wallet/coin/delay/largest_component) |
| UI-FP-025 | Account graph total PnL | **PASS** | SVG #lcEquityChart rendered (1.75MB); subtitle "ALL range - 151 portfolio pts, 47295 realized fills"; baseline-relative deltas ($100.9/-$942.x); API exchange_account_history 156 pts |
| UI-FP-029 | Selected wallet exposure graph | **FAIL** | exactly ONE svg page-wide (lcEquityChart); no per-wallet exposure graph; wallet-row click does not add a chart; API live_leader_performance[wallet].exposure_series IS present but not plotted |

## Evidence files
- UI_FP_012_029_t_2b312d5c.json - machine-readable package (rows + raw sha256)
- raw/ - probe4/3/2/rows captures + register matrix copy
- scripts/ - the row-specific probes that produced them

## Key raw facts
- Status strip card labels captured: 8 (list above); NO "MASTER REAL ORDERS" card present.
- Page-wide svg count = 1; ids = [lcEquityChart].
- Cross-process skew: DOM capture and API read are 2-4s apart on fields that advance
  every 1-3s (last_send/last_fill/last_latency_warning), so exact coin values can differ
  while the FIELD/STATUS/SHAPE match - recorded, not hidden.
