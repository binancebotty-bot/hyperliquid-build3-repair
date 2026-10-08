# Graph Report - b3-main  (2026-10-08)

## Corpus Check
- 16 files · ~58,194 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 491 nodes · 1696 edges · 24 communities (22 shown, 2 thin omitted)
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS · INFERRED: 1 edges (avg confidence: 0.8)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `6f067ab5`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- HL_Live_Copy_Service.py
- DryRunLiveCopyService
- DedicatedLiveWSManager
- exchange_truth.py
- self_test
- Architecture Contract — Hyperliquid Build 3 Repair
- JSONResponse
- Operating Protocol
- convergence_shadow.py
- Build 3 — Product Semantics, Non-Goals and Measurable DONE (Gate 1 freeze)
- Bootstrap
- Hyperliquid Build 3 Repair
- HL_Copy_App_SSOT.py
- inum
- .__init__
- Any
- fnum
- load_json
- parse_leader_fill_row
- .from_raw
- _live_audit_summary
- get
- event_authorised_desired_net
- test_g4_fixed_slices.py

## God Nodes (most connected - your core abstractions)
1. `fnum()` - 55 edges
2. `self_test()` - 50 edges
3. `DryRunLiveCopyService` - 43 edges
4. `build_model_state()` - 34 edges
5. `fnum()` - 33 edges
6. `LeaderFill` - 30 edges
7. `_live_audit_summary()` - 27 edges
8. `manual_send_one_intent()` - 25 edges
9. `utc_now_iso()` - 24 edges
10. `LiveWalletConfig` - 22 edges

## Surprising Connections (you probably didn't know these)
- `_archive_manual_reconciliation_ledger_row()` --references--> `_post()`  [EXTRACTED]
  _archive/hl_stage2/HL_Copy_App_SSOT.py → _archive/hl_stage2/exchange_truth.py
- `main()` --calls--> `fresh()`  [INFERRED]
  _archive/hl_stage2/test_g2_copy_correctness.py → _archive/hl_stage2/test_g3_exchange_truth.py
- `set_wallet_include()` --references--> `_post()`  [EXTRACTED]
  _archive/hl_stage2/HL_Copy_App_SSOT.py → _archive/hl_stage2/exchange_truth.py
- `set_wallet_config()` --references--> `_post()`  [EXTRACTED]
  _archive/hl_stage2/HL_Copy_App_SSOT.py → _archive/hl_stage2/exchange_truth.py
- `api_wallet_meta()` --references--> `_post()`  [EXTRACTED]
  _archive/hl_stage2/HL_Copy_App_SSOT.py → _archive/hl_stage2/exchange_truth.py

## Import Cycles
- None detected.

## Communities (24 total, 2 thin omitted)

### Community 0 - "HL_Live_Copy_Service.py"
Cohesion: 0.09
Nodes (57): append_send_attempt(), attach_send_result(), classify_ignored_ws_message(), clear_unresolved_send(), extract_ws_fills(), extract_ws_fills_with_meta(), fetch_live_fills_range(), fetch_live_fills_since() (+49 more)

### Community 1 - "DryRunLiveCopyService"
Cohesion: 0.11
Nodes (21): adverse_diff_pct(), audit_reason_for_fill(), dry_run_intent_audit_decision(), DryRunLiveCopyService, executable_price_from_fill_payload(), fnum(), LeaderFill, LiveWalletConfig (+13 more)

### Community 2 - "DedicatedLiveWSManager"
Cohesion: 0.21
Nodes (6): DedicatedLiveWSManager, FixedModeAuthorityConflict, main(), The intended fixed-mode target exposure cannot be proven from durable evidence., write_ws_health(), Exception

### Community 3 - "exchange_truth.py"
Cohesion: 0.07
Nodes (33): _fill_key(), identity_ok(), list_perp_dexes(), master_account_net(), master_userfills(), master_userfills_all_dexes(), _match(), G3 EXCHANGE_TRUTH / SETTLEMENT seam (ruling B3-A2C-G2-PASS-G3-1). Read-only… (+25 more)

### Community 4 - "self_test"
Cohesion: 0.14
Nodes (23): append_csv(), atomic_write_json(), audit_notes_for_fill(), build_ws_health_snapshot(), configure_paths(), count_csv_data_rows(), ensure_csv_header(), ensure_csv_schema() (+15 more)

### Community 5 - "Architecture Contract — Hyperliquid Build 3 Repair"
Cohesion: 0.13
Nodes (14): Architect's job, Architecture Contract — Hyperliquid Build 3 Repair, Automatic Architect escalation, Build 4 requirements source set, Chosen repair, Completion definition, Conflict rule, Full project acceptance scope (+6 more)

### Community 6 - "JSONResponse"
Cohesion: 0.12
Nodes (49): _post(), Read-only POST to /info; `fetcher` is injected so tests use offline fixtures., _active_live_copy_wallet_count(), add_live_config_wallet(), admin_purge_wallet(), api_get_ui_state(), api_norm(), api_set_ui_state() (+41 more)

