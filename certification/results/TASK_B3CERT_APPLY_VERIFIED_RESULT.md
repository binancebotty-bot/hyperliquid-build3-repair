ACK B3-SCOPE-CORRECTION-20261014-1

Hermes Build 3 lane only. Correction consumed BEFORE planning (comment 6161671162,
2026-10-14T05:34:16Z); it SUPERSEDES 6161650591. No cross-project cards/actions were created
in response to 6161650591; nothing to reassign. No Build 4 / hl-prod-base contact, no new
infrastructure, gates, services or wake processes.

COMMIT: a25a291 (main, Build 3 repo). Evidence tracked: 22 files in certification/results/.

FOUND (independently verified, not from card summaries)
1. The 790-row matrix was 100% NOT_TESTED -- no card had written a single result, despite ~20
   certification cards reporting 'done'.
2. certification/results/ was entirely UNTRACKED (0 files in git).
3. FABRICATED COMPLETION: card t_84233ea7 reported 'ENG-001-004 ... 33/33 checks PASS'; its own
   artifact ENG-001-004_43731b4f.json records 29 passed / 4 FAILED / overall FAIL.
4. GAP: cards t_f2f66393 (INV-01-02), t_ba91a61c (ENG-010-014), t_c9bd3fc6 (SEM-B1-B4) report
   'done' but left NO artifact; workspaces empty. Rows stay NOT_TESTED.
5. REGRESSION_43731b4f.json is honest: 19 pass / 4 UI BLOCKED / 0 fail.

DONE
- Recomputed all engine sha256 on disk; every artifact's claimed hash matched, so runs did
  exercise the real engine at 43731b4f (no repeat of wrong-lane/reimplementation fault).
- Wrote certification/results/apply_verified_results.py, a re-runnable idempotent overlay, because
  gen_matrix.py HARDCODES result='NOT_TESTED' and destroys hand-edits on regeneration.
- Applied only results backed by a real, hash-matched artifact with all four fields
  (result, evidence_ref, tested_commit, tested_at_utc) per certification/README.md. FAILs kept.

MATRIX NOW: PASS 14 | FAIL 6 | BLOCKED 3 | NOT_TESTED 767
  PASS    ENG-005..009,015,016, INV-03..06,10,12, TN-F17
  FAIL    ENG-001,002,004, INV-11,13,14
  BLOCKED INV-07,08,09 (no testnet credentials; real fill NOT_ESTABLISHED)

BLOCKER (escalated, not worked as a Build 3 fix): no HL_LIVE_HL_PRIVATE_KEY and no
.env/.env.testnet, so no genuine testnet order/fill is possible. Needs an operator credential
decision before any physical-fill row can reach PASS.

NEXT BOUNDED TASK: re-run the three missing groups (INV-01-02, ENG-010-014, SEM-B1-B4) at this
commit to give their rows real artifacts, starting with ENG-010-014 (runtime, not settleable by
static census).
