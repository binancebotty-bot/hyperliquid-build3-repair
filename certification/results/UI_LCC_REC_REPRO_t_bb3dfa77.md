# UI-LCC recon rows: how every ratio in this batch was produced

Task t_bb3dfa77 (redo of a56b8eb after review t_228fe60f).
Probed instance: PID 26592, started 2026-10-18T10:33:44Z, cwd
`C:/Users/wigmore/trading_stack/hl-build3-testnet-cert-j28-89b3bc7/_archive/hl_stage2`,
serving HEAD 89b3bc7 (confirmed `git rev-parse HEAD` in that repo; commit date
2026-10-17T07:18:14Z, i.e. the commit predates the process start). NOT the 33368
process cited by the original a56b8eb evidence. `_serving_process.json` records
the PID, start time, exe, cmdline and cwd actually probed.

## The one structural point

The page refreshes only on load/click. It renders whatever
`/api/live-audit-summary` returned at its own load. So the only join that can
say anything about *the page* is DOM-vs-the-body-that-page-received. A payload
fetched by the reviewer afterwards is a different snapshot of a book that moves
between reads, and any ratio computed against it measures the gap between two
reads, not the correctness of a cell.

This probe scores against the payload captured from inside the page
immediately after render, and records the cross-snapshot number as an
**unscored control**, so the reviewer's figures can be explained rather than
argued about.

## Scoring rule (changed this run)

All three reconciliation comparisons are scored with a **keyed join on
(coin, short_wallet, side)**, per the review directive that an unkeyed or
positional comparison is a defect regardless of the number it produces.
Positional zip is still computed and stored as `positional_ratio`, but it is a
cross-check only and never decides a verdict.

On this capture REC-04, REC-06 and REC-07 are **50/50 keyed**, with 0 duplicate
source keys and identical row order.

## Reproducing

    py311 -m py_compile certification/results/ui_lcc_rowbound_probe.py
    py311 certification/results/ui_lcc_rowbound_probe.py

Writes:
* `UI_LCC_AUD_REC_WS_8031.json` - verdicts, per-check ratios, and
  `snapshot_drift_control`
* `UI_LCC_AUD_REC_WS_01_verdicts.json` - one row per check, each with `probe`
* `UI_LCC_AUD_REC_WS_capture_t_bb3dfa77.json` - the raw inputs: the 50 source
  rows, the 50 rendered rows, and the 2.6s-later re-read

Helpers, all committed, all operating on that same capture:
* `joins_t_bb3dfa77.py` - positional and keyed joins, plus the failing rows
* `crosssnap_t_bb3dfa77.py` - same DOM against a live re-read
* `drift_probe_t_bb3dfa77.py` - how much the payload moves over 35s
* `coinagg_t_bb3dfa77.py` - proves `exchange_signed_size` is per-coin

## Why the reviewer saw 48/50 and 41/50

Same DOM, a later fetch, a worse number. In the run committed here:

| row | keyed (same snapshot) | positional | cross-snapshot |
|-----|----------------------|------------|----------------|
| REC-04 | 50/50 | 50/50 | 50/50 |
| REC-06 | 50/50 | 50/50 | 49/50 |
| REC-07 | 50/50 | 50/50 | 46/50 |

`snapshot_drift_control` records the mechanism: within that 2.6s window 1 of 50
manual values and 4 of 50 exchange values changed, while `issue` did not change
at all - and REC-04, the issue column, is the one that stayed 50/50. Drift is
intermittent: an earlier window over the same code and server showed 0 of 50
manual values changed, and the 35s drift probe produced different byte hashes
with no row value changed at all. So a cross-snapshot join lands anywhere
between 50/50 and 41/50 purely on fetch timing. The reviewer's 48/50 and 41/50
are that effect at a longer gap, not cell mis-binding.

## What is genuinely wrong, and survives every join

1. REC-11 FAIL on its own evidence: the column is headed `Action`,
   `action_available` is false on all 50 rows, and every cell instead carries
   the source `count` (50/50). The count evidence is the load-bearing half;
   with the flag false everywhere, "renders the flag" and "renders nothing"
   are indistinguishable.
2. REC-02/03 FAIL: Wallet and Coin are transposed against their headers.
3. REC-05/08/09/10 FAIL: Count, Last intent, Last oid, Last updated are
   absent; the count renders under Action.
4. `exchange_signed_size` is a **per-coin** quantity in the source - 14/14
   coins carry one value across every wallet row holding them. When a coin
   moves, its whole row group moves together, which is the shape of the
   reviewer's "every APT row says 19.95" observation. Whether the field
   *should* be per-coin is a source-design question, out of scope here -
   flagged, not scored.

## Two checks that are weaker than PASS suggests

REC-01 and AUD-12 are PASS, but both predicates are one-sided on today's
payload: every `severity` is `INFO` and every rendered note happens to match,
so neither can distinguish a correct mapping from a constant. AUD-12 further
cannot be re-measured at all here (`last_rows=[]`), and is kept PASS on
construction only. Read both as "no counter-example found", not "proven".

## Two silent-zero bugs found and fixed in this run

1. `keyed_hits` built a 3-tuple key (`coin, wallet, side`) while reading only 2
   DOM cells, so the third component never matched and REC-06's keyed
   cross-check silently scored 0/50.
2. The first fix then read the embedded `side` from the field's own cell, so
   REC-04 (issue column) and REC-07 (exchange column) still scored 0/50 while
   REC-06 passed - a bug that looked exactly like a finding. `side` is the
   first token of the ledger column whatever field is being checked.

Both were caught by recomputing the join over the committed capture instead of
trusting the verdict. Every check now carries an explicit comparator control
proven to flip, so a silent zero cannot pass as a result.
