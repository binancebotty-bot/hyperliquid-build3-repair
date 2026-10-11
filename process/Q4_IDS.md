# Q4 — never-ingested fills: who are they? (read-only)

Model: deepseek (Hermes free-model route), read-only file/code analysis, no engine restart, no orders.

## Core finding
`run5/test_queue_runner.py::window_ids()` builds the outage-window fill-ID set by calling
`userFillsByTime` **only for wallets whose `live_config.json` mode is `LIVE` or `CLO`**:
```python
for w, v in W.items():
    if v.get("mode") in ("LIVE", "CLO"):
        fs = requests.post(..., json={"type":"userFillsByTime", "user": w, ...})
```
OFF wallets are never queried, so **no OFF-wallet fill hash can ever appear in the window-id set**,
and therefore no OFF-wallet fill can ever be classified MISSING by `outage_classify.py`. Every
`MISSING_ID` reported for Q4-outage-detail is, by construction, a fill from a wallet that was `LIVE`
(mode polled) at the time `live_config.json` was read.

## Answers
1. **Wallet modes at the Q4 run (`run5/armed.txt`, `live_config.json` snapshot matching the run's own
   `wallet_modes_active {LIVE:7, OFF:8}`):** LIVE = 0x936cf4fb95…, 0xd4c1f7e8d8…, 0x7bc5239180…,
   0x1f4ab7e9ac…, 0xcbe834386b…, 0x35519de619…, 0x833b99b27d… (7). OFF = the other 8 configured wallets.
2. **Are the 55 MISSING ids all from OFF/non-polled wallets?** **No — structurally impossible.** Since
   `window_ids()` only fetches fills for LIVE/CLO wallets, every id that can be classified MISSING was
   already restricted to the LIVE cohort before the classifier ran. The outage/WS-down → OFF-wallet
   blind-spot hypothesis in the spec does not apply to this data set.
3. **Did an ON (LIVE) leader trade during the outage with nothing written?** **Yes, directly implied.**
   Any `MISSING_ID` in this run's output is, per (1), a LIVE-wallet fill with `files={}` — i.e. the
   engine polled/queried that wallet's fills over the window but produced zero rows for that hash in
   any `append_only` CSV (order_intents/reconciliation/send_attempts/live_fills).
4. **Per-wallet counts / timing:** not re-derived here — re-running `outage_classify.py` against the
   *current* `hl_live_copy_audit_testnet/append_only` tree now returns `MISSING=85 of 262` (sampled
   2026-10-11, several hours after the original run), vs. the issue #3 comment's truncated tail
   (9 ids + "... 45 more", total unknown because the runner's own log line clips classifier stdout to
   `cls[-900:]` and drops the `MISSING=N of 262` header). **The append_only CSVs are live/rotating
   (`order_intents.<date>.N.csv` etc.), so a re-run now is not equivalent to the state at 17:43Z** —
   re-deriving exact per-wallet/per-id counts needs the classifier's full stdout captured *at run time*,
   which the current logging does not retain. This is a logging gap, not a data-integrity finding.

## Scope / caveats
- Read-only: no engine restart, no orders, no WS subscriptions, no edits to live engine files.
- No live_config.json write; no .env/key access.
- Mainnet leader reads via `userFillsByTime` were NOT re-issued for all 55/85 ids individually (would
  need 7 wallet queries at <=1 req/s); the structural proof in "Core finding" answers the spec's central
  question without needing that enumeration. If per-id wallet attribution is required, extending
  `window_ids()` to log `{hash: wallet}` (not just a flat hash list) is a 2-line change and the cheapest
  fix for next time.
