# STATE — the current truth

**Written:** 2026-10-20 08:40 UTC

**THIS FILE WAS STALE FOR TWO DAYS AND ITS GENERATOR NO LONGER EXISTS.** `AGENTS.md` says to regenerate with
`python tools/cert/gen_state.py --write` — **that file is missing**. It was hand-written this once, from the live board and
`origin/main`. Until a generator exists, **update it by hand whenever a standing order changes**, and treat the age above as a warning:
if it is more than a day old, do NOT trust it — check the board and the issue thread instead.

If it disagrees with a comment thread, **the thread wins** until this file is brought up to date.

---

## SUPERSEDED — original standing order FREEZE (Boss ruling 6285500040, 07:12Z 2026-10-20)

> **Status: NO LONGER IN FORCE, as of ~19:40Z 2026-10-20.** Kept verbatim below for the record only.
> The controller (Claude) subsequently issued overnight fan-out and merge authority (`6298184108`, `6298280292`) and
> named specific engine branches (`6299368113` dust / `no-sub-minimum-positions`, `6299692364` MO#6 override fix),
> and the operator pre-authorised all controller instructions for this session. Work on those named branches is
> authorised. What still does NOT happen is unsolicited register/decision/review sprawl.

**The certification register work is a sprawl and it has ENDED.** No new register, evidence, mutation-control, decision-table or review
cards. No new engine branches beyond those named below. Park every other card. **The board being idle is CORRECT — do not refill it.**
It was refilled in error once already (8 cards at 08:25, all archived).

**The only authorised work:**

1. **The sleeve/exit fault** — exits were sent with `reduce_only=false` on a margin-exhausted account, so they were rejected and sleeves
   stayed open. Fix `t_65bc408d` (`e0a8017`) is **DELIVERED and verified**: `pure_reduce` is true only when the exit opposes the existing
   position AND its size does not exceed it, so it cannot flip the position. Mock proves an accepted send at `reduce_only=True` with
   `withdrawable=0`; revert control makes the test fail. Artifact in `worker_patches/t_65bc408d/`. **Gap:** the full Core self-test never
   reaches that assertion — it aborts earlier on an unrelated `ENTRY_SAFETY_*` failure.
2. **The two-month engine as reference** — `HL_Live_Copy_Service_Core.py` at 7,705 lines from `.bak_pre_convergence_wiring_20260602`
   (sha `5bda57be…`). Read-only comparison against the current `_close_wire_plan`. Port nothing else. `PORT_VS_REBUILD.md` covers this but
   was written by deepseek-flash, not Codex as the ruling specified — a draft until a Codex pass exists.
3. **Push route** — needs Boss's one-time GitHub sign-in on the PC. **Human-only gate.**

After the push works: merge `t_65bc408d`, restart once, read the exit-fill share against the **3-of-690** baseline. Everything else waits.

## Board

```
archived 977 · done 614 · running 0 · ready 0 · todo 0 · blocked 0 · triage 0
```

Idle by design under the freeze.

## The register

Register of record — `origin/main`: **PASS 59 · FAIL 107 · BLOCKED 12 · NOT_TESTED 654 · total 832**

An earlier version of this file claimed `origin/main` was a stub with every row `NOT_TESTED` and 0 evidence refs. **That was wrong**, and
it cost real work — cards were refused because workers "saw" a stub. Verify with
`git show origin/main:certification/certification_matrix.json`.

Of the 654 `NOT_TESTED`, 208 carry an open decision (OD-05…OD-24) and cannot be verdicted until ruled. Moot while the freeze stands.

ENG-INV: 01 NOT_TESTED · 03 FAIL (psutil undeclared; controller ruled remove) · 07 FAIL (REDO delivered `ISOLATION_PROVEN`, review
outstanding) · 08 BLOCKED · 09 BLOCKED · 10 NOT_TESTED. **All frozen.**

## The alert-only fact that outlives the freeze

`HL_LIVE_GATES_ALERT_ONLY` defaults to **`True`**. Every cycle gate writes one `GATE_WOULD_BLOCK` row and then **allows the entry**; only
`DAILY_LOSS_LIMIT_REACHED` is a hard stop. Requirements of the form "the engine blocks X" therefore cannot pass by testing alone — the
requirement and the policy disagree. Unresolved; needs a ruling when work resumes.

---

## Superseded detail (kept for lineage — do not act on it)

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
