# B3-CERT t_674c5537 - 6-row evidence package (UI-FP-145/149/150/165/167/168)

Register of record: `main:certification/certification_matrix.json` @ `b142cf88d389e791160f691aac3d936852b99975`
(read via `git show b142cf88:...` ONLY; the working-tree copy was never used).

Live surface: `http://127.0.0.1:8031/live-copy` (HTTP 200, UI PID 8668, uvicorn `HL_Copy_App_SSOT:app`).
Live state dir (from `/api/global-controls`): `C:/Users/wigmore/trading_stack/hl-build3-testnet-cert/_archive/hl_stage2/hl_live_copy_audit_testnet`.
All captures READ-ONLY; no start/stop/order action; no register edit; no mocks.

## Route (proven, extended)

`scripts/ui_fp_probe_t674.py` - playwright.chromium **headless** (Python 3.11) renders the page, clicks the
`Reconciliation` and `WS Health` tabs, and captures the RENDERED table cell text (headers + rows) plus the
pill classes. Independent oracles: the served JSON API (`/api/live-ws-health`, `/api/live-audit-summary`) and
the on-disk state files. No import of `HL_Copy_App_SSOT.py`.

## Verdicts (6 rows)

| row | area | feature | prior | result recorded | basis |
|---|---|---|---|---|---|
| UI-FP-145 | UI | Reconciliation / Warnings: Action | FAIL | **PASS** | Action cell captured for 100/100 rendered rows; all bind to reconciliation.csv SEND_TERMINAL + served API |
| UI-FP-149 | UI | Reconciliation / Warnings: Wallet | FAIL | **PASS** | Wallet cell captured for 100/100 rows; 93/93 warning rows bind to a served leader_wallet; 0 placeholder |
| UI-FP-150 | UI | Reconciliation / Warnings: Intent | FAIL | **PASS** | Intent cell captured for 100/100 rows; 78 bind to served intent_id, 22/22 remainder bind to CSV intent_id |
| UI-FP-165 | UI | WS Health Detail: Current | FAIL | **FAIL** | Rendered `OFFLINE` x10 while same-capture API `stale=false` x10; UI key `current_status/effective_status/status` absent from payload and disk |
| UI-FP-167 | UI | WS Health Detail: Thread | FAIL | **FAIL** | Rendered `down` x10 while same-capture API `thread_alive=true`; UI key `thread_alive/worker_thread_alive` absent |
| UI-FP-168 | UI | WS Health Detail: Reconnect/min | FAIL | **FAIL** | Rendered `0.00` x10; UI key `reconnects_per_min` absent; only summary `total_reconnect_count` exists and is never read |

## Evidence files

- `UI_FP_145_149_150_165_167_168_t_674c5537.json` - the six row verdicts + hard facts + sha256
- `raw/ui_fp_probe_t674.json` - rendered-DOM capture + served-API slices + on-disk oracle
- `raw/crosscheck_t674.json` - cell-by-cell DOM vs API comparison
- `raw/disk_oracle_t674.json` - disk oracle against the RUNNING app's state_dir
- `raw/diag_t674.json` - unbound-intent-cell diagnosis + register row fields + source token counts
- `scripts/` - the harnesses that produced all of the above

## Key raw facts

- WS Health tab renders 10 rows; headers `WALLET, CURRENT, GRADE, THREAD, RECONNECT/MIN, PROCESSED, RAW MSG, ...`
- Reconciliation Warnings table renders 93 rows, Critical 7 rows (total 100 = the served `send_terminal_rows` window).
- Served `send_terminal_rows`: 100. Live `append_only/reconciliation.csv`: 25,438 data rows, 6,857 SEND_TERMINAL.
- Per-wallet keys in BOTH the served payload and the on-disk `live_ws_health.json`:
  `last_error, last_message_ms, stale, stale_ms` - none of the UI's lookup keys exist.
- `stale_ms`: DOM == same-capture API for 10/10 rows. DOM vs DISK differs 10/10 (two writers of one rolling file).

## Two instrument corrections worth carrying forward

1. **Wrong disk dir.** The first disk-oracle read hit the ARCHIVED repo copy
   (`<repo>/_archive/hl_stage2/hl_live_copy_audit_testnet`, dated 2026-10-14, 1 wallet). The RUNNING app uses the
   `trading_stack/hl-build3-testnet-cert` state_dir (10 wallets). Resolve the live state dir from
   `/api/global-controls` before reading any state file.
2. **Prior notes were a field-name matcher miss.** The previous verdicts (`interval/tags/links/search/export/import
   element not found`) searched tokens that are not the matrix field names. The real headers are
   `ACTION / WALLET / INTENT` and `CURRENT / THREAD / RECONNECT/MIN`; locate the field by its HEADER, not a guessed id.

## Negative tests

The three negative tests on 145/149/150 (source unavailable -> `n/a`/`Unavailable` not `0`; stale source flagged;
API error surfaced) were **NOT_EXERCISED**: inducing them requires mutating the read-only live surface. They are
reported as NOT_EXERCISED, never as PASS. Each row's positive-result PASS therefore depends on the negative tests
being accepted as out of scope for a read-only probe; if the certifier requires them, this package must be re-run
with a fault-injection fixture (a separate, non-live harness).

Committed on isolated branch `hermes/ui-fp-t_674c5537` (base `b142cf88`); the shared main checkout was not written to.
