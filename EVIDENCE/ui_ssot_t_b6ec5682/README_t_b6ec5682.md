# B3-CERT t_b6ec5682 — 6-row UI-SSOT evidence package

Register of record: `git show b142cf88:certification/certification_matrix.json` ONLY
(`b142cf88d389e791160f691aac3d936852b99975`). Working-tree copy never used.

Live surface: `http://127.0.0.1:8031` (server PID 8668, uvicorn `HL_Copy_App_SSOT:app`).
All captures READ-ONLY: no start/stop/order action, no register edit, no engine import,
no touch of the operator Edge / CDP 9223 / the :8031 process.

## Verdicts (6 rows)

| row | feature | prior | result recorded | basis |
|---|---|---|---|---|
| UI-SSOT-TOP-06 | top bar: Set | NOT_TESTED | **FAIL** | writes model-only (PASS) but NOT labelled as model; "model" absent from register top bar |
| UI-SSOT-TOP-07 | top bar: Current mode label | FAIL | **FAIL** | label is `Current:`/`Mode:`, not marked as app-model |
| UI-SSOT-TOP-09 | top bar: POLL badge | FAIL | **FAIL** | static `POLL` string in HTML_TEMPLATE, not model-derived, not labelled |
| UI-SSOT-TBL-25 | `/sort/{column}` | NOT_TESTED | **PASS** | endpoint + allowlist + persistence (api==disk) + DIFF flag on L/C mismatch |
| UI-SSOT-PAGE-01 | `/wallet/{wallet}` detail | FAIL | **PASS** | route + closed-trades/actions tables + 404 fail-closed; reset/snapshot safe (7/7) |
| UI-SSOT-PAGE-11 | `/api/live-config` | NOT_TESTED | **PASS** | endpoint consistent with on-disk config; fail-closed errors; banner present |

## CRITICAL PROVENANCE FINDING

The running `:8031` server does **NOT** serve the register build.

- Register (`hyperliquid-build3-repair @ b142cf88`): `_archive/hl_stage2/HL_Copy_App_SSOT.py`,
  git blob `04533ced547a6e8c1d31b8ce25b4b215889e4409`, sha256 `7468ab51…`, 6360 lines.
  It defines **NO `/live-copy` route** (0 hits). Its top bar (line 5181) reads `Mode:` / `Current: {mode}`.
- Live server serves a **different checkout**: `C:/Users/wigmore/trading_stack/hl-build3-testnet-cert`
  @ `b5e6d613de36e3020ac28ba2317e6571a5c37e9b`, SSOT sha256 `658ec8e3…`. Its top bar reads
  `Model mode:` / `Engine sizing:` and it DOES expose `/live-copy`, `/live-copy.json`, `/api/live-copy-summary`.
- The register matrix additionally pins `hyperliquid-build3-repair/HL_Copy_App_SSOT.py`
  sha `c0f9e508…`, which is **not a resolvable object** in the repo (`git cat-file` fatal).

Consequence: a DOM-only probe against `:8031` would certify a build that is not the register's
certified artefact. Verdicts here are therefore grounded on the **register source read via
`git show`**; the live DOM is cited only as a contrasting deployed build.

## Evidence files

- `UI_SSOT_TOP_06_07_09_t_b6ec5682.json` — rows TOP-06/07/09
- `UI_SSOT_TBL25_PAGE01_11_t_b6ec5682.json` — rows TBL-25, PAGE-01, PAGE-11
- `raw/probe.json` — rendered-DOM + API + on-disk oracle capture (playwright py3.11 headless)
- `raw/provenance.txt` — register-vs-live token/commit/sha divergence table
- `raw/endpoints_oracle.txt` — HTTP statuses + api-vs-disk oracle comparisons
- `raw/test_g4_ui_controls.txt` — register's own UI-controls test: TOTAL=7 FAILED=0
- `raw/wallet_page_live.txt` — live wallet-page DOM + 404 fail-closed proof
- `scripts/ui_ssot_probe.py` — the harness that produced raw/probe.json

## Key raw facts

- Register top bar (line 5181): `Mode:</span>`, `Current: {mode}`, static `<span class="live">POLL</span>`;
  the token `model` appears **nowhere** in the top bar (0 hits). Set form posts to `/api/ui-state`
  → `save_ui_state` → `atomic_write_json(ui_state.json)` (model-only, no engine truth).
- `/sort/{column}` (line 6181): allowlisted columns, fail-closed `BAD_SORT`, persists to
  `ui_state.json`. Live oracle: `/api/ui-state` ranking `{'column':'wallet','direction':'asc'}` ==
  on-disk `ui_state.json` ranking (match).
- L/C mismatch: `mismatch = left != right` → `LEAD_COPY_COUNT_MISMATCH` flag + `DIFF` badge (line ~5095).
- `/wallet/{wallet}` (line 6020): renders TRADE…HOLD closed-trades table + `Expected copy fills`
  table with an `ACTION` column; unknown wallet → 404 `Wallet not found` (fail closed).
- Contract banner: `render_home` (line 5057-5061) prepends `CONTRACT WARNING (n errors)` when
  `validate_render_contract` returns errors.
- `test_g4_ui_controls.py` (register): `B_RESET_SAFE_DOES_NOT_TOUCH_ENGINE_TRUTH_PASS`,
  `B_SNAPSHOT_GRANTS_NO_AUTHORITY_PASS`, TOTAL=7 FAILED=0.

Committed on isolated branch (no matrix edit). The shared main checkout was not written to.
