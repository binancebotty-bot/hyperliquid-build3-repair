# PASS-row audit consolidation (register b142cf88)

Read-only arithmetic over the immutable register snapshot `b142cf88` and four cited audit commits. This is a partial, not complete, surviving-PASS count because UI audit parts 1/4 and 4/4 are missing.

| Measure | Count / value |
|---|---:|
| Register rows | 790 |
| Register PASS | 579 |
| PASS rows covered by these audits | 385 |
| PASS rows not covered | 194 |
| Demoted occurrences | 147 |
| Demoted unique row IDs | 147 |
| Demoted rows still marked PASS in immutable register | 147 |
| Partial surviving PASS | 579 − 147 = 432 |
| Partial surviving / all rows | 432 / 790 = 54.68% |
| Partial surviving / register PASS | 432 / 579 = 74.61% |

| Audit commit | Scope / reported result | Demotions |
|---|---|---:|
| `8b8c114` | REGRESSION + CONTROL (reported 81 demotions among 183 PASS rows) | 81 |
| `9a7ae8d` | UI part 2/4 (row range UI-LCC-REC-05–UI-SSOT-PAGE-05); 55 kept | 23 |
| `e99b288` | RISK + WALLET + SETTLE + LIFECYCLE (46 PASS rows); 32 kept | 14 |
| `3a78996` | UI part 3/4 (row range UI-SSOT-PAGE-06–UI-FP-085); 49 kept | 29 |

Coverage gap: only UI parts 2/4 and 3/4 landed; parts 1/4 and 4/4 did not appear in the committed audit history examined. The uncovered 194 PASS rows comprise UI 158, ENGINE 25, NETWORK 7, and HEALTH 4. Therefore 432 is the arithmetic survivor count after the 147 unique demotions found, but it is not a complete project-wide count.

All 147 demoted IDs still read `PASS` in the immutable register at `b142cf88`; this is a snapshot-status mismatch by design of the read-only audits, not a register mutation. See the companion JSON for the full deduplicated ID list and audit SHA values.
