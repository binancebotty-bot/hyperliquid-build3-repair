# UI Capture Harness — proof report

## What was built
`tools/ui_capture_harness.py` — a Playwright harness that captures the served HTML of the
live-copy dashboard, proves which process/SSOT file is serving the page, verifies the
metric key set, checks for text truncation, and (optionally) performs a live
mutation-control test on a config value.

## Runtime evidence

### 1. Live page, port 8031 (read-only)
- serving PID 26336, started 2026-10-19T08:34:35+01:00
- SSOT sha256 `b45ff9af...e7c2`, declared path matches the process cmdline
- served HTML sha256 `1c4a096a...c99f` (21851 bytes)
- all 22 header keys present, no truncated prefixes
- truncation: 1 cell clipped, 1 recovered from data-sort

### 2. Truncation recovery (fixed)
Wallet column rendered `0x7ae3b0…5e9205` with scrollWidth == clientWidth, so CSS-overflow
detection alone could not recover it. The full id `0x7ae3b08bb4e7b085c6db5d635b96bec9715e9205`
lives in `data-sort`; the harness now reads it.

**Bug found and fixed:** `Number('0x7ae3b0...')` parses a wallet address as a HEX literal
and silently produced `7.0157e+47`. Now only genuine decimal literals are converted.
Result: cells_clipped 1 / cells_recovered 1.

### 3. Mutation control (proves the capture observes served truth)
On an isolated instance (port 8033, own audit dir, `HL_LIVE_AUTO_SEND_ENABLED=0`):
- bump `fee_bps` 5.0 -> 12.0 -> diff key `input.fee_bps` -> restore -> residual keys []
- verdict PASS, bump_diff_count 1, restore_residual_count 0
- negative control: bumping `global_controls.max_order_notional_usd` produced ZERO diff
  (that control is not rendered on the root page) -> verdict FAIL, correctly reported

## Metric of interest
`pct_entries_ge10` — header `% ≥ $10 ▲`, value 0.0%, data-sort 0, full key verified.
