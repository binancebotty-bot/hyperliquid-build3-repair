# Graph Report - b3-main  (2026-10-08)

## Corpus Check
- 25 files · ~66,116 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 513 nodes · 1738 edges · 16 communities (13 shown, 3 thin omitted)
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS · INFERRED: 2 edges (avg confidence: 0.8)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `7bc1f172`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- HL_Live_Copy_Service.py
- DryRunLiveCopyService
- FixedModeAuthorityConflict
- exchange_truth.py
- Architecture Contract — Hyperliquid Build 3 Repair
- get
- Operating Protocol
- convergence_shadow.py
- Build 3 — Product Semantics, Non-Goals and Measurable DONE (Gate 1 freeze)
- Bootstrap
- Hyperliquid Build 3 Repair
- load_json
- HL_Copy_App_SSOT.py
- test_g4_order_cap.py
- test_g4_fixed_slices.py
- test_g4_ui_controls.py

## God Nodes (most connected - your core abstractions)
1. `fnum()` - 55 edges
2. `self_test()` - 50 edges
3. `DryRunLiveCopyService` - 49 edges
4. `build_model_state()` - 34 edges
5. `fnum()` - 34 edges
6. `LeaderFill` - 30 edges
7. `_live_audit_summary()` - 27 edges
8. `manual_send_one_intent()` - 25 edges
9. `utc_now_iso()` - 24 edges
10. `LiveWalletConfig` - 23 edges

## Surprising Connections (you probably didn't know these)
- `_archive_manual_reconciliation_ledger_row()` --references--> `_post()`  [EXTRACTED]
  _archive/hl_stage2/HL_Copy_App_SSOT.py → _archive/hl_stage2/exchange_truth.py
- `main()` --calls--> `fresh()`  [INFERRED]
  _archive/hl_stage2/test_g2_copy_correctness.py → _archive/hl_stage2/test_g3_exchange_truth.py
- `main()` --calls--> `fresh()`  [INFERRED]
  _archive/hl_stage2/test_g4_intake_sleeves.py → _archive/hl_stage2/test_g3_exchange_truth.py
- `set_wallet_include()` --references--> `_post()`  [EXTRACTED]
  _archive/hl_stage2/HL_Copy_App_SSOT.py → _archive/hl_stage2/exchange_truth.py
- `set_wallet_config()` --references--> `_post()`  [EXTRACTED]
  _archive/hl_stage2/HL_Copy_App_SSOT.py → _archive/hl_stage2/exchange_truth.py

## Import Cycles
- None detected.

## Communities (16 total, 3 thin omitted)

### Community 0 - "HL_Live_Copy_Service.py"
Cohesion: 0.06
Nodes (87): append_csv(), append_send_attempt(), atomic_write_json(), attach_send_result(), audit_notes_for_fill(), build_ws_health_snapshot(), classify_ignored_ws_message(), clear_unresolved_send() (+79 more)

### Community 1 - "DryRunLiveCopyService"
Cohesion: 0.06
Nodes (38): adverse_diff_pct(), audit_reason_for_fill(), dry_run_intent_audit_decision(), DryRunLiveCopyService, event_authorised_desired_net(), executable_price_from_fill_payload(), fnum(), LeaderFill (+30 more)

### Community 2 - "FixedModeAuthorityConflict"
Cohesion: 0.50
Nodes (3): FixedModeAuthorityConflict, The intended fixed-mode target exposure cannot be proven from durable evidence., Exception

### Community 3 - "exchange_truth.py"
Cohesion: 0.07
Nodes (35): _fill_key(), identity_ok(), list_perp_dexes(), master_account_net(), master_userfills(), master_userfills_all_dexes(), _match(), G3 EXCHANGE_TRUTH / SETTLEMENT seam (ruling B3-A2C-G2-PASS-G3-1). Read-only… (+27 more)

### Community 5 - "Architecture Contract — Hyperliquid Build 3 Repair"
Cohesion: 0.13
Nodes (14): Architect's job, Architecture Contract — Hyperliquid Build 3 Repair, Automatic Architect escalation, Build 4 requirements source set, Chosen repair, Completion definition, Conflict rule, Full project acceptance scope (+6 more)

