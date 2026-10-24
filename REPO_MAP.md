# REPO_MAP — what is actually here

Verified against the working tree on 2026-10-24, not against intent. If a directory is
missing from this list it is not part of the repo.

| Path | Purpose | Notes |
|---|---|---|
| `_archive/hl_stage2/` | The live-copy engine (`HL_Live_Copy_Service_Core.py`), the UI (`HL_Copy_App_SSOT.py`) and their runners | This is the Core. Never edit a running build in place; build from a pinned commit. |
| `certification/` | Certification matrix + generator | `certification_matrix.csv/.json`, `gen_matrix.py` |
| `EVIDENCE/` | Durable evidence artifacts and schemas | Written by the lane, read by reviewers |
| `process/` | Operating documents: matrix, PC run scripts/specs, port-vs-rebuild crosschecks | Reference, not executable |
| `tools/` | Repo-side helpers (`cert`, `function_inventory.py`, `restore_live_config.py`, `run_report.py`) | |
| `ops/` | Launch/stop/flatten tooling and the pinned launch spec | Present in the launcher checkout (`C:/tmp/codex-cutover-launcher-*`), NOT in every worktree |
| `graphify-out/` | Code-knowledge graph output | `graphify-out/cache/` is generated and now ignored |
| top-level `*.md` | Architecture, bootstrap, protocol, handover | |

## Where the lane actually runs (not in this tree)

| Thing | Path |
|---|---|
| Running Core build | `C:/tmp/v31_bf40a9d-clean-20261024` @ `bf40a9d` |
| Run state / audit | `C:/Users/wigmore/trading_stack/hl-build3-testnet-cert-evidence/run8/state_20261024` |
| Launch spec + ops tooling | `C:/tmp/codex-cutover-launcher-20261024/ops` @ `63f6f0d` |
| Global Core lock | `C:/Users/wigmore/AppData/Local/HL_Live_Copy_Service_Core/engine-global.lock` |

A worktree is a build/staging area. A release is only a release if its directory matches a
committed SHA — a modified release directory is a breach, not a build.
