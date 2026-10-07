# Graph Report - b3-main  (2026-10-07)

## Corpus Check
- 7 files · ~20,383 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 171 nodes · 540 edges · 14 communities
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `b3bfb7df`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- DryRunLiveCopyService
- self_test
- DedicatedLiveWSManager
- Any
- Architecture Contract — Hyperliquid Build 3 Repair
- Operating Protocol
- HL_Live_Copy_Service.py
- convergence_shadow.py
- manual_send_one_intent
- prepare_hl_order_numbers
- Bootstrap
- inum
- send_hyperliquid_order
- Hyperliquid Build 3 Repair

## God Nodes (most connected - your core abstractions)
1. `self_test()` - 50 edges
2. `DryRunLiveCopyService` - 26 edges
3. `LeaderFill` - 25 edges
4. `utc_now_iso()` - 24 edges
5. `manual_send_one_intent()` - 20 edges
6. `fnum()` - 19 edges
7. `inum()` - 16 edges
8. `LiveWalletConfig` - 15 edges
9. `DedicatedLiveWSManager` - 15 edges
10. `append_csv()` - 13 edges

## Surprising Connections (you probably didn't know these)
- `append_csv()` --references--> `Path`  [EXTRACTED]
  _archive/hl_stage2/HL_Live_Copy_Service.py →   _Bridges community 1 → community 0_
- `load_leader_fills()` --references--> `Path`  [EXTRACTED]
  _archive/hl_stage2/HL_Live_Copy_Service.py →   _Bridges community 1 → community 6_
- `main()` --calls--> `configure_paths()`  [EXTRACTED]
  _archive/hl_stage2/HL_Live_Copy_Service.py → _archive/hl_stage2/HL_Live_Copy_Service.py  _Bridges community 1 → community 2_
- `build_ws_health_snapshot()` --calls--> `utc_now_iso()`  [EXTRACTED]
  _archive/hl_stage2/HL_Live_Copy_Service.py → _archive/hl_stage2/HL_Live_Copy_Service.py  _Bridges community 0 → community 2_
- `fetch_live_fills_range()` --calls--> `utc_now_iso()`  [EXTRACTED]
  _archive/hl_stage2/HL_Live_Copy_Service.py → _archive/hl_stage2/HL_Live_Copy_Service.py  _Bridges community 0 → community 3_

## Import Cycles
- None detected.

## Communities (14 total, 0 thin omitted)

### Community 0 - "DryRunLiveCopyService"
Cohesion: 0.18
Nodes (15): adverse_diff_pct(), append_csv(), append_send_attempt(), audit_reason_for_fill(), dry_run_intent_audit_decision(), DryRunLiveCopyService, executable_price_from_fill_payload(), fnum() (+7 more)

### Community 1 - "self_test"
Cohesion: 0.15
Nodes (22): atomic_write_json(), audit_notes_for_fill(), classify_ignored_ws_message(), configure_paths(), count_csv_data_rows(), ensure_csv_header(), ensure_csv_schema(), ensure_dirs() (+14 more)

### Community 2 - "DedicatedLiveWSManager"
Cohesion: 0.28
Nodes (5): build_ws_health_snapshot(), DedicatedLiveWSManager, main(), utc_now_ms(), write_ws_health()

### Community 3 - "Any"
Cohesion: 0.21
Nodes (15): Any, extract_ws_fills(), extract_ws_fills_with_meta(), fetch_live_fills_range(), fetch_live_fills_since(), fetch_public_executable_quote(), normalise_side(), normalize_live_wallet_config() (+7 more)

### Community 4 - "Architecture Contract — Hyperliquid Build 3 Repair"
Cohesion: 0.14
Nodes (13): Architect's job, Architecture Contract — Hyperliquid Build 3 Repair, Automatic Architect escalation, Build 4 requirements source set, Chosen repair, Completion definition, Conflict rule, Full project acceptance scope (+5 more)

