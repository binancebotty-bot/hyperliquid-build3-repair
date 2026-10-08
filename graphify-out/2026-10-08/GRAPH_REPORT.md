# Graph Report - b3-main  (2026-10-08)

## Corpus Check
- 26 files · ~67,220 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 514 nodes · 1739 edges · 24 communities (22 shown, 2 thin omitted)
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS · INFERRED: 2 edges (avg confidence: 0.8)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `bf088e6e`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- HL_Live_Copy_Service.py
- DryRunLiveCopyService
- DedicatedLiveWSManager
- exchange_truth.py
- HL_Copy_App_SSOT.py
- Architecture Contract — Hyperliquid Build 3 Repair
- JSONResponse
- Operating Protocol
- convergence_shadow.py
- Build 3 — Product Semantics, Non-Goals and Measurable DONE (Gate 1 freeze)
- Bootstrap
- Hyperliquid Build 3 Repair
- atomic_write_json
- get
- LeaderFill
- fnum
- test_g4_order_cap.py
- Any
- manual_send_one_intent
- Any
- block_num
- prepare_hl_order_numbers
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

## Communities (24 total, 2 thin omitted)

### Community 0 - "HL_Live_Copy_Service.py"
Cohesion: 0.09
Nodes (42): atomic_write_json(), classify_ignored_ws_message(), configure_paths(), count_csv_data_rows(), ensure_csv_header(), ensure_csv_schema(), ensure_dirs(), extract_ws_fills() (+34 more)

### Community 1 - "DryRunLiveCopyService"
Cohesion: 0.08
Nodes (24): DryRunLiveCopyService, event_authorised_desired_net(), fnum(), proportional_sleeve_scale(), Mutate the genuine post-baseline leader EVENT lineage for (wallet, coin). The…, Persisted attributed fixed-sleeve magnitude for (wallet, coin) - EXISTING state…, A ledger entry is AUTHORITATIVE only when well formed AND side-consistent. -…, ONLY wallets with a VALID attributed sleeve ledger are released from the hold.… (+16 more)

### Community 2 - "DedicatedLiveWSManager"
Cohesion: 0.21
Nodes (5): DedicatedLiveWSManager, FixedModeAuthorityConflict, The intended fixed-mode target exposure cannot be proven from durable evidence., write_ws_health(), Exception

### Community 3 - "exchange_truth.py"
Cohesion: 0.07
Nodes (35): _fill_key(), identity_ok(), list_perp_dexes(), master_account_net(), master_userfills(), master_userfills_all_dexes(), _match(), G3 EXCHANGE_TRUTH / SETTLEMENT seam (ruling B3-A2C-G2-PASS-G3-1). Read-only… (+27 more)

### Community 4 - "HL_Copy_App_SSOT.py"
Cohesion: 0.10
Nodes (39): _account_reconciliation_baseline_timestamp(), alignment_status_for_key(), _apply_price_model(), block(), bps_fee(), build_model_state(), calc_unrealized(), close_positions_fifo() (+31 more)

### Community 5 - "Architecture Contract — Hyperliquid Build 3 Repair"
Cohesion: 0.13
Nodes (14): Architect's job, Architecture Contract — Hyperliquid Build 3 Repair, Automatic Architect escalation, Build 4 requirements source set, Chosen repair, Completion definition, Conflict rule, Full project acceptance scope (+6 more)

### Community 6 - "JSONResponse"
Cohesion: 0.12
Nodes (51): _post(), Read-only POST to /info; `fetcher` is injected so tests use offline fixtures., _active_live_copy_wallet_count(), add_live_config_wallet(), admin_purge_wallet(), api_equity(), api_get_ui_state(), api_metrics() (+43 more)

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

### Community 12 - "atomic_write_json"
Cohesion: 0.21
Nodes (20): atomic_write_csv(), atomic_write_json(), backup_purge_files(), invalidate_model_cache(), _live_order_intents_path(), load_engine_truth(), load_local_env_file(), load_purged_wallets() (+12 more)

