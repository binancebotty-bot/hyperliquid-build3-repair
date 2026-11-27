# Lane C Testnet Symbol Eligibility Results

## Old and new eligibility

| State | Explicit symbols | Eligibility rules |
| --- | --- | --- |
| Old | Fixture blocklist: `SOL` | Volume threshold of USD 10,000 24-hour notional; entry blocked when the L2 book is one-sided or empty. |
| New | `BTC ETH SOL NEAR DOGE AVAX PUMP BNB ME SUI INIT AAVE XMR kPEPE ARB ADA OP ZRO PAXG INJ TIA` | Explicit allowlist from the supplied derived snapshot. No volume check or one-sided/empty-book block. Delisted and other unlisted assets are excluded. |

The supplied snapshot covers 213 assets, including 54 delisted, and identifies these 21 live assets above the USD 10,000 24-hour notional threshold. In this checkout, the archived engine has no per-market volume eligibility check; the volume criterion is represented by the supplied allowlist. The entry L2 book guard was present and is disabled.

## Tests first / base expectations

- `_archive/hl_stage2/test_g2_blocklist.py::TestnetSymbolEligibilityTests::test_live_testnet_allowlist_excludes_delisted_or_unqualified_assets` - should fail on the base because the fixture has no symbol allowlist and still blocklists `SOL`.
- `_archive/hl_stage2/test_g2_blocklist.py::TestnetSymbolEligibilityTests::test_one_sided_or_empty_book_does_not_block_entry` - should fail on the base for `(1, 0)`, `(0, 1)`, and `(0, 0)` book-side counts.

Both tests were added before the implementation edits. Per the instruction not to run Python or interpreters, neither test nor any other test was executed; these base failures are reasoned from the original code, not observed test output.

## Changes

- `_archive/hl_stage2/HL_Live_Copy_Service_Core.py` - `_one_sided_book_block` now returns no block.
- `tools/cert/fixtures/live_config_copy.json` - replaces the old `SOL` blocklist with the 21-symbol allowlist and an empty blocklist.
- `_archive/hl_stage2/test_g2_blocklist.py` - covers the allowlist, exclusion of unlisted/delisted assets, and one-sided/empty books.

## Verification and commit

- Tests not run: Python and interpreter execution were prohibited by the task.
- `git diff --check` passed. The installed Git executable reported the four intended files as the only changes.
- Local commit not created: Git could not create `.git/index.lock` (`Permission denied`) while staging. No push was attempted.
