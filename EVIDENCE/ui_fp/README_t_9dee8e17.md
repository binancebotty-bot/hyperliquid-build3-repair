# B3-CERT t_9dee8e17 — UI-FP-119/120/133/137/139/140 (6 rows)

Register of record: `main:certification/certification_matrix.json` @ `b142cf88d389e791160f691aac3d936852b99975`
(read via `git show b142cf88:...` ONLY).

Surface: `http://127.0.0.1:8031/live-copy` (HTTP 200). All captures READ-ONLY; no start/stop/order;
no register edit; no mocks; no engine import.

## Route (the proven one)

playwright.chromium headless (Python 3.11, `PLAYWRIGHT_BROWSERS_PATH=C:/Users/wigmore/AppData/Local/ms-playwright`)
renders the live page, clicks each tab, and captures the RENDERED table headers + rows.
Independent oracle: `urllib` read of the served JSON API (`/api/live-audit-summary`) plus the
on-disk `append_only/*.csv`, recomputed without importing `HL_Copy_App_SSOT.py`.

## Verdicts (6 rows)

| row | feature | result | basis |
|---|---|---|---|
| UI-FP-119 | Execution Quality: Exchange ms | **PASS** | DOM header `EXCHANGE MS`; 300 rows; values 1078/1117/1045 ms; API field `exchange_call_ms` == CSV column |
| UI-FP-120 | Execution Quality: Error | **PASS** | DOM header `ERROR`; real reject text "Insufficient margin to place order. asset=140" + reject_category |
| UI-FP-133 | Order Intents/Audit: Real order result | **PASS** | DOM header `REAL ORDER RESULT`; values REAL_ORDER_FILLED/EXCHANGE_REJECTED/NO_SEND_ATTEMPT reproducible from intent_id→send_attempts.status join |
| UI-FP-137 | Recon/Actionable: Reject category | **PASS** | DOM header `REJECT CATEGORY`; Actionable Critical Items 17 rows + Warnings 83 rows; real categories INSUFFICIENT_MARGIN, LIQ_PARITY_BLOCK |
| UI-FP-139 | Recon/Actionable: Coin | **PASS** | DOM header `COIN`; populated DOGE/WLD/ZORA/STBL/NEAR |
| UI-FP-140 | Recon/Actionable: Wallet | **PASS** | DOM header `WALLET`; real 0x addresses |

## Provenance finding (material — read before merging)

The RUNNING UI is deployed from a commit NEWER than the register of record.

- Register commit `b142cf88`: Execution Quality table has **13** columns and **no** `Exchange ms`;
  Reconciliation panel is "Ledger vs Exchange" with **no** "Actionable Critical Items" table.
- LIVE DOM: Execution Quality table has **18** columns incl. `EXCHANGE MS`, `TERMINAL STATE`,
  `OPERATOR ACTION`, `REJECT CATEGORY`; Reconciliation panel has an "Actionable Critical Items"
  table incl. `REJECT CATEGORY`/`COIN`/`WALLET`.
- Live source commit: `5223ce2` (hermes/ui-delta-landing), re-run at `ecd6788`.

Consequence: UI-FP-119/137/139/140 certify the LIVE surface, which is **ahead of** the register
commit. Either certify against the deployed commit, or fold the live source into the register.
The register currently pins `b142cf88`, which lacks these fields.

## Evidence files

- `F_UI_FP_119_120_133_137_139_140_t_9dee8e17.json` — the 6 row verdicts
- `scripts/ui_fp_probe_119_140.py` — rendered-DOM capture (all 3 tabs)
- `scripts/ui_fp_probe_recon_137_139_140.py` — focused recon Actionable/Warnings capture
- `scripts/ui_fp_oracle_119_140.py` — independent API+CSV oracle
- `raw/*.json` — captured runtime output (sha256 in the verdict JSON)

Isolated branch `hermes/ui-fp-119-120-133-137-139-140-t_9dee8e17`; the shared main checkout was not written to.
