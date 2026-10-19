# The SSOT source hash map — six hashes, one file

Established 2026-10-19 by hashing every candidate copy, not by trusting a declaration.

`HL_Copy_App_SSOT.py` exists in at least six distinct states across this estate:

| hash | what it is | resolves? |
|---|---|---|
| `fad19d22…` | 13 May tree `build3-live-screen-0513-view/hl_stage2/`, **served by :8023** | **yes**, on disk |
| `658ec8e3…` | the file at `tested_commit 89b3bc7` | yes, via git |
| `c0f9e508…` | **declared by the register of record** (`cert/local-main-b142cf8`) | **NO — no file on this box matches** |
| `7468ab51…` | the file at the cert branch's own HEAD | yes, via git |
| `4574ca72…` | the file at `origin/main` | yes, via git |
| `b45ff9af…` | **what :8031 actually serves** | yes, on disk |
| `bb7b9cc3…` | current working-tree `_archive/hl_stage2/` | yes, on disk |

## The two findings that matter

1. **The register of record declares a hash that resolves to no artifact.** `c0f9e508` is in
   `source_sha256["hyperliquid-build3-repair/HL_Copy_App_SSOT.py"]` on `cert/local-main-b142cf8`, and no
   `HL_Copy_App_SSOT*.py` under `trading_stack` hashes to it. Same defect class as the 12 FAIL rows citing
   `NET_LIFE_SETTLE_fa9d9f55ff.json`, which also exists nowhere: **a declaration with nothing behind it.**

2. **The cert branch's HEAD contains a different file (`7468ab51`) than the hash it declares (`c0f9e508`).** Reading
   the file from the very ref that declares it does not reproduce the declared hash.

## Merge consequence

Merging the cert branch into `origin/main` would replace `fad19d22` (which resolves, and which :8023 actually serves)
with `c0f9e508` (which resolves to nothing), and drop 42 rows, on top of verdicts that are only 77-of-579
audit-verified. Do not merge until the declaration is corrected.

## Rule

A `source_sha256` entry is only a binding if the hash resolves to a real artifact. Check it by hashing the file; a
declared hash is a claim, not evidence.
