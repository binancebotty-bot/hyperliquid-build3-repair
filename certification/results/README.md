# Retired result overlay

`apply_verified_results.py` used to be described as “the durable record” and operators were told to re-run it after matrix regeneration. That wording is withdrawn. It is a **stale historical map**, not the producer of the committed matrix.

Verified at base `c63d2299` (read-only; the overlay was not run against the tracked matrix):

- The literal map `V` has **672 entries: 582 PASS / 77 FAIL / 13 BLOCKED**. It reads no evidence files.
- The committed `certification_matrix.json` has **832 records: 54 PASS / 105 FAIL / 11 BLOCKED / 662 NOT_TESTED**. Commit `c63d2299` withdrew five unsupported PASS rows, so the earlier-quoted 59 PASS / 657 NOT_TESTED is stale.
- Applied in a scratch copy at this base, the map moves the matrix to **604 PASS / 76 FAIL / 13 BLOCKED / 139 NOT_TESTED** (the hazard report quoted 579/76/13/164 on an earlier matrix). It changes **552 of 832** result fields: 521 NOT_TESTED→PASS and 29 FAIL→PASS=*** manufactured PASS rows.

**Never run it as a pipeline step.** The implementation is retained at `_retired/apply_verified_results.py` purely as audit history. It refuses by default; the only bypass is `APPLY_VERIFIED_ALLOW_FABRICATION=1` in a scratch copy.
