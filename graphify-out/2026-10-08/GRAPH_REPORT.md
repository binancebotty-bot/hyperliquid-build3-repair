# Graph Report - b3-main  (2026-10-08)

## Corpus Check
- 11 files · ~30,030 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 265 nodes · 733 edges · 20 communities (19 shown, 1 thin omitted)
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS · INFERRED: 3 edges (avg confidence: 0.8)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `dc9960aa`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Any
- DryRunLiveCopyService
- utc_now_iso
- exchange_truth.py
- self_test
- Architecture Contract — Hyperliquid Build 3 Repair
- test_g3_exchange_truth.py
- Operating Protocol
- convergence_shadow.py
- Build 3 — Product Semantics, Non-Goals and Measurable DONE (Gate 1 freeze)
- Bootstrap
- Hyperliquid Build 3 Repair
- FixedModeAuthorityConflict
- HL_Live_Copy_Service.py
- manual_send_one_intent
- load_json
- .__init__
- prepare_hl_order_numbers
- append_csv
- master_net_snapshot

## God Nodes (most connected - your core abstractions)
1. `self_test()` - 50 edges
2. `DryRunLiveCopyService` - 40 edges
3. `fnum()` - 31 edges
4. `LeaderFill` - 29 edges
5. `manual_send_one_intent()` - 25 edges
6. `utc_now_iso()` - 24 edges
7. `LiveWalletConfig` - 20 edges
8. `inum()` - 18 edges
9. `DedicatedLiveWSManager` - 15 edges
10. `utc_now_ms()` - 13 edges

## Surprising Connections (you probably didn't know these)
- `main()` --calls--> `fresh()`  [INFERRED]
  _archive/hl_stage2/test_g2_copy_correctness.py → _archive/hl_stage2/test_g3_exchange_truth.py

## Import Cycles
- None detected.

## Communities (20 total, 1 thin omitted)

### Community 0 - "Any"
Cohesion: 0.24
Nodes (15): Any, force_fetch_hl_perp_meta(), get_hl_perp_meta_by_coin(), inum(), _is_reduce_only_full_close_bypass(), normalise_side(), parse_api_leader_fill(), parse_hl_order_status() (+7 more)

### Community 1 - "DryRunLiveCopyService"
Cohesion: 0.10
Nodes (24): adverse_diff_pct(), audit_notes_for_fill(), audit_reason_for_fill(), dry_run_intent_audit_decision(), DryRunLiveCopyService, event_authorised_desired_net(), fnum(), LeaderFill (+16 more)

### Community 2 - "utc_now_iso"
Cohesion: 0.19
Nodes (9): build_ws_health_snapshot(), DedicatedLiveWSManager, main(), Write health file before sockets open so every subscribed wallet has an entry., utc_now_iso(), utc_now_ms(), write_ws_health(), write_ws_health_initial() (+1 more)

### Community 3 - "exchange_truth.py"
Cohesion: 0.11
Nodes (25): _fill_key(), identity_ok(), list_perp_dexes(), master_account_net(), master_userfills(), master_userfills_all_dexes(), _match(), _post() (+17 more)

### Community 4 - "self_test"
Cohesion: 0.16
Nodes (19): atomic_write_json(), classify_ignored_ws_message(), configure_paths(), count_csv_data_rows(), ensure_csv_header(), ensure_csv_schema(), extract_ws_fills(), extract_ws_fills_with_meta() (+11 more)

### Community 5 - "Architecture Contract — Hyperliquid Build 3 Repair"
Cohesion: 0.13
Nodes (14): Architect's job, Architecture Contract — Hyperliquid Build 3 Repair, Automatic Architect escalation, Build 4 requirements source set, Chosen repair, Completion definition, Conflict rule, Full project acceptance scope (+6 more)

