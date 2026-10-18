# STATE — the current truth

**Generated:** 2026-10-18 18:31 UTC  
**This file is derived and overwritten.** Do not append to it; do not hand-edit facts into it.  
If it disagrees with a comment thread, **this file wins**.

Regenerate: `python tools/cert/gen_state.py --write`

---

## The register

Register of record — `origin/cert/local-main-b142cf8`:

| result | rows |
|---|---:|
| PASS | 579 |
| FAIL | 76 |
| BLOCKED | 13 |
| NOT_TESTED | 122 |
| **total** | **790** |

Rows carrying an `evidence_ref`: **668** of 790

`origin/main`: 832 rows, results {'NOT_TESTED': 832}, **0 evidence_refs**
→ **THIS IS A STUB.** Anything reading `main` sees every row as unproven.

## The position, stated honestly

**74 rows are audit-verified.** That is the number to quote. The register's PASS count is a *claim* count; audits demoted 301 rows because their evidence was not row-bound, and 201 were never audited at all.

Zero UI rows are certified. UI evidence needs rebuilding from scratch, not auditing — the existing checks would pass for any row.

## Board

| status | count |
|---|---:|
| running | 16 |
| ready | 30 |
| todo | 42 |
| review | 4 |
| blocked | 10 |
| triage | 4 |
| done | 317 |

## Lanes (running / measured ceiling)

| lane | running | ceiling |
|---|---:|---:|
| custom-deepseek-free | 0 | 3 |
| openai-codex | 0 | 4 |
| gemini | 5 | 4 |
| openrouter | 6 | 2 |
| nous | 4 | 3 |

## Blocked — each must name its blocker

- `t_4e3d93f0` CERT 2/53 [gemini] ENG-SEM-B2..ENG-012 (15 rows)
- `t_6c568cbd` MERGE ENG-INV-01..06 to main [deepseek:v4-flash] - gated on 
- `t_931d2d8d` CONTROL-WRITE test [gemini] UI-LCC rows against isolated :80
- `t_3de80923` REDO RTT [gemini] measure a REAL order interval — decomposit
- `t_8c9cbd7b` REDO [openrouter] CERT17 rows evidence failures — independen
- `t_6ba55115` FIX UI-WALLET-003/012 catch-up replay and invalid payload pe
- `t_f46232c3` REVIEW [openrouter] REDO t_bb3dfa77 UI-LCC-REC-04/06/07 + AU
- `t_c605428f` REDO [openrouter/nemotron] NET-004/006/007, HEALTH-001..004,
- `t_56d9c96c` REVIEW [gemini] REDO TN-F04 runtime evidence
- `t_0a0a5f32` REVIEW [gemini] REDO CERT 30/53 evidence-anchor corrections 

## Recently completed

- `t_b0df04df` REDO [free DeepSeek] TN-F04 - reviewer rejected: harness unexecuted
- `t_bb3dfa77` REDO [openrouter] UI-LCC-REC-04/06/07 + AUD-11/13 - reviewer rejected:
- `t_bd28ad9b` REVIEW [gemini] UI schema placed on shared base
- `t_45c1e992` PLACE UI_CERT_ARTIFACT_SCHEMA on the shared base [deepseek:v4-flash] —
- `t_91325124` REVIEW [nous] REDO t_91949b78 UI-SSOT-TBL-13..PAGE-02

---

## Open items needing a human or another agent

- **J15 / merge** — the register must reach a ref that is not a stub before anything downstream is certifiable.
- **`:8032`** — an isolated instance is required before the control-write test can run; it has never landed.
- **ENG-INV-02** — two reachable order sites. The merge stays held on this.