### Community 13 - "get"
Cohesion: 0.15
Nodes (33): active_wallet_row(), _append_exchange_history(), _archive_manual_reconciliation_ledger_row(), _build_account_reconciliation(), _build_execution_quality_rows(), _build_execution_quality_summary(), _build_live_leader_performance(), _build_live_wallet_derived() (+25 more)

### Community 14 - "LeaderFill"
Cohesion: 0.18
Nodes (13): adverse_diff_pct(), append_csv(), audit_notes_for_fill(), audit_reason_for_fill(), dry_run_intent_audit_decision(), executable_price_from_fill_payload(), LeaderFill, LiveWalletConfig (+5 more)

### Community 15 - "fnum"
Cohesion: 0.09
Nodes (45): active_wallet(), avg(), core_missing(), core_td(), css_class(), dash_td(), dual(), dual_cell_core() (+37 more)

### Community 16 - "test_g4_order_cap.py"
Cohesion: 0.67
Nodes (3): check(), main(), # NOTE: the aggregate-lag scenario from the directive is NOT reproducible in…

### Community 17 - "Any"
Cohesion: 0.17
Nodes (19): build_ws_health_snapshot(), fetch_live_fills_range(), fetch_live_fills_since(), fetch_public_executable_quote(), force_fetch_hl_perp_meta(), get_hl_perp_meta_by_coin(), inum(), normalise_side() (+11 more)

### Community 18 - "manual_send_one_intent"
Cohesion: 0.13
Nodes (19): append_send_attempt(), attach_send_result(), clear_unresolved_send(), fixed_notional_buffered_cap(), get_wallet_live_config(), load_manual_live_positions(), load_would_send_order(), manual_send_one_intent() (+11 more)

### Community 19 - "Any"
Cohesion: 0.16
Nodes (19): build_portfolio_history(), compact_history(), contract_money_equal(), enforce_live_wallet_limit(), _exchange_fill_match_id(), _exchange_fill_side(), _execution_guards_info(), expected_copy_price_from_row() (+11 more)

### Community 20 - "block_num"
Cohesion: 0.36
Nodes (8): block_num(), dd_current(), dd_max(), get_max_dd(), latest_history_block_dd(), max_history_block_dd(), Read numeric metric fields with legacy alias fallback., Return latest combined curve DD when the rendered block lacks it. Used only as…

### Community 21 - "prepare_hl_order_numbers"
Cohesion: 0.60
Nodes (6): floor_decimal_to_places(), prepare_hl_order_numbers(), round_price_hl_perp(), round_size_hl_perp(), size_increment_for_places(), Decimal

## Knowledge Gaps
- **31 isolated node(s):** `Product-preservation presumption`, `Objective`, `Known failure`, `Trading-authority precedence (Gate 1 freeze — Architect ruling `B3-A2C-GATE0-PASS-G1-1`)`, `Non-negotiable invariants` (+26 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **2 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `_post()` connect `JSONResponse` to `exchange_truth.py`, `get`?**
  _High betweenness centrality (0.400) - this node is a cross-community bridge._
- **Why does `DryRunLiveCopyService` connect `DryRunLiveCopyService` to `HL_Live_Copy_Service.py`, `DedicatedLiveWSManager`, `LeaderFill`, `Any`, `manual_send_one_intent`?**
  _High betweenness centrality (0.090) - this node is a cross-community bridge._
- **Why does `_archive_manual_reconciliation_ledger_row()` connect `get` to `HL_Copy_App_SSOT.py`, `JSONResponse`, `atomic_write_json`, `fnum`, `Any`?**
  _High betweenness centrality (0.046) - this node is a cross-community bridge._
- **What connects `Product-preservation presumption`, `Objective`, `Known failure` to the rest of the system?**
  _31 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `HL_Live_Copy_Service.py` be split into smaller, more focused modules?**
  _Cohesion score 0.09371980676328502 - nodes in this community are weakly interconnected._
- **Should `DryRunLiveCopyService` be split into smaller, more focused modules?**
  _Cohesion score 0.0786308973172988 - nodes in this community are weakly interconnected._
- **Should `exchange_truth.py` be split into smaller, more focused modules?**
  _Cohesion score 0.06829268292682927 - nodes in this community are weakly interconnected._