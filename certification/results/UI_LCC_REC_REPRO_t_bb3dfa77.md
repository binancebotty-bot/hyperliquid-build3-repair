# UI-LCC recon rows: how every ratio in this batch was produced

Task t_bb3dfa77 (redo of a56b8eb after review t_228fe60f).
Probed instance: PID 26592, started 2026-10-18T10:33:44Z, cwd
`C:/Users/wigmore/trading_stack/hl-build3-testnet-cert-j28-89b3bc7/_archive/hl_stage2`,
serving HEAD 89b3bc7 (confirmed `git rev-parse HEAD` in that repo). NOT the
33368 process cited by the original a56b8eb evidence.

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

Measured here (`snapshot_drift_control`): the payload is not stable between
reads. Drift is intermittent - in one 2.6s window 0 of 50 manual values
changed; the 35s drift probe produced different byte hashes with no row value
changed. So a cross-snapshot join lands anywhere between 50/50 and 41/50
depending on when it was taken. The number is a property of fetch timing, not
of the render.

`cross_snapshot_ratio` per row shows exactly that, and it is not a one-off:
REC-06's keyed cross-check read 0/50 on one run and 50/50 on another of the
same code against the same server - the same DOM, a different second fetch.
That is the demonstration, not an anecdote.

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

## A bug this run found and fixed

`keyed_hits` built a 3-tuple key (`coin, wallet, side`) while reading only 2
DOM cells, so the third component never matched and REC-06's keyed cross-check
silently scored 0/50. The `side` component is embedded in the ledger cell
("SHORT -414"); the helper now takes it from the front of that cell. Same class
of silent-zero defect the reviewer was right to distrust - which is why every
check now carries an explicit comparator control that is proven to flip.
