# ENG-INV-01 / -02 / -06 — row-bound re-earn (card t_20e1cb6d)

Branch off `89b3bc7`. **Not merged.** No edit to `apply_verified_results.py` or
`certification_matrix.json`.

## Deliverable

`verdicts.json` — one object per row: `{row_id, verdict, quoted_evidence,
mutation_control, why}`.

| row | verdict |
|---|---|
| ENG-INV-01 | PASS |
| ENG-INV-02 | **FAIL** |
| ENG-INV-06 | PASS |

## How it was produced

* `probe.py --repo <worktree> --out result.json` — reads engine sources out of
  git objects at `43731b4f` (the commit the register cites), so the result is
  commit-bound and cannot drift with a dirty tree. It is not a re-run of
  `census_inv_06_09.py`: that harness scopes ENG-INV-06 to `py_files=[core_file]`
  and never looks at the other production files.
* `gen_final.py` — builds `verdicts.json`, quoting the cited artifacts from
  `cited/` (copied from `origin/cert/local-main-b142cf8`, hashes in
  `cited/SHA256SUMS.txt`).

## Findings in one line each

* **01 PASS.** Row-owned single check `NO_PROCESS_SPAWNS`; widened to all five
  production sources, still 0 spawns; Popen and multiprocessing.Process
  mutations both flip it.
* **02 FAIL.** The cited detail is self-contradicting — `"[2703] (total all: 2)"`
  — because the predicate is `2700 < line < 2800` on the Core file only
  (harness L232). At `43731b4f` there are **two** physical `.order()` call
  nodes: `HL_Live_Copy_Service.py:1036` and `..._Core.py:2703`. A second real
  send path appended to the service file leaves the cited predicate PASSING.
  Needs a Controller/Architect scope ruling on whether "production" means Core
  only.
* **06 PASS.** "No **new** engine/runtime": vs `89b3bc7` zero files added, no
  new `.order()` site, no new store constructor. The cited run scanned 1 file
  (limitation stated); the whole-file-set comparison closes that gap.

## Reproduce

```
python certification/eng_inv_01_02_06_reearn/probe.py --repo . \
  --out certification/eng_inv_01_02_06_reearn/result.json
python certification/eng_inv_01_02_06_reearn/gen_final.py
```
