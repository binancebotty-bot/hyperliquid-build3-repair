# J15 Register Re-Projection (read-only)

Refs: `origin/cert/local-main-b142cf8` = `b142cf88d389e791160f691aac3d936852b99975`; `origin/main` = `3ea99f4d912b329cdd248fe068bede93a6d8bc80`.

## 1. Row reconciliation

| | rows |
|---|---|
| cert branch | 790 |
| main | 832 |
| shared ids | 790 |
| cert-only | 0 |
| main-only | 42 |
| merged union | 832 |

Working: 790 cert + 42 main-only = 832; union of ids = 832. **The earlier 832 figure is CONFIRMED.** The cert id set is a strict subset of main; there are no cert-only rows.

Matrix sha256: cert `86b2237fe95f88ca9eb758fb42ddbdf3efdaef71e56f79a10e2d2635f44f341a`, main `5202a4b4f4da0ef34285ca1e38d535282a8e2365ba130df18b92178c43c422e7`.

## 2. PASS resolvability against the cert branch

| measure | count |
|---|---|
| PASS rows on cert | 579 |
| fully resolvable | 579 |
| missing evidence file | 0 |
| unresolvable tested_commit | 0 |
| distinct evidence_ref | 14 |
| distinct tested_commit | 5 |

All five tested commits (`43731b4f`, `fa9d9f55`, `2d29211`, `fefc2b04`, `2a269ad2`) resolve to commit objects in this repo.

## 3. Evidence files

The cert branch carries 68 files under `certification/results/`; the PASS rows cite 14 distinct ones and **all 14 are present on the cert branch**. Missing: none.

## 4. Merged projection

| result | rows |
|---|---|
| PASS | 579 |
| FAIL | 76 |
| NOT_TESTED | 164 |
| BLOCKED | 13 |
| **total** | **832** |

Composition = cert-branch verdicts on the 790 shared rows + the 42 main-only rows, all of which are NOT_TESTED on main. Demotions: none (0 non-resolvable PASS rows).

Shared-row drift is one-way: 668 shared rows are NOT_TESTED on main and carry a verdict on cert (579 PASS / 76 FAIL / 13 BLOCKED); 122 shared rows are NOT_TESTED on both. No row regresses.

Schema drift: main rows carry an extra `proof_network` key that cert rows do not.

Assumptions: row identity = record `id`; resolvability = evidence file presence on the cert branch + `tested_commit` object existence; no verdict re-probe; merged count = union of ids.
