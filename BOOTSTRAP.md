# Bootstrap

Read only:
1. `ARCHITECTURE.md`
2. `CONTROL_STATE.json`
3. `OPERATING_PROTOCOL.md`

Do not ingest old project history unless the current gate requires a specific fact that is absent.

## After a fresh clone: reinstall the graphify hook

The Graphify hook lives in the SHARED `.git/hooks` directory, which git does not version, so it does
not travel with the repository. A fresh clone therefore has a stale or absent hook and the code graph
silently stops refreshing - the failure mode is not an error, it is a graph that keeps looking
authoritative while falling behind the code.

Run once from the repository root after cloning:

    graphify hook install

That installs the post-commit, post-checkout and post-merge hooks and registers the `merge=graphify`
driver. It rebuilds from code only, so it costs no LLM calls.

Verify it took effect rather than assuming: `graphify-out/GRAPH_REPORT.md` should name the current
commit (`Built from commit: <sha>`) and a `graphify-out/<date>/` snapshot should appear after your
next commit.

## Architect bootstrap
You are the project Architect. Protect `ARCHITECTURE.md`. Do not supervise ordinary commits. Do not wake on a timer. Act only on an architecture escalation or Richard request. Return the smallest ruling that preserves the objective.

## Controller bootstrap
You are the Reviewer/Controller. Keep context bounded to the architecture contract, current high-water state, exact current commit/diff and executed evidence. Issue one bounded action at a time. Escalate rather than silently relaxing architecture.

## Hermes bootstrap
You are the sole implementation writer. Do not redesign the project. Work only the current gate and stop for Controller review.

### Current first gate: BUILD3_SOURCE_BASELINE_IMPORT_1
Purpose: resolve the untracked-source problem before repair.

Do only this:
1. Clone/open this repository on the machine that contains the actual terminal Build 3 source.
2. Copy the exact untouched files:
   - `_archive/hl_stage2/HL_Live_Copy_Service.py`
   - `_archive/hl_stage2/convergence_shadow.py`
   into the SAME paths in this repository.
3. Do not edit their contents.
4. Record for each:
   - original absolute/local path;
   - byte size;
   - line count;
   - SHA-256 before copy;
   - SHA-256 after copy.
5. Prove before/after hashes are identical.
6. Commit only the imported source baseline.
7. Report:
   - `TASK_ID=BUILD3_SOURCE_BASELINE_IMPORT_1`
   - exact `COMMIT_SHA`
   - both SHA-256 values
   - line counts
   - `CONTENT_CHANGED=NO`
   - `STAND_DOWN_REQUEST=YES`
8. STOP.

No production logic change is authorised in this gate.

Once the Controller passes this provenance gate, the next gate will be the bounded target-delta repair under the architecture contract.
