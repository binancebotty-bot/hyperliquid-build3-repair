# CONTROL/REGRESSION evidence package - kanban t_b7f52cc1

Rows: CTRL-BIND, B4-I13, B4-I20, B4-I21, B4-I26, F-EXC-016

Register of record: `git show b142cf88:certification/certification_matrix.json` (main @ b142cf88).
The working-tree matrix was NOT used and was NOT edited.

## Verdict

| row | at register | this run |
|---|---|---|
| CTRL-BIND | NOT_TESTED | NOT_TESTED |
| B4-I13 | NOT_TESTED | NOT_TESTED |
| B4-I20 | NOT_TESTED | NOT_TESTED |
| B4-I21 | NOT_TESTED | NOT_TESTED |
| B4-I26 | NOT_TESTED | NOT_TESTED |
| F-EXC-016 | BLOCKED | BLOCKED |

No row changed. Each row's own `execution_proof` requires a live engine run (testnet or
recorded replay) or an oracle that does not exist at the register commit. All are named
below per row.

## Files

| file | what |
|---|---|
| `CONTROL_REGRESSION_t_b7f52cc1_b142cf88.json` | consolidated package (executed checks + per-row verdicts) |
| `CTRL_BIND_t_b7f52cc1_b142cf88.json` | CTRL-BIND row record |
| `B4_I13_t_b7f52cc1_b142cf88.json` | B4-I13 row record |
| `B4_I20_t_b7f52cc1_b142cf88.json` | B4-I20 row record |
| `B4_I21_t_b7f52cc1_b142cf88.json` | B4-I21 row record |
| `B4_I26_t_b7f52cc1_b142cf88.json` | B4-I26 row record |
| `F_EXC_016_t_b7f52cc1_b142cf88.json` | F-EXC-016 row record |
| `CONTROL_REGRESSION_harness_t_b7f52cc1_b142cf88.py` | executed probe (git objects + live HTTP) |
| `_runA_scrubbed.json` / `_runB_inherited.json` | two-run control outputs |

## Method / honesty notes

- Two-run control: runA with PYTHONPATH scrubbed, runB with PYTHONPATH inherited; both rc=0.
- Oracle independence: the harness reads git objects and the OS HTTP surface only. It does NOT
  import engine or UI code.
- No credentials loaded, no key value printed. No orders placed, cancelled or modified.
- Read-only: no controller wake was sent or consumed this run.

## What a PASS would still need (per row)

- **CTRL-BIND**: a live wake -> envelope on `origin/control-mailbox` -> correlated consumption
  record -> durable state transition. None exists for any new envelope (newest inbox is
  2026-10-09 seq71; newest outbox 2026-10-16 has no reply). AND OD-03 is unruled: three distinct
  controller UUIDs; the live CONTRACT (v2, ACTIVE) says `6ac8e179-...`, while CONTROL_STATE still
  carries `6ac6427b-...` and its dispute field names `6ac7a51f-...`.
- **B4-I13**: a testnet/replay run of the ENTRY/ADD min-notional path. OD-09 unruled (Build-4
  USD 30 + buffer 12 vs Core `HL_LIVE_MIN_NOTIONAL` default 10).
- **B4-I20 / B4-I21**: a testnet/replay entry order. OD-10 unruled (entry price bound). At the
  register commit `max_diff_pct` is absent from the Core (present only in the legacy module),
  and `PRICE_WAIT` / `ENTRY_PRICE_BOUND` do not appear at all - the rows name symbols that must be
  re-derived against the Core's actual mechanism before they can be certified.
- **B4-I26**: OD-11 unruled - the runtime independent oracle was deleted; the register commit has
  no file matching `oracle`, so the row's own requirement cannot be demonstrated.
- **F-EXC-016**: UI-visibility evidence. The live surface answers (HTTP 200, 87117 bytes) but the
  served document carries no truth-tier token (`AUTHORITATIVE_EXCHANGE` / `LOCAL_LEDGER` /
  `DISPLAY_ONLY` / `LEADER_SIGNAL`), so the row's requirement cannot be exercised. BLOCKED, and
  NOT a product failure.

## Provenance note (carried from AUTHORITY_INDEX)

The four pinned hashes `2dfbd57`, `2dfbd571`, `5bda57be`, `5de53fa` remain unresolvable against
this LOCAL repo. Per the controller correction they must be re-checked against
`origin/cert/local-main-b142cf8` after J15 publishes it.
