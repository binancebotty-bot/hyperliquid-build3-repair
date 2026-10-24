# Graph Report - hyperliquid-build3-repair  (2026-10-09)

## Corpus Check
- 17 files · ~63,520 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 621 nodes · 1900 edges · 27 communities (24 shown, 3 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 56 edges (avg confidence: 0.86)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `55994157`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- HL_Live_Copy_Service.py
- DryRunLiveCopyService
- FixedModeAuthorityConflict
- exchange_truth.py
- self_test
- Architecture Contract — Hyperliquid Build 3 Repair
- HL_Copy_App_SSOT.py
- Operating Protocol
- convergence_shadow.py
- Build 3 — Product Semantics, Non-Goals and Measurable DONE (Gate 1 freeze)
- Bootstrap
- Hyperliquid Build 3 Repair
- os
- build_model_state
- LeaderFill
- Any
- test_g4_order_cap.py
- utc_now_ms
- load_json
- test_g2_copy_correctness.py
- test_g3_exchange_truth.py
- test_g4_intake_sleeves.py
- attach_send_result
- tempfile
- G4-C2A — READ-ONLY MARK SOURCE INVENTORY (Architect F3)

## God Nodes (most connected - your core abstractions)
1. `fnum()` - 62 edges
2. `self_test()` - 61 edges
3. `DryRunLiveCopyService` - 51 edges
4. `build_model_state()` - 37 edges
5. `fnum()` - 34 edges
6. `LeaderFill` - 31 edges
7. `_live_audit_summary()` - 28 edges
8. `utc_now_iso()` - 28 edges
9. `manual_send_one_intent()` - 25 edges
10. `render_home()` - 24 edges

## Surprising Connections (you probably didn't know these)
- `Precise blocker for Architect ruling` --references--> `executable_price_from_fill_payload()`  [INFERRED]
  _archive/hl_stage2/evidence/G4_C2A_MARK_SOURCE_INVENTORY.md → _archive/hl_stage2/HL_Live_Copy_Service.py
- `Trace table` --references--> `utc_now_ms()`  [INFERRED]
  _archive/hl_stage2/evidence/G4_C2A_MARK_SOURCE_INVENTORY.md → _archive/hl_stage2/HL_Live_Copy_Service.py
- `Trace table` --references--> `FixedModeAuthorityConflict`  [INFERRED]
  _archive/hl_stage2/evidence/G4_C2A_MARK_SOURCE_INVENTORY.md → _archive/hl_stage2/HL_Live_Copy_Service.py
- `Trace table` --references--> `dry_run_intent_audit_decision()`  [INFERRED]
  _archive/hl_stage2/evidence/G4_C2A_MARK_SOURCE_INVENTORY.md → _archive/hl_stage2/HL_Live_Copy_Service.py
- `Trace table` --references--> `fetch_public_executable_quote()`  [INFERRED]
  _archive/hl_stage2/evidence/G4_C2A_MARK_SOURCE_INVENTORY.md → _archive/hl_stage2/HL_Live_Copy_Service.py

## Import Cycles
- None detected.

## Communities (27 total, 3 thin omitted)

### Community 0 - "HL_Live_Copy_Service.py"
Cohesion: 0.08
Nodes (45): append_send_attempt(), classify_ignored_ws_message(), on_message(), extract_ws_fills(), extract_ws_fills_with_meta(), fetch_live_fills_range(), fetch_live_fills_since(), fetch_public_executable_quote() (+37 more)

### Community 1 - "DryRunLiveCopyService"
Cohesion: 0.08
Nodes (11): Trace table, configure_paths(), DryRunLiveCopyService, event_authorised_desired_net(), fnum(), main(), normalize_live_wallet_config(), proportional_sleeve_scale() (+3 more)

### Community 3 - "exchange_truth.py"
Cohesion: 0.11
Nodes (12): _fill_key(), identity_ok(), list_perp_dexes(), master_account_net(), master_userfills(), master_userfills_all_dexes(), _match(), reconcile_sleeve() (+4 more)

### Community 4 - "self_test"
Cohesion: 0.09
Nodes (20): append_csv(), atomic_write_json(), build_ws_health_snapshot(), count_csv_data_rows(), ensure_csv_header(), ensure_csv_schema(), last_csv_row(), load_local_env_file() (+12 more)

### Community 5 - "Architecture Contract — Hyperliquid Build 3 Repair"
Cohesion: 0.13
Nodes (14): Architect's job, Architecture Contract — Hyperliquid Build 3 Repair, Automatic Architect escalation, Build 4 requirements source set, Chosen repair, Completion definition, Conflict rule, Full project acceptance scope (+6 more)

### Community 6 - "HL_Copy_App_SSOT.py"
Cohesion: 0.05
Nodes (100): _post(), _account_reconciliation_baseline_timestamp(), _active_live_copy_wallet_count(), add_live_config_wallet(), admin_purge_wallet(), api_equity(), api_get_ui_state(), api_metrics() (+92 more)

### Community 7 - "Operating Protocol"
Cohesion: 0.17
Nodes (11): Architect, Architectural interrupt, Control model, Controller, Evidence discipline, GitHub discipline, Hermes, Hermes reporting convention — Richard instruction, October 2026 (+3 more)

### Community 8 - "convergence_shadow.py"
Cohesion: 0.35
Nodes (6): _check(), compute_convergence_order(), ConvergenceOrder, _expect(), _none(), run_self_test()

### Community 9 - "Build 3 — Product Semantics, Non-Goals and Measurable DONE (Gate 1 freeze)"
Cohesion: 0.29
Nodes (6): 1. Preserved product behaviour (must survive the repair), 2. Trading-authority model (the frozen semantics), 3. Explicit non-goals, 4. Measurable downstream DONE (project completion), 5. Open items this freeze does NOT resolve (carried forward, not silently merged), Build 3 — Product Semantics, Non-Goals and Measurable DONE (Gate 1 freeze)

### Community 10 - "Bootstrap"
Cohesion: 0.33
Nodes (5): Architect bootstrap, Bootstrap, Controller bootstrap, Current first gate: BUILD3_SOURCE_BASELINE_IMPORT_1, Hermes bootstrap

### Community 11 - "Hyperliquid Build 3 Repair"
Cohesion: 0.40
Nodes (4): Hyperliquid Build 3 Repair, Immediate state, Read order, Roles

### Community 12 - "os"
Cohesion: 0.50
Nodes (4): _execution_guards_info(), ev(), _local_env_value(), _public_account_address()

### Community 13 - "build_model_state"
Cohesion: 0.10
Nodes (27): alignment_status_for_key(), _apply_price_model(), avg(), block(), bps_fee(), build_model_state(), copy_wallet_exposure(), record_copy_exposure() (+19 more)

### Community 14 - "LeaderFill"
Cohesion: 0.21
Nodes (10): adverse_diff_pct(), audit_notes_for_fill(), audit_reason_for_fill(), dry_run_intent_audit_decision(), executable_price_from_fill_payload(), LeaderFill, LiveWalletConfig, side_from_signed() (+2 more)

### Community 15 - "Any"
Cohesion: 0.06
Nodes (83): active_wallet(), active_wallet_row(), _append_exchange_history(), block_num(), _build_account_reconciliation(), _build_live_wallet_derived(), _build_manual_reconciliation_rows(), append_expected_fill() (+75 more)

### Community 16 - "test_g4_order_cap.py"
Cohesion: 0.22
Nodes (3): check(), main(), engine()

### Community 17 - "utc_now_ms"
Cohesion: 0.21
Nodes (10): DedicatedLiveWSManager, on_close(), on_error(), on_open(), on_ping(), on_pong(), schedule_proactive_recycle(), recycle_after_delay() (+2 more)

### Community 18 - "load_json"
Cohesion: 0.20
Nodes (6): ensure_dirs(), load_auto_send_attempt_ids(), load_csv_ids(), load_json(), load_unresolved_sends(), write_ws_health_initial()

### Community 19 - "test_g2_copy_correctness.py"
Cohesion: 0.22
Nodes (4): check(), main(), fresh(), wire_account_net()

### Community 20 - "test_g3_exchange_truth.py"
Cohesion: 0.22
Nodes (4): check(), Fixture, reset_master(), with_master()

### Community 21 - "test_g4_intake_sleeves.py"
Cohesion: 0.31
Nodes (5): check(), main(), authority_for(), fresh(), wire_account_net()

### Community 22 - "attach_send_result"
Cohesion: 0.32
Nodes (5): attach_send_result(), clear_unresolved_send(), persist_unresolved_send(), _mut(), _state_write()

### Community 23 - "tempfile"
Cohesion: 0.19
Nodes (4): check(), main(), check(), main()

### Community 24 - "G4-C2A — READ-ONLY MARK SOURCE INVENTORY (Architect F3)"
Cohesion: 0.33
Nodes (5): Answer, Consequences, G4-C2A — READ-ONLY MARK SOURCE INVENTORY (Architect F3), Precise blocker for Architect ruling, Question

## Knowledge Gaps
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `DryRunLiveCopyService` connect `DryRunLiveCopyService` to `HL_Live_Copy_Service.py`, `self_test`, `LeaderFill`, `utc_now_ms`, `load_json`, `.settle_from_master_evidence`, `.wallet_gate`?**
  _High betweenness centrality (0.080) - this node is a cross-community bridge._
- **Are the 17 inferred relationships involving `self_test()` (e.g. with `.update_status()` and `.append_would_send_order()`) actually correct?**
  _`self_test()` has 17 INFERRED edges - model-reasoned connections that need verification._
- **Should `HL_Live_Copy_Service.py` be split into smaller, more focused modules?**
  _Cohesion score 0.08499743983614952 - nodes in this community are weakly interconnected._
- **Why does `self_test()` connect `self_test` to `HL_Live_Copy_Service.py`, `DryRunLiveCopyService`, `LeaderFill`, `utc_now_ms`, `load_json`?**
  _High betweenness centrality (0.048) - this node is a cross-community bridge._
- **Should `DryRunLiveCopyService` be split into smaller, more focused modules?**
  _Cohesion score 0.07541478129713423 - nodes in this community are weakly interconnected._
- **Why does `_post()` connect `HL_Copy_App_SSOT.py` to `exchange_truth.py`?**
  _High betweenness centrality (0.028) - this node is a cross-community bridge._
- **Should `exchange_truth.py` be split into smaller, more focused modules?**
  _Cohesion score 0.11 - nodes in this community are weakly interconnected._