### Community 6 - "get"
Cohesion: 0.11
Nodes (61): _post(), Read-only POST to /info; `fetcher` is injected so tests use offline fixtures., _active_live_copy_wallet_count(), add_live_config_wallet(), admin_purge_wallet(), api_equity(), api_get_ui_state(), api_metrics() (+53 more)

### Community 7 - "Operating Protocol"
Cohesion: 0.17
Nodes (11): Architect, Architectural interrupt, Control model, Controller, Evidence discipline, GitHub discipline, Hermes, Hermes reporting convention — Richard instruction, October 2026 (+3 more)

### Community 8 - "convergence_shadow.py"
Cohesion: 0.50
Nodes (7): _check(), compute_convergence_order(), ConvergenceOrder, _expect(), _none(), Return the single safe next order to move ACTUAL_NET toward DESIRED_NET. Hard…, run_self_test()

### Community 9 - "Build 3 — Product Semantics, Non-Goals and Measurable DONE (Gate 1 freeze)"
Cohesion: 0.29
Nodes (6): 1. Preserved product behaviour (must survive the repair), 2. Trading-authority model (the frozen semantics), 3. Explicit non-goals, 4. Measurable downstream DONE (project completion), 5. Open items this freeze does NOT resolve (carried forward, not silently merged), Build 3 — Product Semantics, Non-Goals and Measurable DONE (Gate 1 freeze)

### Community 10 - "Bootstrap"
Cohesion: 0.33
Nodes (5): Architect bootstrap, Bootstrap, Controller bootstrap, Current first gate: BUILD3_SOURCE_BASELINE_IMPORT_1, Hermes bootstrap

### Community 11 - "Hyperliquid Build 3 Repair"
Cohesion: 0.40
Nodes (4): Hyperliquid Build 3 Repair, Immediate state, Read order, Roles

### Community 12 - "load_json"
Cohesion: 0.14
Nodes (31): _account_reconciliation_baseline_timestamp(), _archive_manual_reconciliation_ledger_row(), atomic_write_csv(), atomic_write_json(), backup_purge_files(), _build_account_reconciliation(), _earliest_real_order_filled_ms(), _fetch_exchange_account_snapshot() (+23 more)

### Community 15 - "HL_Copy_App_SSOT.py"
Cohesion: 0.05
Nodes (123): active_wallet(), active_wallet_row(), alignment_status_for_key(), _append_exchange_history(), _apply_price_model(), avg(), block(), block_num() (+115 more)

## Knowledge Gaps
- **31 isolated node(s):** `Product-preservation presumption`, `Objective`, `Known failure`, `Trading-authority precedence (Gate 1 freeze — Architect ruling `B3-A2C-GATE0-PASS-G1-1`)`, `Non-negotiable invariants` (+26 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `_post()` connect `get` to `exchange_truth.py`, `load_json`?**
  _High betweenness centrality (0.402) - this node is a cross-community bridge._
- **Why does `DryRunLiveCopyService` connect `DryRunLiveCopyService` to `HL_Live_Copy_Service.py`?**
  _High betweenness centrality (0.091) - this node is a cross-community bridge._
- **Why does `_archive_manual_reconciliation_ledger_row()` connect `load_json` to `get`, `HL_Copy_App_SSOT.py`?**
  _High betweenness centrality (0.046) - this node is a cross-community bridge._
- **What connects `Product-preservation presumption`, `Objective`, `Known failure` to the rest of the system?**
  _31 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `HL_Live_Copy_Service.py` be split into smaller, more focused modules?**
  _Cohesion score 0.061239731142643763 - nodes in this community are weakly interconnected._
- **Should `DryRunLiveCopyService` be split into smaller, more focused modules?**
  _Cohesion score 0.06383619391749473 - nodes in this community are weakly interconnected._
- **Should `exchange_truth.py` be split into smaller, more focused modules?**
  _Cohesion score 0.06829268292682927 - nodes in this community are weakly interconnected._