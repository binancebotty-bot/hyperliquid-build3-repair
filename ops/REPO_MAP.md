# REPO_MAP — which version is running, and where everything lives

Last updated: 2026-10-24 11:30Z (Hermes). Update this file in the SAME step as any change to the running
engine, its folder, its state folder, or its UI.

## THE ONE TRUTH LINE

```
RUNNING ENGINE : NONE. No HL_Live_Copy_Service_Core process exists.
RUNNING SHA    : none running. Pinned build is bf40a9d8bbb91348ebebf1b7d8d53ec15cbc7847
RUNNING FOLDER : C:/tmp/v31_bf40a9d-clean-20261024  (git status: CLEAN, 0 dirty, detached HEAD)
STATE FOLDER   : run8/state_20261024  -> DOES NOT EXIST YET
UI             : :8031 NOT LISTENING. :8014 is a DIFFERENT service (wallet_proof_engine), not the HL copy UI.
```

Plain words: the engine is **down**. It was force-stopped during the cutover and the launcher's
`prepare` step is failing with HTTP 500, so run8 was never created. Nothing is copying anything right
now. The clean checkout is present and clean at the pinned commit; it is simply not started.

Owner of the restart: **Codex**. Hermes does not touch the engine.

## FOLDER LABELS

| Folder | Label | Purpose |
|---|---|---|
| `C:/tmp/v31_bf40a9d-clean-20261024` | **ACTIVE (read-only)** | The product. Pinned bf40a9d, clean tree. Engine + UI start from here. Never edit inside it — changes go on a branch elsewhere, then get re-pinned. |
| `trading_stack/hl-build3-testnet-cert-evidence/run7` | **EVIDENCE (frozen)** | Last completed run's audit data (state_20261023). Point-in-time record — do not rewrite. |
| `trading_stack/hl-build3-testnet-cert-evidence/run3..run6` | **EVIDENCE (frozen)** | Older runs, superseded. Kept for the record only. |
| `trading_stack/hl-build3-testnet-cert-evidence/run8` | **ACTIVE (pending)** | Target state folder for the cutover. Does not exist yet; Codex creates it at start. |
| `C:/tmp/v31_bf40a9d` | **REFERENCE-OLD-BUILD** | Previous working tree, now dirty and abandoned. Not the product. Do not start from it. |
| `hyperliquid-build3-repair` (this repo) | **ACTIVE (work)** | Control surface, scripts, ops tooling, evidence. A branch of work — not the running product. |
| `ops/` | **ACTIVE** | Launch spec, startup/flatten scripts, runbook, and this map. |
| `certification/` | **ACTIVE** | Certification matrix and result-application scripts. |
| `EVIDENCE/` | **EVIDENCE** | Reports, rulings, audit extracts. Written by agents, read by the controller. |
| `tools/` | **ACTIVE** | Helper tooling (cert posting queue, etc.). |
| `worker_patches/` | **EVIDENCE** | Patches produced by Kanban workers. |
| `process/` | **REFERENCE** | Port-vs-rebuild and process notes. |
| `graphify-out/`, `anonymous_clone_t_5ce39500/` | **ARCHIVE** | Graphify output and a throwaway clone. Not on the running path. |
| `_archive/` | **ARCHIVE** | Archived stage code (`hl_stage2`). |
| `_deliver/` | **ARCHIVE** | One-off delivery folder. |
| `_scratch/`, `scratch/` | **SCRATCH** | Ad-hoc probes and one-off files. Anything durable belongs elsewhere. |
| `clone_test/` | **ARCHIVE** | Clone experiment. |
| Root loose files (`HEAD.txt`, `target_rows_dump.txt`, `lat_post_1922.md`, `_reg_of_record.json`, `MERGE_*`, `DONE10_*`, `cert_matrix_*.json.tmp`, `debug_check.py`) | **SCRATCH — to be filed** | Loose artefacts that should be moved into the labelled folder that matches them, or archived. |

## RULES THAT KEEP THIS TRUE

1. **Running folders are read-only.** Never edit, create or drop files inside the running checkout
   (`C:/tmp/v31_bf40a9d-clean-20261024`). Every change goes on a branch in a separate working folder,
   gets reviewed, and then gets re-pinned to a new SHA.
2. **One truth file.** This file. Whoever changes the running SHA, the folder, the state folder or the
   UI updates it in the same step.
3. **Identity line on every status report:** running PID, running SHA, `git status` clean yes/no,
   state folder, UI folder. A mismatch is reported at once, never hidden.
4. **Nothing unlabelled lives past a day.** Every top-level folder carries one of ACTIVE / ARCHIVE /
   REFERENCE-OLD-BUILD / EVIDENCE.
5. **New files go in the labelled folder that owns them**, never in the repo root and never inside a
   running tree.

## KNOWN OPEN FAULTS

- Engine down; launcher `prepare --dry-run` returns `PREPARE_FAILED: HTTP Error 500`. Owner: Codex.
- `:8031` (HL copy UI) not listening. It will come up with run8. Owner: Codex.
- This repo's working tree carries 153 dirty entries. Owner: Hermes (tidy lane, in progress).
