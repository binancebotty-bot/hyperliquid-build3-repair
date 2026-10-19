# REGISTER OF RECORD — read it from the right ref

**`origin/main`'s matrix is a STUB. Do not certify against it.**

    origin/main                      832 rows    6 PASS, 826 NOT_TESTED   <- stub, no evidence refs
    origin/cert/local-main-b142cf8   790 rows  579 PASS, 76 FAIL, 13 BLOCKED, 122 NOT_TESTED  <- THE REGISTER

Verified 2026-10-19 by reading both refs:

    git show origin/main:certification/certification_matrix.json | ...
    git fetch origin cert/local-main-b142cf8
    git show origin/cert/local-main-b142cf8:certification/certification_matrix.json | ...

## Why this matters

A worker that clones the repository and reads `certification/certification_matrix.json` from `origin/main` sees **every
row as NOT_TESTED**. It then reports, correctly, that the rows it was asked to earn are already NOT_TESTED and that the
task brief ("4 rows are FAIL") does not match the tree. That refusal is right, and it has happened repeatedly.

The rows are not untouched. Their verdicts live on the cert branch. The defect is that the register of record has never
been merged onto `main`.

## The rule

When a card asks you to check a row's **current verdict**, read it from the cert branch:

    git fetch origin cert/local-main-b142cf8
    git show origin/cert/local-main-b142cf8:certification/certification_matrix.json > /tmp/register.json

Then read `records[]` for your row ids. Do not conclude "the row is NOT_TESTED" from `origin/main` alone.

## The other rule, unchanged

When a card asks you to **test code**, test the code at `origin/main` (or the commit the card names). The stub is a
problem with the *register*, not with the *engine* — the engine on `main` is current, and 5dddc8e2 carries the
single-instance guard and the O1 ordering fix.

So: **verdicts from the cert branch, code from main.** Both, every time, and say which you used in your artifact.

## Open question for the controller

Merging the cert register onto `main` would remove this trap entirely — it is the same "unmerged work" problem that
keeps PASSes invisible. Until that happens, this document is the workaround, and every card must carry it.
