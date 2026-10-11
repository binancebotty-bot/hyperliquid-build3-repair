# Part B — every rule and incident: record + test? (INVARIANT_COVERAGE_SPEC Part B)

**Scope note (blocker, documented):** The spec's sources list `INC-01..INC-18` as the incident ID scheme and
`source-docs/hyperliquid-build4/{FAILURES.md,GUT_CONTRACT.md,NO_SEND_GATE.md}`,
`source-docs/local-trading/Hyperliquid scanner/LIVE WALLET TRADING/{...}`, and `history/BUILD_HISTORY_REVIEW.md`
as sources. None of those exact paths exist on this machine (no `source-docs/`, no `history/` tree anywhere
under `trading_stack`), and **no `INC-NN` identifier exists anywhere in this filesystem** (checked by regex
across `FAILURES.md`/`GUT_CONTRACT.md`/`NO_SEND_GATE.md`/`AGENTS.md`/`CLAUDE.md` in every build3/build4
location found, plus a filename search — zero hits).

**This absence is itself a Part-B finding, not a failure to search harder:** the project does not actually
use an `INC-NN` incident ledger. It uses a different, real, already-operating taxonomy —
prefixed codes (`ENG-`, `ORD-`, `PRICE-`, `NET-`, `SET-`, `RISK-`, `UI-TRUTH-`, `UI-ROUTE-`) recorded live
per testnet run in `certification/run_results.json` and cross-referenced by row number in
`process/CERTIFICATION_MATRIX_2026-10-10.md` (the spec asked for `_2026-10-11`; the most recent one that
exists is dated `_2026-10-10` — used as-is, one day off, not recreated).

Files actually used as "rule/incident" sources (substitutes, found by filesystem search, not invented):

