# ENG-INV-01..06 Evidence Audit

Audited branch: `cert/local-main-b142cf8` at `b142cf88d389e791160f691aac3d936852b99975`.
The six matrix entries all cite tested commit `43731b4f1f19a56e835032dabf608a550f925717`. `git merge-base --is-ancestor 43731b4f origin/cert/local-main-b142cf8` returned 1 (not ancestor); the full cited commit `43731b4f1f19a56e835032dabf608a550f925717` is an ancestor (short `43731b4` check returned 0). Thus evidence is for an earlier source snapshot, not the audited branch head.

## Row verdicts

| row_id | verdict | why |
|---|---|---|
| ENG-INV-01 | KEEP | Corrected shared JSON contains a distinct `checks.ENG-INV-01` result (`NO_PROCESS_SPAWNS`, zero found) and an `inv01_add_subprocess` negative control that fails as expected. It explicitly tests the matrix assertion “One process” via zero process spawns, though its stated check is source spawn census rather than an independent OS process-count observation; KEEP is limited to the cited evidence's static assertion. |
| ENG-INV-02 | KEEP | Same JSON has distinct `checks.ENG-INV-02` (`ONE_PHYSICAL_ORDER_SITE`, one physical site at line 2703) and `inv02_add_second_order_site` negative control which fails. This directly distinguishes the one-call-site assertion. |
| ENG-INV-03 | DEMOTE | The ENG-INV-03..05 artifact has only combined aggregate totals (third-party imports=0, persistent stores=0, Build-4 imports=0) and aggregate findings. It does not provide a separately keyed ENG-INV-03 result nor a row-specific negative control. The report describes a census and three category mutations collectively, but the delivered JSON cannot bind the result uniquely to this row. |
| ENG-INV-04 | DEMOTE | Same combined artifact: persistent-store count is zero, but no row-keyed assertion or row-specific mutation result distinguishes ENG-INV-04 from ENG-INV-03/05. |
| ENG-INV-05 | DEMOTE | Same combined artifact: Build-4 import count is zero, but no row-keyed assertion or row-specific mutation result distinguishes ENG-INV-05 from ENG-INV-03/04. |
| ENG-INV-06 | KEEP | ENG-INV-06..09 JSON has a distinct `invariants.ENG-INV-06` object with four checks and its own result, plus `INV-06_second_order_site` negative control. ENG-INV-06 report also states its specific assertion and observed call site, zero process spawns, dependencies and stores. |

## Shared-file attribution

- `ENG-INV-01-02_ENG-010-014_SEM-B1-B4_corrected_43731b4f.json` legitimately covers ENG-INV-01 and ENG-INV-02: the checks are independently keyed and have matching mutation controls. It also reports other separately keyed test families, outside this audit.
- `ENG-INV-03-05_43731b4f.json` does NOT legitimately substantiate PASS for any of ENG-INV-03, ENG-INV-04, or ENG-INV-05 as attributed in the matrix: category totals/findings are merged rather than row-keyed. The accompanying report describes three census categories and mutations, but the source script referenced by that report (`census_eng_inv_03_05_corrected.py`) is not present in the audited branch tree, so those claims could not be reproduced here.
- `ENG-INV-06-09_43731b4.json` legitimately covers ENG-INV-06: the result object and mutation test are specifically keyed. It separately includes INV-07..09, outside this audit.

## Rerun status

The cited source commit is present and is an ancestor of the certification head. The corrected ENG-INV-01/02 harness is in the branch, but the complete cited-source checkout plus environment needed for its runtime checks was not available in this clean audit worktree; no new run is represented as a reproduction. For ENG-INV-03..05 the report's named census/mutation scripts are absent from the branch tree, so rerun is not possible from the shipped artifacts. For ENG-INV-06..09 `census_inv_06_09.py` is present, but the clean audit worktree has no checked-out certified repository at the historical commit/path required by its `--engine-dir` input; therefore no rerun was performed. The originals, as recorded in the artifacts, are: corrected ENG-INV-01/02 shared run PASS, 36/36 checks and 11/11 mutation negatives; ENG-INV-03..05 census PASS with 0 third-party imports, 0 persistent stores, 0 Build-4 imports and three described mutations detected; ENG-INV-06 individual result PASS with 4/4 checks and its mutation reported FAIL as expected. These are original artifact claims, not newly reproduced results.
