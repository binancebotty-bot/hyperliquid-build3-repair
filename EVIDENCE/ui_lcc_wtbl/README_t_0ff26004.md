# B3-CERT t_0ff26004 - UI-LCC WTBL-10..14 + DETAIL-01

Register of record: main:certification/certification_matrix.json @ b142cf88d389e791160f691aac3d936852b99975 (read via git show b142cf88:... ONLY).

UI source: _archive/hl_stage2/HL_Copy_App_SSOT.py @ register commit, sha256 7468ab5188750617b090b56c3e719d73e91f5b4241f4782382ccac1a22989276. Panel block render_live_copy_control_panel lines 5436-6016, sha256 174bc8214e2e7755...

Live surface READ-ONLY untouched: http://127.0.0.1:8031/live-copy HTTP 200 (PID 8668). No start/stop, no POST to live surface, no served-config write, no Edge/CDP touch, no edit to certification_matrix.json or apply_verified_results.py.

## Route (copied from EVIDENCE/ui_wallet t_7fc73e22)

Register-commit panel extracted VERBATIM (never imported) and rendered in headless Chromium (playwright, py3.11). window.fetch routed at the network layer to REAL served payloads from :8031. Independent oracle = served JSON API, compared field-by-field to the DOM. Harness facts: unset PLAYWRIGHT_BROWSERS_PATH; serve via page.route from an http origin (not about:blank); page.on('dialog',accept) for Archive.

## Verdicts

WTBL-10 NOT_TESTED: F/N inputs render on all 15 rows and ride the Save wire, but the row negative test "source unavailable shows n/a/Unavailable not 0" FAILS (null fixed_notional/norm_base renders default 10/100), and the B (leader_equity_base) input named in the feature is type=hidden (source line 5780).

WTBL-11 PASS: Save executes; click posts /api/live-config/set-wallet with row payload.
WTBL-12 PASS: CLO executes; posts /api/live-config/set-mode mode=CLO.
WTBL-13 PASS: OFF executes; posts /api/live-config/set-mode mode=OFF.
WTBL-14 PASS: Archive executes; posts /api/live-config/remove-wallet archive=true.
DETAIL-01 PASS: row click inserts detail row with sections A-E; A renders attribution_quality from engine truth.

## Key raw facts

15 rows rendered. Per-row DOM vs engine truth: mode 15/15, copy_mode 15/15. Wires: Save body {...mode LIVE copy_mode fixed norm_base 100 fixed_notional 12...}; CLO mode=CLO; OFF mode=OFF; Archive archive=true. Detail section B Open Positions (94) matches served current_open_positions len 94; attribution ENGINE_LEDGER_SLEEVES_PARTIAL matches served. Negative: /api/live-config non-JSON 500 surfaces in #lcStatus as a JSON parse error, 0 rows rendered.

## Honesty boundary

These rows exist because sibling PASS rows WTBL-01..08 were earned on a SHALLOW server-side header-render check (WTBL-08 passed because header=="Controls"), which cannot show a control EXECUTES. This package executes the certified renderer and captures the write wire (component PASS). The engine-APPLIES leg of execution_proof is bound to committed in-process proof certification/results/UI_CORRECTION_2d29211.json checks B1-B7, not re-proven live, because CERT_ENVIRONMENT forbids mutating the live surface and the operator :8031 build is NOT the register build. WTBL-10 stays NOT_TESTED until the missing runtime (source-unavailable render path) exists.

## Live divergence noted (not this card's evidence)

GET /api/state reports send_mode=OFF while GET /api/live-config reports every wallet mode=LIVE.

## Files

UI_LCC_WTBL_10_14_DETAIL_01_t_0ff26004.json (six rows, executed checks + verdict); raw_wtbl_probe.json (capture); probe.py (harness); emit.py (emitter); HL_Copy_App_SSOT_b142cf88.py (register UI source); live_config.json; ws_health.json.
