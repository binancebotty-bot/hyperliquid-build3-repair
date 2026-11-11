---
name: send-and-liquidity
description: Change the global send switch only under order and identify unsupported liquidity-filter controls.
---

# Sending and liquidity filter

Require a fresh signed order naming the run and the exact control change. `OFF` blocks sends; `CLOSE` blocks entries/adds while allowing closes; `ON` enables normal sending.

The running pair reads these controls from its state directory's `live_config.json`. The dashboard's `/api/global-controls` form does not submit `send_mode`, `min_24h_notional_usd`, or `liq_parity`; do not treat a successful form save as changing them.

## Liquidation parity

Set `global_controls.liq_parity` explicitly to `false` on testnet and `true` on mainnet. The Core gate is read at construction and defaults to `true`, so seed it correctly before start; a live file edit does not change the active gate. If the approved launcher uses a parity override, it must agree with the selected network. Do not dump environment values.

## Ordered live edits

For an explicitly ordered change to a running pair, make a timestamped backup of that run's `live_config.json`, edit a staged copy, validate the JSON and the single changed field, then atomically replace the file. Record the before/after SHA-256 and UTC time. Never edit another run's file or change any other controls in the same operation.

- **`send_mode`:** Core re-reads the file when its mtime changes. This supports a live change on an instance that started with sending enabled. An instance started `OFF` remains fail-closed and cannot be armed by a live edit; enabling it requires a separate fresh order and the approved start procedure. Verify the effective mode from engine-owned status after the next cycle.
- **Liquidity filter:** set `global_controls.min_24h_notional_usd`. Core re-reads this threshold from the same file for the next fill; absent or `0` means the filter is off. Verify the effective threshold/status and the resulting named skip rows after the next cycle. This is independent of `liq_parity`.
