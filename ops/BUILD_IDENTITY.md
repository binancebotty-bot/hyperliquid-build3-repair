# BUILD_IDENTITY

One product, one identity. Written 2026-10-25 16:22Z (Hermes, tidy lane). Updated 2026-10-25 for the v32
8ce6763 product ahead of a controller-ordered cutover. Nothing here was deleted to make it true.

## CURRENT PRODUCT

| Field | Value |
|---|---|
| Build SHA | `6c693108332d6bb961e54638c5a61014df61d6d6` (v33, Codex PASS for 8ce6763..6c69310) |
| Folder | `C:/tmp/v33_6c69310` (detached HEAD, clean) |
| Engine | `_archive/hl_stage2/HL_Live_Copy_Service_Core.py` |
| State dir | `C:/Users/wigmore/trading_stack/hl-build3-testnet-cert-evidence/run8/state_20261024` |
| Launcher spec | `C:/Users/wigmore/.hermes/state/core_launch_env.json` (cwd + script point at v32; `HL_LIVE_AUDIT_DIR` and `HL_LIVE_CONVERGE_THREAD=1` unchanged) |
| Mode | follower TESTNET / leader MAINNET |
| UI | `127.0.0.1:8031` |
| Cutover state | LIVE — running engine is PID 34896 on the v33_6c69310 checkout, started 2026-10-25T22:12:39Z under the controller's restart order (testnet restarts are controller authority). Previous engine PID 31180 on v32 was stopped by exact PID at 22:12:30Z after the zero-engine proof; one engine only, holding run8/instance.lock exclusively. Rollback is v32_8ce6763. Credentials come from the launcher spec env block (names present, lengths only). |

## ROLLBACK

| Field | Value |
|---|---|
| Build SHA | `bf40a9d8bbb91348ebebf1b7d8d53ec15cbc7847` (rw15) |
| Keep tag | `keep/product-pinned-bf40a9d` (remote, verified) |
| Folder | `C:/tmp/v31_bf40a9d-clean-20261024` (detached HEAD, 1 untracked evidence file) |
| Engine | `_archive/hl_stage2/HL_Live_Copy_Service_Core.py` |
| Notes | Rollback product. Leave the folder in place until the v32 cutover is proven. |

## ARCHIVED

| Item | Ref | SHA |
|---|---|---|
| Two-month engine (2 June 2026, 7705 lines, sha256 `5bda57be...1f848`) | folder `_archive/hl_stage2/`; tag `keep/engine-two-month-20260602` | commit `2abf84cc52a1fd998f8f3494b9e9c4242208de7b`, branch `candidate/core-20260602` |
| June 2026 build import | tag `keep/build-june-20260602` | same commit `2abf84cc52a1fd998f8f3494b9e9c4242208de7b` |
| 2026-10-25 branch archive | tags `archive/20261025/*` | 754 tags / 1508 remote refs, per-branch tips |
| Runs 3-7 | `run3..run7` state folders | frozen evidence, not run |

## NEVER DELETE

`keep/*` tags (all three: `keep/product-pinned-bf40a9d`, `keep/engine-two-month-20260602`,
`keep/build-june-20260602`), `candidate/core-20260602`, `_archive/hl_stage2/` in every branch, the running
checkout `C:/tmp/v31_bf40a9d-clean-20261024`, the new checkout `C:/tmp/v32_8ce6763`, state folders
`run3`..`run8`, and every `archive/20261025/*` tag.
No branch, tag or folder in this repo is deleted without an order that names the exact ref. The
2026-10-25 ruling (order 6398022825) is: delete nothing.

## Live pair — 2026-10-25T22:47:56Z

The engine and the UI are one product and are now restarted as one operation against a single
fresh audit dir (see ops/WORKER_BRIEF.md).

| | engine | ui |
|---|---|---|
| pid | 20592 | 46600 |
| folder | C:/tmp/v33_6c69310/_archive/hl_stage2 | C:/tmp/v34_ui_8262b87/_archive/hl_stage2 |
| build | 6c693108332d | 8262b872279c (ui/truthful-banner) |
| interpreter | Python 3.11 pythonw (the SDK lives only there) | pythoncore-3.14 python.exe, console-less |
| audit dir | run9/state_20261025 | run9/state_20261025 |

Audit history: run8/state_20261024 is archived and untouched (47 entries). run9 was created
empty at 22:47:55Z and its first record is 22:47:57Z, so the new lineage carries no backfill.

Follower account was flattened immediately before the restart: 18 positions and 1 open order
reduced to zero by reduce-only IOC closes, verified by a fresh exchange read.

State at start: auto_send_enabled False (a fresh state dir takes the default), WS_DEGRADED with
subscribe_pending while the first subscriptions ack. Both are declared, not hidden.

Operational notes learned here:
- start the UI from a parent whose PYTHON* variables do not leak into the 3.14 process; an
  inherited 3.11 environment makes the UI exit instantly, silently, with no listener.
- the engine must be started with the Python 3.11 pythonw; under 3.14 the SDK is absent and the
  failure looks like a credential problem rather than an interpreter problem.
- perp limit prices need BOTH five significant figures AND at most (6 - szDecimals) decimals;
  applying only the decimals cap gets 'Price must be divisible by tick size'.