### Community 6 - "test_g3_exchange_truth.py"
Cohesion: 0.21
Nodes (10): check(), main(), check(), Fixture, fresh(), main(), G3 acceptance evidence: EXCHANGE_TRUTH_RECOVERY_SETTLEMENT (ruling…, Offline /info double: perpDexs + per-dex clearinghouseState + userFillsByTime. (+2 more)

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

### Community 12 - "FixedModeAuthorityConflict"
Cohesion: 0.50
Nodes (3): FixedModeAuthorityConflict, The intended fixed-mode target exposure cannot be proven from durable evidence., Exception

### Community 13 - "HL_Live_Copy_Service.py"
Cohesion: 0.19
Nodes (14): executable_price_from_fill_payload(), fetch_live_fills_range(), fetch_live_fills_since(), fetch_public_executable_quote(), load_leader_fills(), normalize_live_wallet_config(), parse_l2_level_price(), parse_leader_fill_row() (+6 more)

### Community 14 - "manual_send_one_intent"
Cohesion: 0.19
Nodes (13): attach_send_result(), clear_unresolved_send(), fixed_notional_buffered_cap(), get_wallet_live_config(), load_would_send_order(), manual_send_one_intent(), persist_unresolved_send(), Durably record an unresolved reservation BEFORE exchange.order authority is… (+5 more)

### Community 15 - "load_json"
Cohesion: 0.29
Nodes (7): load_json(), load_manual_live_positions(), load_unresolved_sends(), Unresolved send reservations from the EXISTING service-state file (durable…, save_manual_live_positions(), update_manual_live_position_from_fill(), ws_coverage_for_fill()

### Community 16 - ".__init__"
Cohesion: 0.33
Nodes (4): ensure_dirs(), load_auto_send_attempt_ids(), load_csv_ids(), A persisted lineage checkpoint is valid only if durably coupled to the…

### Community 17 - "prepare_hl_order_numbers"
Cohesion: 0.60
Nodes (6): floor_decimal_to_places(), prepare_hl_order_numbers(), round_price_hl_perp(), round_size_hl_perp(), size_increment_for_places(), Decimal

### Community 18 - "append_csv"
Cohesion: 0.50
Nodes (3): append_csv(), append_send_attempt(), should_write_would_send()

## Knowledge Gaps
- **30 isolated node(s):** `Product-preservation presumption`, `Objective`, `Known failure`, `Trading-authority precedence (Gate 1 freeze — Architect ruling `B3-A2C-GATE0-PASS-G1-1`)`, `Non-negotiable invariants` (+25 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `DryRunLiveCopyService` connect `DryRunLiveCopyService` to `Any`, `utc_now_iso`, `self_test`, `HL_Live_Copy_Service.py`, `.__init__`, `append_csv`?**
  _High betweenness centrality (0.085) - this node is a cross-community bridge._
- **Why does `self_test()` connect `self_test` to `Any`, `DryRunLiveCopyService`, `utc_now_iso`, `HL_Live_Copy_Service.py`, `manual_send_one_intent`, `load_json`, `prepare_hl_order_numbers`, `append_csv`?**
  _High betweenness centrality (0.044) - this node is a cross-community bridge._
- **Why does `fnum()` connect `DryRunLiveCopyService` to `Any`, `self_test`, `HL_Live_Copy_Service.py`, `manual_send_one_intent`, `load_json`, `master_net_snapshot`?**
  _High betweenness centrality (0.034) - this node is a cross-community bridge._
- **What connects `Product-preservation presumption`, `Objective`, `Known failure` to the rest of the system?**
  _30 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `DryRunLiveCopyService` be split into smaller, more focused modules?**
  _Cohesion score 0.09941944847605225 - nodes in this community are weakly interconnected._
- **Should `exchange_truth.py` be split into smaller, more focused modules?**
  _Cohesion score 0.11384615384615385 - nodes in this community are weakly interconnected._
- **Should `Architecture Contract — Hyperliquid Build 3 Repair` be split into smaller, more focused modules?**
  _Cohesion score 0.13333333333333333 - nodes in this community are weakly interconnected._