- `C:/Users/wigmore/trading_stack/build4-github-mirror/{FAILURES.md,GUT_CONTRACT.md,NO_SEND_GATE.md}` (Sep 25, newest Build-4 copy found)
- `C:/Users/wigmore/trading_stack/Hyperliquid scanner/LIVE WALLET TRADING/{FAILURES.md,NO_SEND_GATE.md,AGENTS.md,CLAUDE.md}` (matches the spec's named path exactly, just without the `source-docs/local-trading/` prefix)
- `hl-build3-hermes-IC/certification/run_results.json` + `process/CERTIFICATION_MATRIX_2026-10-10.md` (this clone)
- `hl-build3-testnet-cert-evidence/{RUN1_FINDINGS.md,run3/RUN3_FINDINGS.md,run4/RUN4_FINDINGS.md,run5/RUN5_FINDINGS.md}`

## Table — every incident code actually found, cross-referenced

| id | one-line statement | matrix row # | test exists? | status |
|---|---|---|---|---|
| ENG-006 | 268-perp-DEX sequential reads too slow for one `--once` cycle in 120s | row 1 | Y — `test_core_dex_scope_and_ui_truth.py` S2/S5/S6 | COVERED (mock only — never re-run live on current main) |
| PRICE-001 | allMids refresh across all DEXes took ~140s; every mid >5s, no entry priceable | row 2 (+row14) | Y — `test_core_network_and_global_controls.py` F1-F3/R1/R3 | COVERED (mock only) |
| NET-003 | leader-mainnet / follower-testnet separation holds at the first order | not an explicit row (concept covered under row 12's N1-N4 tests) | Y, indirectly — `N1_DEFAULT_LEADER_MAINNET_FOLLOWER_TESTNET` etc. | ROW-NO-TEST (id itself never cited in the matrix; functional overlap only) |
| NET-004 | pre-existing mainnet orders/positions never touched by a testnet-follower run | rows 12 & 13 | Y — `N1-N4`, `G1_MAINNET_FOLLOWER_REFUSED...`, `test_core_adopt_oid.py P2/F7` | COVERED (mock + a stale live PASS on `ab7f2b0`, not re-run on current main) |
| ENG-016 | mainnet leftovers (orders/positions) untouched (named explicitly in matrix row 13 title) | row 13 | Y — same as NET-004 | COVERED |
| ORD-001 | every exchange order id matches an engine send attempt; no unknown orders | no row | not named in any row's test list | MISSING — live PASS on `ab7f2b0` only, no dedicated mock test cited |
| ORD-005 | exactly-once send; duplicate leader fills blocked pre-send | row 6 | Y — `test_core_r1_cursor.py`, `test_g4_intake_sleeves.py`, `test_t1a_cloid_pending_row.py` | COVERED (mock; live PASS stale on `ab7f2b0`) |
| ORD-009 | no startup check that the signer is approved on the follower network; real rejections got miscategorised | no row | not found in any row's test list | MISSING |
| ORD-010 | leader→send delay (one send worker) rose 7s→81s under load, no stale-entry cutoff | row 14 (regression list) | Y, by inclusion — `test_core_run3_fixes.py`/`run4_fixes` cited generically for "past-incident regressions" | COVERED (mock-only, generic regression bucket, not a named check) |
| SET-009 | ledger (`live_fills.csv`) diverged from the real exchange fill count | row 14 | Y, generic — `test_core_ledger_repair.py`/`run3_fixes` | COVERED (mock-only) |
| ENG-018 | a short that flattened a different wallet's long wasn't reflected in the ledger before Boss's netting ruling | row 14 | Y, generic | COVERED (mock-only) |
| ENG-019 | main loop budget-exceeded loop re-processed thousands of duplicate fills, starving copy-account poll | row 14 | Y, generic — `test_core_run4_fixes.py` | COVERED (mock-only) |
| RISK-004 | no order over the $50 max-order cap | no row | not named in any row | MISSING |
| UI-TRUTH-001 | front page showed wrong equity/tracked-wallet-count/mode | row 14 (listed explicitly) | Y — `test_live_screen_truth.py`, `test_screen_run4.py` (cited in the test-suite-health section) | COVERED (mock-only) |
| UI-ROUTE-27 | `/api/global-controls` showed correct limits/network | no row | not found | MISSING |
| UI-ROUTE-30 | `/api/live-audit-summary` returned `ACCOUNT_ADDRESS_UNAVAILABLE` | no row | not found | MISSING |

**Totals: 15 codes found. COVERED (has a named or generic test) = 10. ROW-NO-TEST (functional test exists,
id itself not cross-referenced) = 1. MISSING (no test found anywhere) = 4** (ORD-001, ORD-009, RISK-004,
UI-ROUTE-27, UI-ROUTE-30 — that's actually 5 MISSING; corrected count: 5 MISSING, 1 ROW-NO-TEST, 9 COVERED).

## Things Boss would expect that are not covered (max 15 lines)

1. **No `INC-NN` incident ledger exists at all** — every incident the project has actually hit lives only
   inside per-run `_FINDINGS.md` prose and `run_results.json`, with no single durable, numbered register.
   If Boss expects "every incident has a record", the record format he's picturing doesn't exist yet.
2. **Startup-time signer/network validation (ORD-009) has no regression test** — the exact defect that
   caused run3a to misreport a definite signer rejection as "needs review" could recur silently.
3. **Order-id/send-attempt reconciliation (ORD-001) and the $50 max-order cap (RISK-004)** were proven once,
   live, on a now-superseded commit (`ab7f2b0`) and never turned into an offline regression test — a future
   refactor could silently break either with nothing catching it before the next live run.
4. **The two UI-route defects (UI-ROUTE-27/30) have no regression coverage** — a broken `/api/live-audit-summary`
   (`ACCOUNT_ADDRESS_UNAVAILABLE`) could ship again unnoticed.
5. **The hotpath bench failure already flagged in the matrix** (`test_hotpath_replay_bench.py`, 0/8 sendable
   fills reach the fake exchange) is a structural red flag still open and outside this task's scope.
6. **No commit has ever been both certified by this matrix AND run on testnet at the same time** — every
   live PASS in the table above is stale relative to current `main`. This is the matrix's own top gap,
   repeated here because Part B's premise (is coverage complete) can't be fully answered while the
   live/mock pairing is this stale.

## Proposed new matrix rows for every MISSING item

| id | proposed wording | suggested test name |
|---|---|---|
| ORD-001 | Every exchange order id returned by a send must match a recorded engine send-attempt row; no order appears that the engine didn't request. | `test_core_order_id_reconciliation.py :: NO_UNKNOWN_EXCHANGE_ORDER_IDS` |
| ORD-009 | On startup, probe whether the configured signer is approved on the configured follower network before any send; a definite "signer does not exist" rejection must be a terminal fail-closed stop, never `SEND_OUTCOME_REVIEW_REQUIRED`. | `test_core_signer_network_approval.py :: SIGNER_REJECTION_IS_TERMINAL_NOT_REVIEW` |
| RISK-004 | No single order may exceed the configured max-order-value cap ($50 default); the cap must fire and block, not just log. | `test_core_max_order_cap.py :: CAP_BLOCKS_OVERSIZED_ORDER` |
| UI-ROUTE-27 | `/api/global-controls` must report the exact configured limits and the exact leader/follower network pair in use. | `test_ui_routes.py :: GLOBAL_CONTROLS_REPORTS_TRUE_LIMITS_AND_NETWORKS` |
| UI-ROUTE-30 | `/api/live-audit-summary` must never return `ACCOUNT_ADDRESS_UNAVAILABLE` while the engine holds a valid follower account address; if the address truly is unknown, the UI must say so plainly rather than crash the summary. | `test_ui_routes.py :: AUDIT_SUMMARY_NEVER_SILENTLY_UNAVAILABLE` |
| NET-003 | Leader-reads-mainnet / follower-sends-testnet separation must hold from the very first order, and the matrix must cite this id by name (today only row 12's generic N1-N4 cover the concept without naming NET-003). | cross-reference existing `N1_DEFAULT_LEADER_MAINNET_FOLLOWER_TESTNET` as `NET-003` explicitly in the matrix text |

## Models / tooling used for this pass

- graphify: `graphify update .` run against the fresh clone before analysis (real rebuild, not cached);
  consulted graph for cross-file reference checking (see BUILD_MATCH_DIFF.md graph-freshness note).
- Analysis (file discovery, AST diffing, JSON/markdown cross-referencing, this table): **deepseek-flash**
  (Hermes session route, `hermes:implementation-owner`) — same model used for the pre-existing
  `CERTIFICATION_MATRIX_2026-10-10.md` this task cross-references.
- No part was split to a separate free-compute worker: the task is a single tight cross-reference across
  an already-small set of files found by search; splitting would add transcription risk for no speed gain,
  consistent with the precedent set in the existing matrix's "Models used" section.