### Community 5 - "Operating Protocol"
Cohesion: 0.18
Nodes (10): Architect, Architectural interrupt, Control model, Controller, Evidence discipline, GitHub discipline, Hermes, High-water discipline (+2 more)

### Community 6 - "HL_Live_Copy_Service.py"
Cohesion: 0.27
Nodes (9): is_benign_ws_error(), is_reducing_position(), is_ws_abnf_frame(), load_leader_fills(), parse_leader_fill_row(), parse_raw_json(), HL_Live_Copy_Service.py Phase 2 dry-run live copy service for the Hyperliquid…, weighted_entry_price() (+1 more)

### Community 7 - "convergence_shadow.py"
Cohesion: 0.50
Nodes (7): _check(), compute_convergence_order(), ConvergenceOrder, _expect(), _none(), Return the single safe next order to move ACTUAL_NET toward DESIRED_NET. Hard…, run_self_test()

### Community 8 - "manual_send_one_intent"
Cohesion: 0.32
Nodes (7): fixed_notional_buffered_cap(), get_wallet_live_config(), load_manual_live_positions(), load_would_send_order(), manual_send_one_intent(), truthy_csv(), update_manual_live_position_from_fill()

### Community 9 - "prepare_hl_order_numbers"
Cohesion: 0.60
Nodes (6): floor_decimal_to_places(), prepare_hl_order_numbers(), round_price_hl_perp(), round_size_hl_perp(), size_increment_for_places(), Decimal

### Community 10 - "Bootstrap"
Cohesion: 0.33
Nodes (5): Architect bootstrap, Bootstrap, Controller bootstrap, Current first gate: BUILD3_SOURCE_BASELINE_IMPORT_1, Hermes bootstrap

### Community 11 - "inum"
Cohesion: 0.50
Nodes (5): force_fetch_hl_perp_meta(), get_hl_perp_meta_by_coin(), inum(), resolve_hl_perp_symbol(), should_recover_ws_snapshot_fill()

### Community 12 - "send_hyperliquid_order"
Cohesion: 0.40
Nodes (5): _is_reduce_only_full_close_bypass(), parse_hl_order_status(), Return True iff the $10 min-notional preflight should be bypassed. Hyperliquid…, response_has_order_error(), send_hyperliquid_order()

### Community 13 - "Hyperliquid Build 3 Repair"
Cohesion: 0.40
Nodes (4): Hyperliquid Build 3 Repair, Immediate state, Read order, Roles

## Knowledge Gaps
- **25 isolated node(s):** `Product-preservation presumption`, `Objective`, `Known failure`, `Chosen repair`, `Non-negotiable invariants` (+20 more)
  These have ≤1 connection - possible missing edges or undocumented components.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `self_test()` connect `self_test` to `DryRunLiveCopyService`, `DedicatedLiveWSManager`, `Any`, `HL_Live_Copy_Service.py`, `manual_send_one_intent`, `prepare_hl_order_numbers`, `inum`, `send_hyperliquid_order`?**
  _High betweenness centrality (0.070) - this node is a cross-community bridge._
- **Why does `DryRunLiveCopyService` connect `DryRunLiveCopyService` to `self_test`, `DedicatedLiveWSManager`, `Any`, `HL_Live_Copy_Service.py`, `manual_send_one_intent`?**
  _High betweenness centrality (0.038) - this node is a cross-community bridge._
- **Why does `DedicatedLiveWSManager` connect `DedicatedLiveWSManager` to `self_test`, `HL_Live_Copy_Service.py`?**
  _High betweenness centrality (0.034) - this node is a cross-community bridge._
- **What connects `Product-preservation presumption`, `Objective`, `Known failure` to the rest of the system?**
  _25 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Architecture Contract — Hyperliquid Build 3 Repair` be split into smaller, more focused modules?**
  _Cohesion score 0.14285714285714285 - nodes in this community are weakly interconnected._