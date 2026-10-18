# Merge instruction — ENG-INV-01..06 rebuild (t_7366969c)

Status: review this branch and this instruction together at one commit. No merge to main was performed.

## Branch and base

Branch: hermes/eng-inv-rebuild-t_7366969c
Base: origin/main @ 2a2c24160a57ed5b2e8b298abfdf1dc06d64c1dd

## Register accounting (832-row origin/main base)

After this change: PASS=4, FAIL=2, BLOCKED=0, NOT_TESTED=826 (total=832).
Rows changed vs origin/main: ENG-INV-01, ENG-INV-02, ENG-INV-03, ENG-INV-04, ENG-INV-05, ENG-INV-06; each was NOT_TESTED on main. No row outside ENG-INV-01..06 changed.

ENG-INV-02 is FAIL: the census finds two reachable production exchange.order() sites (Core:2703; Service:1036). ENG-INV-06 is FAIL: its cited artifact scans one Python file only and reports a single site, contradicted by the committed two-site census; no all-five-file re-derivation was performed here. ENG-INV-01/03/04/05 retain reviewed PASS evidence.

The separate 790-row register at origin/cert/local-main-b142cf8 has 579 PASS, is not an ancestor of main, and all 790 IDs exist in the 832-row register. The 42 additional IDs on the 832-row base include ENG-017/018/019, ORD-009/010, SET-009, UI-DIFF-01, UI-ROUTE-01, and 34 others. This rebuild does not import or alter that 790-row register.

## Changed files vs origin/main

M certification/certification_matrix.json (six rows listed above)
A certification/results/ENG-INV-01-02_ENG-010-014_SEM-B1-B4_corrected_43731b4f.json
A certification/results/ENG-INV-02_two_site_census_43731b4f.json
A certification/results/ENG-INV-03-05_oracle_t_ff1af604.py
A certification/results/ENG-INV-03-05_oracle_run_tested_43731b4f.json
A certification/results/ENG-INV-03-05_oracle_run_head_b142cf8.json
A certification/results/ENG-INV-03-05_resolution_t_ff1af604.json
A certification/results/ENG-INV-06-09_43731b4.json
A MERGE_INSTRUCTION_ENG-INV-01-06.md

No rows outside the six named rows changed. No engine files or secrets are included.

## Schema preservation

EVIDENCE/UI_CERT_ARTIFACT_SCHEMA.md remains present and byte-identical to origin/main (SHA-256 5a555bd8...).

## Suggested review checks (do not merge without approval)

    git fetch origin hermes/eng-inv-rebuild-t_7366969c
    git show FETCH_HEAD:certification/certification_matrix.json
    git show FETCH_HEAD:EVIDENCE/UI_CERT_ARTIFACT_SCHEMA.md
    git ls-remote --heads origin hermes/eng-inv-rebuild-t_7366969c

Only after independent approval should a merge be considered. This card does not authorize merging or pushing to main.
