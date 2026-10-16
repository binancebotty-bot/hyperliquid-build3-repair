# B3-CERT t_d925c3dd — 6-row evidence package

Register of record: `main:certification/certification_matrix.json` @ `b142cf88d389e791160f691aac3d936852b99975`
(read via `git show b142cf88:...` ONLY; the working-tree copy was never used).

Live surface: `http://127.0.0.1:8031/live-copy` (HTTP 200, UI PID 8668) plus the running engine
PID 28164. All captures READ-ONLY; no start/stop/order action; no register edit; no mocks.

## Verdicts (6 rows)

| row | area | prior | result recorded | basis |
|---|---|---|---|---|
| F-UI-001 | REGRESSION | BLOCKED (ui-visibility) | **FAIL** | rendered DOM + served API + source @register commit contain no truth-tier token |
| F-UI-002 | REGRESSION | BLOCKED (ui-visibility) | **PARTIAL** (surface PASS, stale-affects-status FAIL) | rendered DOM shows age/source; stale snapshot does not change status |
| F-UI-003 | REGRESSION | BLOCKED (ui-visibility) | **FAIL** | 60 green/red elements captured; green comes from engine status, no GREEN-ONLY-001 evaluator |
| F-TEST-010 | REGRESSION | NOT_TESTED | **NOT_TESTED** | missing runtime independent oracle (OD-11) + replay fixture + halt path |
| F25-X05 | LIFECYCLE | NOT_TESTED | **NOT_TESTED** | no authoritative lease mechanism / canonical operator entry point (OD-12) |
| F25-X06 | LIFECYCLE | NOT_TESTED | **NOT_TESTED** | no deployment-candidate build mechanism exists (OD-12) |

## Evidence files

- `F_UI_001_002_003_t_d925c3dd.json` — rows F-UI-001/002/003
- `F_TEST_010_F25_X05_X06_t_d925c3dd.json` — rows F-TEST-010, F25-X05, F25-X06
- `raw/` + `scripts/` — captured runtime output and the harnesses that produced it (sha256 in each JSON)

## Key raw facts

- Truth-tier literals in the rendered panel, the served `/api/state` + `/api/ui-state`, and the
  certified UI source @ `b142cf88`: **0 occurrences of all seven tier tokens** (F-UI-001 FAIL).
- Oracle: `exchange_account_snapshot_app.json` `fetched_at_ms=1792154922440` → age ≈ **36,326,546 ms**
  at capture; the panel still shows green `Websocket OK` / `Live` and a value (F-UI-002).
- 60 green/red/amber elements captured; source @ register commit has **0** occurrences of
  `GREEN_ONLY_001` (F-UI-003 FAIL).
- No `lease_holder`/`single_writer`/`LOCKFILE`; no `current_release`/`launcher`/`version_source`;
  no release/build tooling anywhere in the tree (F25-X05/X06).
- Source blobs read at the register commit: `HL_Copy_App_SSOT.py` sha256
  `7468ab5188750617b090b56c3e719d73e91f5b4241f4782382ccac1a22989276`;
  `HL_Live_Copy_Service_Core.py` sha256
  `b171ec8fef01ead5ed2fe4a4a075857b5b1a56e425bab8394440c7dbad57f2a0`.

Committed on isolated branch `hermes/ui-fp-t_d925c3dd`; the shared main checkout was not written to.
