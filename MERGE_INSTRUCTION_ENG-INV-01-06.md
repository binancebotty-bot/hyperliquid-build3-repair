# MERGE INSTRUCTION — ENG-INV-01..06 merge-ready branch (card t_26921cd0)

Status: READY FOR CONTROLLER APPROVAL. Nothing was merged to main by this card.

## Branch

    branch : hermes/eng-inv-merge-ready-t_26921cd0
    head   : 55902f3a5fa9d74fbd16ffb7f3272001831ec678
    base   : origin/main @ 3ea99f4 (no merge to main performed)
    pushed : yes

Verify:

    git ls-remote --heads origin hermes/eng-inv-merge-ready-t_26921cd0
    # 55902f3a5fa9d74fbd16ffb7f3272001831ec678  refs/heads/hermes/eng-inv-merge-ready-t_26921cd0

## Files changed vs origin/main (10)

    M  certification/certification_matrix.json                (6 rows: NOT_TESTED -> PASS)
    A  certification/results/ENG-INV-01-02_ENG-010-014_SEM-B1-B4_corrected_43731b4f.json
    A  certification/results/ENG-INV-03-05_oracle_t_ff1af604.py
    A  certification/results/ENG-INV-03-05_oracle_run_tested_43731b4f.json
    A  certification/results/ENG-INV-03-05_oracle_run_head_b142cf8.json
    A  certification/results/ENG-INV-03-05_resolution_t_ff1af604.json
    A  certification/results/ENG-INV-06-09_43731b4.json
    A  certification/results/apply_eng_inv_03_05_t_ff1af604.py
    A  overlay_six.py   (deterministic, idempotent row overlay, re-runnable)
    A  verify_six.py    (per-path resolution proof, non-zero exit on any miss)

No engine file, no CONTROL_STATE.json, no apply_verified_results.py change.

NOTE: the row-bound source branch carried a stale operator_hold block in CONTROL_STATE.json
(set 2026-10-14, absent from origin/main). That branch was NOT merged — only the evidence
files were checked out — so the hold block is deliberately absent from this branch.

## Six-row before/after (origin/main -> branch)

    row          before      after   tested_commit  tested_at_utc
    ENG-INV-01   NOT_TESTED  PASS    43731b4f       2026-10-14T09:05:00Z
    ENG-INV-02   NOT_TESTED  PASS    43731b4f       2026-10-14T09:05:00Z
    ENG-INV-03   NOT_TESTED  PASS    43731b4f       2026-10-17T11:15:00Z
    ENG-INV-04   NOT_TESTED  PASS    43731b4f       2026-10-17T11:15:00Z
    ENG-INV-05   NOT_TESTED  PASS    43731b4f       2026-10-17T11:15:00Z
    ENG-INV-06   NOT_TESTED  PASS    43731b4f       2026-10-14T05:00:01Z

Register totals on the branch: PASS=6, NOT_TESTED=826, total=832 (id set identical to main).

## Per-path resolution check (verify_six.py, EXIT=0)

    ENG-INV-01  certification/results/ENG-INV-01-02_ENG-010-014_SEM-B1-B4_corrected_43731b4f.json  OK
    ENG-INV-02  (same file as 01)                                                                 OK
    ENG-INV-03  certification/results/ENG-INV-03-05_oracle_t_ff1af604.py                         OK
                certification/results/ENG-INV-03-05_oracle_run_tested_43731b4f.json              OK
    ENG-INV-04  (same two files as 03)                                                           OK
    ENG-INV-05  (same two files as 03)                                                           OK
    ENG-INV-06  certification/results/ENG-INV-06-09_43731b4.json                                 OK

    VERDICT: six rows resolvable = True | failures = []

## Idempotence

overlay_six.py run twice; matrix sha256 identical after both runs
(54414de18e43e32e737e8c1c8c5747126dbb80c10f5e1aac43434a02b26e4d22). The overlay only
rewrites the six in-scope rows and aborts if any out-of-scope row or the id set would change.

## Merge command (controller decision — NOT run by this card)

    git fetch origin hermes/eng-inv-merge-ready-t_26921cd0
    git rev-parse FETCH_HEAD  # must equal 55902f3a5fa9d74fbd16ffb7f3272001831ec678; otherwise STOP
    git checkout main && git pull --ff-only
    git merge --no-ff 55902f3a5fa9d74fbd16ffb7f3272001831ec678
      -m "ENG-INV-01..06: six row-bound PASS rows with resolving evidence_ref (t_26921cd0)"
    git push origin main

Post-merge re-check on main: python3 verify_six.py  -> EXIT=0

## Caveats for the controller

1. Verdicts were NOT changed or re-adjudicated; this card only makes register and cited files
   co-exist on one branch so the citations resolve.
2. ENG-INV-03/04/05 tested_at 2026-10-17T11:15:00Z is the row-bound re-earn run time; tested_commit
   stays 43731b4f as recorded by that artifact.
3. Control-plane holds are outside this card: the merge moves only the certification register and
   evidence files.
