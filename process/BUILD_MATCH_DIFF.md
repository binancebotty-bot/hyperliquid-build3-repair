# Part A — "Right build?" diff (INVARIANT_COVERAGE_SPEC Part A)

**Scope note (blocker, documented not fabricated):** The spec names three exact paths that do not exist
verbatim anywhere on this machine: `history/evidence/HL_Live_Copy_Service_Core.py.bak_pre_convergence_wiring_20260602`
and `source-docs/hyperliquid-build3-repair/HL_Copy_App_SSOT_20260513.py`. Neither `history/` nor
`source-docs/` exists in this repo, `hl-build3-repair`, or `hl-build3-testnet-cert`. Real substitutes were
located and used instead (documented below) so the comparison is real, not invented.

## Files actually compared

| Spec asked for | Substitute actually used | Why |
|---|---|---|
| `_archive/hl_stage2/HL_Live_Copy_Service_Core.py` (repo main) | same path, this clone, commit `a6e87cda27c00391cd35dab83671cb0280fd5d46` | exact match, no substitution needed |
| `history/evidence/HL_Live_Copy_Service_Core.py.bak_pre_convergence_wiring_20260602` | `C:/Users/wigmore/trading_stack/Hyperliquid scanner/_archive/hl_stage2/HL_Live_Copy_Service_Core.py.bak_pre_convergence_wiring_20260602` | only file on disk matching that exact filename; found by filesystem search, not in any `history/` tree |
| `source-docs/hyperliquid-build3-repair/HL_Copy_App_SSOT_20260513.py` | `git show 91e9980:_archive/hl_stage2/HL_Copy_App_SSOT.py` — commit `91e9980` ("Restore the 13 May Build 3 live screen (HL_Copy_App_SSOT.py), unchanged", 2026-10-09) | that commit message explicitly restores the 13-May file byte-for-byte; it is the real SSOT_20260513 snapshot, pulled from the repo's own git history rather than a missing external file |

## Method

AST-parsed top-level `def`/`async def`/`class` names (not line-by-line) in each of the four files, diffed
old → new by name set. This finds *removed* and *added* functions/classes; it does not prove a kept name's
*behaviour* is unchanged (that needs a line diff per function, out of scope at this deadline — flagged as a
gap below).

## HL_Live_Copy_Service_Core.py: pre-convergence (20260602 bak) → current main

- Old file: 257 top-level defs/classes, 7,705 lines.
- Current file: 438 top-level defs/classes, 11,927 lines.
- **Removed (old had, current lacks): 0.** Nothing named in the pre-convergence snapshot was deleted.
- **Added: 181** new functions/classes, including orphan-order adoption/cancel
  (`_adopt_orphan_order`, `_cancel_orphan_order`, `_adoptable_intent_rows`), liquidation/margin handling
  (`_ensure_margin_mode`, `_follower_projected_liq_px`, `_closes_whole_account_position`), dispatch/locking
  (`_dispatch_fill`, `_coin_lock`, `TimedLock`, `_drain_priority*`), daily-loss and exposure caps
  (`_daily_loss_block`, `_exposure_cap_block`), and outage handling (`_defer_unreadable_truth`,
  `_deferred_loop`).
- **Finding:** no regression by name — the old build's functions all still exist (at minimum by name); the
  current engine is a superset. This does not confirm old *behaviour* survived unchanged inside kept
  functions (e.g. `_dispatch_fill` may have been heavily rewritten under the same name) — that needs a real
  line-level diff per function, not done here under the deadline.

## HL_Copy_App_SSOT.py: 13-May snapshot (git 91e9980) → current main

- Old (13 May) file: 250 top-level defs/classes, 7,243 lines.
- Current file: 280 top-level defs/classes, 8,123 lines.
- **Removed (old had, current lacks): 2**
  - `archive_manual_reconciliation_ledger_row` (public) and `_archive_manual_reconciliation_ledger_row`
    (private twin) — both gone from current main.
  - **Risk flag:** this function name only appears in the Graph Report's "Surprising Connections" section
    referencing `_archive_manual_reconciliation_ledger_row()` → `_post()` in `HL_Copy_App_SSOT.py` →
    `exchange_truth.py` (graphify-out/GRAPH_REPORT.md, built from commit `81c394bd`, now stale vs HEAD
    `a6e87cd`). If manual-reconciliation-ledger archiving was a real feature the 13-May build had and the
    current UI lacks, that is exactly the "feature the old build had that the engine lacks" the spec asks
    to flag. **Not independently confirmed by reading both function bodies at this deadline** — flagged as
    the single highest-value open question for the next pass, not asserted as fact.
- **Added: 32** — mostly UI read-path hardening: paged/cached fills & funding fetch
  (`_fetch_user_fills_paged`, `_fetch_user_fills_cached`, `_fetch_user_funding_paged/cached`,
  `_paged_cache_ident`), dedupe keys (`_fill_dedupe_key`, `_funding_dedupe_key`), incremental CSV reads
  (`_read_csv_incremental`, `_read_csv_tail`), the three-state switch read (`_send_mode`,
  `_master_switch_on`), and a PnL tally/health summary (`_build_pnl_tally`, `_build_health_summary`,
  `_account_card_lines`).

## Answer to "did we revive the build that ran for two months?"

Partial, evidence-bounded answer: by function-name inventory, nothing from the pre-convergence Core was
deleted, and the 13-May live screen lost exactly one paired function
(`archive_manual_reconciliation_ledger_row` / its private twin). Everything else in both old snapshots is
present by name in current main (`a6e87cda27c00391cd35dab83671cb0280fd5d46`). This is **not** proof that
kept functions behave the same — only that nothing was silently deleted. A full line-level behavioural diff
of the ~250–438 shared names is the real next step and was not completed inside the 60-minute deadline.

## Graph freshness note

`graphify update .` was run against this clone before this analysis; the graph (`graphify-out/GRAPH_REPORT.md`)
is now built from HEAD `a6e87cda27c00391cd35dab83671cb0280fd5d46` (127 files, ~352k words, 12 files
unclassified — 11 `.csv`, 1 other). It was consulted for the "surprising connection" above; it was not
sufficient on its own to resolve the removed-function question (graph edges show references, not full
bodies) — grep + AST parsing of the actual files did the real comparison.
