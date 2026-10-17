# UI-FP-175/178/179/181/182/183 evidence

This is a separate UI-only evidence section. The b142cf88 register does not serve `/live-copy`; per controller ruling, these observations are bound to the actual serving process/build. At capture, PID 8668 was Uvicorn serving from `C:/Users/wigmore/trading_stack/hl-build3-testnet-cert/_archive/hl_stage2`, checkout commit `6cf5dcf671b791e8f833060458f00cb7bb7bcdb5`, with `HL_Copy_App_SSOT.py` SHA-256 `658ec8e31eb96d70acc15dc30860334c23612d2e3e9d19fb63ed9ec4e6fa86c2`.

Run the read-only capture from the repository root:

`PLAYWRIGHT_BROWSERS_PATH=C:/Users/wigmore/AppData/Local/ms-playwright C:/Users/wigmore/AppData/Local/Programs/Python/Python311/python.exe EVIDENCE/ui_fp_175_183/probe.py`

The probe renders `/live-copy` with headless Chromium and independently GETs `/api/state`, `/api/live-config`, and `/api/ui-state`; it does not import the engine, submit forms, or mutate controls. Raw DOM and API responses are in `dom_capture.json`. Results are recorded individually in `UI_FP_175_183_t_9d8c6a22.json`: WS health detail rows 175/178/179 are NOT_TESTED because the live_ws_health source/API route and matching DOM fields are absent; controls rows 181/182/183 are PARTIAL because DOM and two independent GET endpoints agree, while POST/persistence behavior is deliberately untested under the read-only restriction.

No main certification matrix was modified.
