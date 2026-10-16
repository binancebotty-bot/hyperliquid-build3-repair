# B3-CERT t_43c88862 — UI-LCC six-row evidence

Register of record: `main:certification/certification_matrix.json` at `b142cf88d389e791160f691aac3d936852b99975` only. Register blob SHA-256: `86b2237fe95f88ca9eb758fb42ddbdf3efdaef71e56f79a10e2d2635f44f341a`.

Probe: prescribed `EVIDENCE/ui_fp/scripts/ui_fp_probe.py` from `36d1c52`, executed read-only under Python 3.11 with `PLAYWRIGHT_BROWSERS_PATH=C:/Users/wigmore/AppData/Local/ms-playwright`. New headless Chromium 145.0.7632.6 rendered `http://127.0.0.1:8031/live-copy` HTTP 200; `#liveCopyPanel` present, 17,741 DOM elements. Served `/api/live-copy-summary` returned HTTP 200 and `/api/live-ws-health` returned HTTP 200 (`WS_OK`). Raw complete probe output: `ui_lcc_probe.json`. No app/engine imports, UI control interaction, service/process changes, or register edits.

## Row results

| Row | Result | Evidence / limitation |
|---|---|---|
| UI-LCC-CARD-03 | NOT_TESTED | Rendered card shows Closed P&L (realised) −$533.04. Served API responds, but independent app snapshot is stale (updated 2026-10-16T12:48:43.384744Z; age 38,014,912 ms), so no same-time independent MASTER exchange truth to establish equality. |
| UI-LCC-CARD-04 | NOT_TESTED | Rendered Open Positions 126; stale independent snapshot prevents same-time truth comparison. |
| UI-LCC-CARD-05 | NOT_TESTED | Rendered Live Exposure $9,634.77; stale independent snapshot prevents same-time truth comparison or confirming the value's truth tier. |
| UI-LCC-CARD-06 | NOT_TESTED | Rendered last fill HEMI SELL 25.0 at 2026-10-16T23:21:22.724387+00:00. No fresh independent MASTER exchange fill oracle available; stale snapshot is insufficient. |
| UI-LCC-CARD-07 | NOT_TESTED | Rendered last reject LINEA / INSUFFICIENT_MARGIN; no fresh independent MASTER exchange reject oracle available. |
| UI-LCC-WTBL-09 | NOT_TESTED | Wallet table rendered with rows and LIVE/CLO/OFF controls. Requirement includes proving selected copy model matches engine truth and control write/apply behavior; read-only route forbids changing controls, and the probe did not establish a contemporaneous independent per-wallet copy-model oracle. |

All six row verdicts deliberately remain NOT_TESTED rather than inferred from a populated UI. Exact missing route for the five card rows: a fresh, independent MASTER exchange snapshot/endpoint for time-aligned comparison. Exact missing route for WTBL-09: independent per-wallet copy-model state plus an approved non-mutating way to prove UI control write/apply behavior. Runtime evidence can still demonstrate a visible red health state (`Action needed: a close is failing`) and API websocket health `WS_OK`; these are observations, not certification of the requested values/behavior.

Source blob SHA-256 at register commit: `_archive/hl_stage2/HL_Copy_App_SSOT.py` = `7468ab5188750617b090b56c3e719d73e91f5b4241f4782382ccac1a22989276`.