### Community 7 - "Operating Protocol"
Cohesion: 0.18
Nodes (10): Architect, Architectural interrupt, Control model, Controller, Evidence discipline, GitHub discipline, Hermes, High-water discipline (+2 more)

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

### Community 12 - "HL_Copy_App_SSOT.py"
Cohesion: 0.13
Nodes (29): alignment_status_for_key(), _apply_price_model(), block(), bps_fee(), build_model_state(), calc_unrealized(), close_positions_fifo(), _copy_cost_bps() (+21 more)

### Community 13 - "inum"
Cohesion: 0.17
Nodes (18): _account_reconciliation_baseline_timestamp(), active_wallet_row(), _append_exchange_history(), _archive_manual_reconciliation_ledger_row(), _build_account_reconciliation(), _build_recent_send_warning_groups(), _fetch_exchange_account_snapshot(), _fetch_user_fills_by_time() (+10 more)

### Community 14 - ".__init__"
Cohesion: 0.33
Nodes (4): ensure_dirs(), load_auto_send_attempt_ids(), load_csv_ids(), A persisted lineage checkpoint is valid only if durably coupled to the…

### Community 15 - "Any"
Cohesion: 0.17
Nodes (20): _build_live_leader_performance(), _build_live_wallet_derived(), contract_money_equal(), _earliest_real_order_filled_ms(), _exchange_fill_match_id(), _execution_guards_info(), expected_copy_price_from_row(), _is_dry_run_live_fill() (+12 more)

### Community 16 - "fnum"
Cohesion: 0.10
Nodes (42): active_wallet(), avg(), core_missing(), core_td(), css_class(), dash_td(), dual(), dual_cell_core() (+34 more)

### Community 17 - "load_json"
Cohesion: 0.23
Nodes (20): atomic_write_csv(), atomic_write_json(), backup_purge_files(), invalidate_model_cache(), load_engine_truth(), load_json(), load_local_env_file(), load_purged_wallets() (+12 more)

### Community 18 - "parse_leader_fill_row"
Cohesion: 0.50
Nodes (4): load_leader_fills(), parse_leader_fill_row(), parse_raw_json(), trade_delta_from_side()

### Community 20 - "_live_audit_summary"
Cohesion: 0.19
Nodes (14): _build_execution_quality_rows(), _build_execution_quality_summary(), _build_live_wallet_rows(), _build_manual_reconciliation_rows(), _build_real_copy_positions(), get_live_audit_summary(), _live_audit_summary(), _live_order_intents_path() (+6 more)

### Community 21 - "get"
Cohesion: 0.15
Nodes (23): api_equity(), api_metrics(), api_state(), api_trades(), block_num(), build_portfolio_history(), compact_history(), dd_current() (+15 more)

### Community 22 - "event_authorised_desired_net"
Cohesion: 0.33
Nodes (6): event_authorised_desired_net(), proportional_sleeve_scale(), Proportional sleeve scale: leader position x scale = copied exposure., Map an event-authorised leader signed position to this wallet's copied sleeve.…, Aggregate same-coin wallet sleeves into ONE signed account-net desired value.…, sleeve_from_leader_event_position()

## Knowledge Gaps
- **30 isolated node(s):** `Product-preservation presumption`, `Objective`, `Known failure`, `Trading-authority precedence (Gate 1 freeze — Architect ruling `B3-A2C-GATE0-PASS-G1-1`)`, `Non-negotiable invariants` (+25 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **2 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `_post()` connect `JSONResponse` to `exchange_truth.py`, `inum`?**
  _High betweenness centrality (0.412) - this node is a cross-community bridge._
- **Why does `DryRunLiveCopyService` connect `DryRunLiveCopyService` to `HL_Live_Copy_Service.py`, `DedicatedLiveWSManager`, `self_test`, `.__init__`?**
  _High betweenness centrality (0.070) - this node is a cross-community bridge._
- **Why does `_archive_manual_reconciliation_ledger_row()` connect `inum` to `JSONResponse`, `HL_Copy_App_SSOT.py`, `Any`, `fnum`, `load_json`, `get`?**
  _High betweenness centrality (0.047) - this node is a cross-community bridge._
- **What connects `Product-preservation presumption`, `Objective`, `Known failure` to the rest of the system?**
  _30 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `HL_Live_Copy_Service.py` be split into smaller, more focused modules?**
  _Cohesion score 0.08852459016393442 - nodes in this community are weakly interconnected._
- **Should `DryRunLiveCopyService` be split into smaller, more focused modules?**
  _Cohesion score 0.11139455782312925 - nodes in this community are weakly interconnected._
- **Should `exchange_truth.py` be split into smaller, more focused modules?**
  _Cohesion score 0.07396870554765292 - nodes in this community are weakly interconnected._