# RE-ADJUDICATION — the 87 rows citing certification/results/UI_CORRECTION_2d29211.json

Evidence: certification/results/UI_CORRECTION_2d29211.json @ tested_commit 2d29211148c9ba8498bade2d5791ed908f193708
Register of record: origin/cert/local-main-b142cf8 (commit b142cf88d389e791160f691aac3d936852b99975)
Read-only. No matrix edits.

## The standard applied (stated before judging)

A check counts as ROW-SPECIFIC evidence for row X only if it meets BOTH limbs:

1. BINDING - the assertion names X's own element/field/column and would fail if X alone were wrong while the rest of the page stayed correct.
2. BEHAVIOUR - it exercises an observable inside X's stated expected_behaviour (engine/exchange-truth binding, unknown -> n/a/Unavailable fallback, persistence/apply, or error surfacing); not merely the presence of a token anywhere on the page, and not a label compared against the same SSOT source that produced the render.

Failing limb 1 = vacuous. Passing 1 but failing 2 = row-bound structural only, which cannot certify the row. Either way a PASS row is DEMOTEd.

## Re-adjudicated result — 87 rows

| slice | slice verdict | rows | re-adjudicated KEEP | re-adjudicated DEMOTE |
|---|---|---|---|---|
| slice1 (UI-LCC HDR/BTN/GRAPH) | KEEP | 27 | 0 | 27 |
| slice2 (UI-LCC WTBL/POS/EXQ) | DEMOTE | 30 | 0 | 30 |
| slice3 (UI-LCC ADD/AUD/REC) | DEMOTE | 30 | 0 | 30 |
| total | | 87 | 0 | 87 |

- Slice-1 KEEP rows that hold: 0 of 27 — all 27 flip to DEMOTE.
- Of the 60 rows slice2/slice3 already DEMOTED: 0 flip to KEEP. Both prior DEMOTEs were right; slice 1 was wrong. The disagreement resolves entirely in favour of slice 2 / slice 3.
- Category split: 85 rows row-bound structural only; 2 rows not row-bound at all (UI-LCC-ADD-08, UI-LCC-ADD-09).

## Why slice 1 was wrong

Slice 1 counted 'carries per-row checks' as sufficient. Per-row binding is necessary but not enough: every one of its 27 rows is satisfied by an element-existence/tag test or a static default substring. None of the 27 has a check exercising the row's own expected_behaviour from the matrix.

## Concrete examples (actual check text from the artifact)

DEMOTE: UI-LCC-WTBL-01 (slice2).
Matrix expected_behaviour: 'Each value matches engine/exchange truth for that wallet; controls write live_config.json and the engine applies them.'
Checks present:
- UI-LCC-WTBL-01:TABLE_EXISTS pass=true detail `tbody#lcWalletRows not found`
- UI-LCC-WTBL-01:COLUMN_COUNT pass=true detail `Column count mismatch: expected 8, got 8`
- UI-LCC-WTBL-01:COLUMN_HEADER pass=true detail `Header 'Wallet' does not match SSOT 'Wallet'`
All three are existence/count/header-label comparisons. Nothing binds a wallet value to engine or exchange truth; nothing exercises the config-write/apply half of the row. Verdict: DEMOTE.

DEMOTE (was slice-1 KEEP): UI-LCC-HDR-01.
Matrix expected_behaviour: 'Shows engine truth (configured/eligible wallets, auto-send env state, WS health aggregate); unknown -> n/a/OFFLINE, never green.'
Checks present:
- UI-LCC-HDR-01:WALLET_COUNT_ELEMENT pass=true detail `lcWalletCount element not found or wrong tag`
- UI-LCC-HDR-01:DEFAULT_SHOWN pass=true detail `Default wallet count '0 / 10' not found`
The negative test is neg_test('UI-LCC-HDR-01:NO_WALLETS_FALLBACK', '0 / 10' in html) — it asserts the same static substring the positive check already asserted, in the initial state, not the unknown-state fallback. No engine truth is bound. Verdict: DEMOTE.

DEMOTE, not row-bound at all: UI-LCC-ADD-09 (slice3).
Only check: UI-LCC-ADD-09:CANCEL_BUTTON pass=true detail `Cancel button not found`, implemented as check(..., 'Cancel' in html, ...). The token 'Cancel' appears anywhere on the page; the assertion would pass for every other row on this page. Limb 1 fails outright. Verdict: DEMOTE.

## Secondary finding (instrument defect, reported not fixed)

The artifact's check runner prints the detail only on failure (harness.py line 46), yet the stored JSON carries a detail string on passing checks too: 261 checks are pass=true with detail containing 'not found' (73 of them 'does not match'); 334 of 441 total. The detail text is written unconditionally while pass is computed separately, so the detail strings are NOT the evidence for the pass — the boolean is. This is why slice 3's 'vacuous-pass: detail reports not found but pass=True' is a real instrument observation but a misattribution of cause: the defect is in the detail plumbing, not in those assertions. It does not rescue any row (no row here has a behaviour assertion), but any future audit reasoning from detail strings rather than assertion source will produce wrong verdicts. Fix belongs to the harness owner, outside this card's read-only scope.

Also noted: summary.failed_checks = 61, but 0 of those 61 failures fall inside these 87 rows. The 87 rows carry 0 failing checks; they were demoted for insufficiency, not for failure.

## Files

- EVIDENCE/provenance/READJUDICATION_UI_CORRECTION_2d29211.json — per-row {row_id, verdict, standard_applied, why, slice, category, row_bound_checks, page_wide_checks}
- EVIDENCE/provenance/RE_ADJUDICATION_UI_CORRECTION_2d29211.md — this summary
