# Retired result overlay

`apply_verified_results.py` was documented as “the durable record” and instructed operators to rerun it after matrix regeneration. It is a retired historical map, not the producer of the committed matrix. Its 672-entry literal mapping has no evidence-file input: it contains 582 PASS, 77 FAIL and 1 NOT_TESTED entries. Applying it would move the committed matrix from 59 PASS / 105 FAIL / 11 BLOCKED / 657 NOT_TESTED to 579 PASS / 76 FAIL / 13 BLOCKED / 164 NOT_TESTED, matching only 255 of 832 results.

The script is quarantined because these mapped verdicts are not verified by the tool. **Never run it as a pipeline step.** The implementation is retained at `_retired/apply_verified_results.py` for historical inspection; refusal can only be bypassed with `APPLY_VERIFIED_ALLOW_FABRICATION=1`.
