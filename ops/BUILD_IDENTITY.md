# BUILD_IDENTITY

One product, one identity. Written 2026-10-25 16:22Z (Hermes, tidy lane). Updated 2026-10-25 for the v32
8ce6763 product ahead of a controller-ordered cutover. Nothing here was deleted to make it true.

## CURRENT PRODUCT

| Field | Value |
|---|---|
| Build SHA | `8ce6763c70c9a4cf532274cafd466bb028ebf0c4` (v32, Codex PASSED candidate A) |
| Folder | `C:/tmp/v32_8ce6763` (detached HEAD, clean) |
| Engine | `_archive/hl_stage2/HL_Live_Copy_Service_Core.py` |
| State dir | `C:/Users/wigmore/trading_stack/hl-build3-testnet-cert-evidence/run8/state_20261024` |
| Launcher spec | `C:/Users/wigmore/.hermes/state/core_launch_env.json` (cwd + script point at v32; `HL_LIVE_AUDIT_DIR` and `HL_LIVE_CONVERGE_THREAD=1` unchanged) |
| Mode | follower TESTNET / leader MAINNET |
| UI | `127.0.0.1:8031` |
| Cutover state | PREPARED ONLY — running engine still PID 5704 on the bf40a9d checkout; restart awaits the controller's word after Boss |

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
