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

## Coordinator verification (2026-11-27)

HEAD: 96a1894c

Command: `python -m pytest -q -p no:cacheprovider _archive/hl_stage2/test_g2_blocklist.py _archive/hl_stage2/test_core_one_sided_book_and_close_fault.py`
Result: 17 passed, 24 subtests passed.
Note for review: this lane removes the one-sided/empty book entry guard and replaces the blocklist with a 21-symbol allowlist. That is a trading-behaviour change and needs independent review before any mainnet consideration.

## CRLF and whitespace normalization (2026-11-27)

Root cause: the flagged branch additions used CRLF line endings, which Git reported as trailing whitespace on added lines; `LANE_RESULTS.md` also had trailing whitespace and a blank line at EOF. Normalized the 12 files flagged by `git diff --check origin/main` to LF and removed line-end spaces. No test assertions or logic were changed.

Files changed: `_archive/hl_stage2/HL_Copy_App_SSOT.py`, `_archive/hl_stage2/HL_Live_Copy_Service.py`, `_archive/hl_stage2/test_core_one_sided_book_and_close_fault.py`, `_archive/hl_stage2/test_core_ratelimit_gate.py`, `_archive/hl_stage2/test_core_v13_cancel.py`, `_archive/hl_stage2/test_send_mode_resolver_parity.py`, `_archive/hl_stage2/test_single_exchange_order_callsite.py`, `_archive/hl_stage2/test_ui_send_mode_controls.py`, `EVIDENCE/handoff_wave50/capfix-a_green.txt`, `EVIDENCE/handoff_wave50/capfix-a_red.txt`, `EVIDENCE/handoff_wave50/capfix-a_test_raw.txt`, `LANE_RESULTS.md`.

Commands and results:

- `& 'C:\Users\wigmore\AppData\Roaming\uv\python\cpython-3.12.13-windows-x86_64-none\python.exe' 'C:\Users\wigmore\WINAGENT-HERMES BRIDGE\graphify_query.py' 'test_core_one_sided_book_and_close_fault CRLF trailing whitespace'`: no matches. Repeated with query `one_sided_book`: no matches. The checked-in graph report identifies its corpus as `b3-main`, built at commit `81c394bd`, so it did not contain this lane's test node.
- `& 'C:\Users\wigmore\AppData\Roaming\uv\python\cpython-3.12.13-windows-x86_64-none\python.exe' -m pytest -q -p no:cacheprovider _archive/hl_stage2/test_g2_blocklist.py _archive/hl_stage2/test_core_one_sided_book_and_close_fault.py`: unavailable; this Python has no `pytest` module.
- Before formatting: `& 'C:\Users\wigmore\AppData\Roaming\uv\python\cpython-3.12.13-windows-x86_64-none\python.exe' _archive/hl_stage2/test_g2_blocklist.py` gave 2 passed; the same command with `_archive/hl_stage2/test_core_one_sided_book_and_close_fault.py` gave 14 passed and 1 error (15 tests run).
- After formatting, the same two script commands gave 2 passed; 14 passed and 1 error (15 tests run). The single error is `test_book_fetch_counts_levels`: `c.requests` is `None`, because `requests` is not installed in the available runtime.
- `$env:UV_CACHE_DIR = Join-Path (Get-Location) '.uv-cache'; uv run --python 'C:\Users\wigmore\AppData\Roaming\uv\python\cpython-3.12.13-windows-x86_64-none\python.exe' --with pytest --with requests python -m pytest -q -p no:cacheprovider _archive/hl_stage2/test_g2_blocklist.py _archive/hl_stage2/test_core_one_sided_book_and_close_fault.py`: blocked because network access to PyPI is denied (socket error 10013).
- `git diff --check`: clean. `git -c diff.external= diff --no-ext-diff --check origin/main`: clean.

Counts: the coordinator verification above records 17 passed before this formatting task. In this checkout's available runtime, the direct-script count is unchanged before/after at 16 passed and 1 error. Blocker: local verification of all 17 passing requires `pytest` and `requests`; neither is installed, and package download is blocked by network policy.
