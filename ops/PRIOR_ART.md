# Startup prior art

Evidence below combines this checkout's read-only search with Hermes's signed inventory in PR #81 comment 6371590155. External files were not opened or copied.

| Item | Path and purpose | Why it is stale or limited | Disposition |
|---|---|---|---|
| `pl_core_watchdog` | `C:/Users/wigmore/.hermes/scripts/pl_core_watchdog.py`; Hermes reports PID 38604 currently supervises Core. | Hermes reports it reads an external launch environment, points at a temporary `C:/tmp/v31_bf40a9d/...` tree and run6 state, and only relaunches when no Core PID exists. The active run is run7. | Do not edit or stop it in this branch. Retire it and disable its startup entry only under a fresh direct order. `supervise` refuses until retirement is confirmed. |
| Watchdog launch environment | `C:/Users/wigmore/.hermes/state/core_launch_env.json`; external launch settings. | Hermes reports it contains a private key and a mainnet leader setting. Its values were not inspected, printed, or copied. It points away from the committed launch spec. | Preserve it untouched; do not use it for a new launch. A separate authorized migration must remove secret material from plaintext state. |
| `runner_guard` | No matching file is present in this checkout. | Its external location and exact behavior could not be verified from this tree. | Leave it untouched until its owner identifies the path and a fresh order assigns its retirement. |
| 15 October continuous-runner spec | No matching spec is present in this checkout. | The file and its ownership could not be verified here. | Preserve it until the project owner locates it; do not guess or disable a scheduled task. |
| Checked-in orphan/startup checks | `_archive/hl_stage2/test_core_startup_orphan_nonblocking.py`, `_archive/hl_stage2/test_core_ws_startup_grace.py`, and `_archive/hl_stage2/test_t1b_startup_orphan.py`. | These are tests, not launchers or persistent relaunchers. | Keep as regression evidence; they do not replace the single pinned-spec supervisor. |
| New TESTNET launcher | `ops/testnet_startup.py` with `ops/testnet_launch_spec.json`. | It uses the committed source pin and one absolute shared run7 state directory. | Use only after the old watchdog is retired and a fresh order authorizes launch. It never modifies wallet modes or sends cancellations. |
