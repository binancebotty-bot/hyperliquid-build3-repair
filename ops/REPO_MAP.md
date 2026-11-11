# REPO_MAP - the one current product, and the archived rest

Updated 2026-10-25 16:22Z (Hermes, tidy lane). No deletions were made. Update this file in the same step as any change
to the running build, its folder, its state folder or its UI.

## THE ONE CURRENT PRODUCT

```
BUILD       : bf40a9d8bbb91348ebebf1b7d8d53ec15cbc7847  (rw15, tag keep/product-pinned-bf40a9d)
FOLDER      : C:/tmp/v31_bf40a9d-clean-20261024   (detached HEAD at the pinned SHA)
ENGINE FILE : _archive/hl_stage2/HL_Live_Copy_Service_Core.py
STATE DIR   : C:/Users/wigmore/trading_stack/hl-build3-testnet-cert-evidence/run8/state_20261024
MODE        : follower TESTNET, leader MAINNET
UI          : 127.0.0.1:8031  (127.0.0.1:8014 is wallet_proof_engine, a different service)
```

There is no second product. Everything else is archive, evidence, scratch or reference.

## NEVER DELETE

None of the following may ever be deleted, renamed, force-pushed over or re-pointed:

- tags `keep/product-pinned-bf40a9d`, `keep/engine-two-month-20260602`, `keep/build-june-20260602` (remote, verified)
- branch `candidate/core-20260602` -> 2abf84cc52a1fd998f8f3494b9e9c4242208de7b (remote)
- folder `_archive/hl_stage2/` in every branch that carries it (holds the 2 June engine, 7705 lines,
  sha256 5bda57be3fbf8766c0d19b7380e451e22342bf953ed97e10d3fa43e191b1f848)
- folder `C:/tmp/v31_bf40a9d-clean-20261024` (the running checkout)
- state folders `run3` .. `run8` under `trading_stack/hl-build3-testnet-cert-evidence` (point-in-time evidence)
- tags `archive/20261025/*` (754 local, 1508 remote refs incl. peeled) - the branch archive of 2026-10-25

## ARCHIVED REST

| Item | Where | What it is |
|---|---|---|
| Two-month engine (2 June 2026) | `_archive/hl_stage2/HL_Live_Copy_Service_Core.py`, 7705 lines, sha256 5bda57be...1f848; branch `candidate/core-20260602`, tip 2abf84c; tags `keep/engine-two-month-20260602`, `keep/build-june-20260602` | The engine that actually traded; certification base. Not the running build. |
| June 2026 build import | same commit 2abf84c ("Import Build 3 live engine HL_Live_Copy_Service_Core.py unchanged", 2026-10-09); ancestor of main | First repo import of that engine. Kept, not run. |
| Older working tree | `C:/tmp/v31_bf40a9d` | Same SHA, dirty, abandoned. Do not start from it. |
| Runs 3-7 | `trading_stack/hl-build3-testnet-cert-evidence/run3..run7` | Superseded run evidence. Frozen. |
| This repo | `C:/Users/wigmore/hyperliquid-build3-repair` | Control surface, ops, certification, EVIDENCE. Not the running product. |

## OPS FILES ON THE PR #95 LANE (`hermes/fresh-pair-launcher`)

| File | What it is | State |
|---|---|---|
| `ops/fresh_pair.py` | fresh start script; `--no-spawn` dry run and injectable start path; not applied to run19 | pushed, PR #95 (draft) |
| `ops/HOTFIX_QUEUE.md` | hot-fix queue; every row a live hot fix routed per `ops/HOTFIX.md` | pushed, PR #95 (draft) |
| `ops/HOTFIX.md` | hot-fix route, pre-checks, load, proof, rollback | pending Codex |
| `ops/apply_hotfix.py` | the helper that applies one queue item per `ops/HOTFIX.md` | pending Codex |

## RULES

1. The running folder is read-only. Changes go on a branch elsewhere, get reviewed, then get re-pinned to a new SHA.
2. This file is the one truth file for build/folder/state/UI. Whoever changes one updates this file in the same step.
3. Nothing is deleted from this repo without an explicit order that names the exact refs. 2026-10-25 ruling: delete nothing.
