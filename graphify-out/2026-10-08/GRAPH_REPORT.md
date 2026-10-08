# Graph Report - b3-main  (2026-10-08)

## Corpus Check
- 9 files · ~25,612 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 208 nodes · 618 edges · 16 communities
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS · INFERRED: 1 edges (avg confidence: 0.8)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `606d32e2`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- DryRunLiveCopyService
- self_test
- DedicatedLiveWSManager
- manual_send_one_intent
- Architecture Contract — Hyperliquid Build 3 Repair
- Operating Protocol
- Build 3 — Product Semantics, Non-Goals and Measurable DONE (Gate 1 freeze)
- convergence_shadow.py
- event_authorised_desired_net
- HL_Live_Copy_Service.py
- Bootstrap
- Any
- inum
- Hyperliquid Build 3 Repair
- prepare_hl_order_numbers
- send_hyperliquid_order

## God Nodes (most connected - your core abstractions)
1. `self_test()` - 50 edges
2. `DryRunLiveCopyService` - 36 edges
3. `LeaderFill` - 29 edges
4. `fnum()` - 25 edges
5. `utc_now_iso()` - 24 edges
6. `manual_send_one_intent()` - 20 edges
7. `LiveWalletConfig` - 20 edges
8. `inum()` - 16 edges
9. `DedicatedLiveWSManager` - 15 edges
10. `append_csv()` - 13 edges

## Surprising Connections (you probably didn't know these)
- `load_leader_fills()` --references--> `Path`  [EXTRACTED]
  _archive/hl_stage2/HL_Live_Copy_Service.py →   _Bridges community 1 → community 9_
- `main()` --calls--> `configure_paths()`  [EXTRACTED]
  _archive/hl_stage2/HL_Live_Copy_Service.py → _archive/hl_stage2/HL_Live_Copy_Service.py  _Bridges community 1 → community 2_
- `append_send_attempt()` --calls--> `utc_now_iso()`  [EXTRACTED]
  _archive/hl_stage2/HL_Live_Copy_Service.py → _archive/hl_stage2/HL_Live_Copy_Service.py  _Bridges community 0 → community 3_
- `build_ws_health_snapshot()` --calls--> `utc_now_iso()`  [EXTRACTED]
  _archive/hl_stage2/HL_Live_Copy_Service.py → _archive/hl_stage2/HL_Live_Copy_Service.py  _Bridges community 0 → community 2_
- `ensure_csv_schema()` --calls--> `utc_now_iso()`  [EXTRACTED]
  _archive/hl_stage2/HL_Live_Copy_Service.py → _archive/hl_stage2/HL_Live_Copy_Service.py  _Bridges community 0 → community 1_

## Import Cycles
- None detected.

## Communities (16 total, 0 thin omitted)

### Community 0 - "DryRunLiveCopyService"
Cohesion: 0.14
Nodes (15): adverse_diff_pct(), audit_reason_for_fill(), dry_run_intent_audit_decision(), DryRunLiveCopyService, fnum(), LeaderFill, LiveWalletConfig, Mutate the genuine post-baseline leader EVENT lineage for (wallet, coin). The… (+7 more)

### Community 1 - "self_test"
Cohesion: 0.13
Nodes (24): append_csv(), atomic_write_json(), audit_notes_for_fill(), classify_ignored_ws_message(), configure_paths(), count_csv_data_rows(), ensure_csv_header(), ensure_csv_schema() (+16 more)

### Community 2 - "DedicatedLiveWSManager"
Cohesion: 0.23
Nodes (7): build_ws_health_snapshot(), DedicatedLiveWSManager, main(), Write health file before sockets open so every subscribed wallet has an entry., utc_now_ms(), write_ws_health(), write_ws_health_initial()

### Community 3 - "manual_send_one_intent"
Cohesion: 0.28
Nodes (8): append_send_attempt(), fixed_notional_buffered_cap(), get_wallet_live_config(), load_manual_live_positions(), load_would_send_order(), manual_send_one_intent(), truthy_csv(), update_manual_live_position_from_fill()

### Community 4 - "Architecture Contract — Hyperliquid Build 3 Repair"
Cohesion: 0.13
Nodes (14): Architect's job, Architecture Contract — Hyperliquid Build 3 Repair, Automatic Architect escalation, Build 4 requirements source set, Chosen repair, Completion definition, Conflict rule, Full project acceptance scope (+6 more)

### Community 5 - "Operating Protocol"
Cohesion: 0.18
Nodes (10): Architect, Architectural interrupt, Control model, Controller, Evidence discipline, GitHub discipline, Hermes, High-water discipline (+2 more)

### Community 6 - "Build 3 — Product Semantics, Non-Goals and Measurable DONE (Gate 1 freeze)"
Cohesion: 0.29
Nodes (6): 1. Preserved product behaviour (must survive the repair), 2. Trading-authority model (the frozen semantics), 3. Explicit non-goals, 4. Measurable downstream DONE (project completion), 5. Open items this freeze does NOT resolve (carried forward, not silently merged), Build 3 — Product Semantics, Non-Goals and Measurable DONE (Gate 1 freeze)

### Community 7 - "convergence_shadow.py"
Cohesion: 0.50
Nodes (7): _check(), compute_convergence_order(), ConvergenceOrder, _expect(), _none(), Return the single safe next order to move ACTUAL_NET toward DESIRED_NET. Hard…, run_self_test()

### Community 8 - "event_authorised_desired_net"
Cohesion: 0.22
Nodes (9): event_authorised_desired_net(), FixedModeAuthorityConflict, proportional_sleeve_scale(), The intended fixed-mode target exposure cannot be proven from durable evidence., Proportional sleeve scale: leader position x scale = copied exposure., Map an event-authorised leader signed position to this wallet's copied sleeve.…, Aggregate same-coin wallet sleeves into ONE signed account-net desired value., sleeve_from_leader_event_position() (+1 more)

### Community 9 - "HL_Live_Copy_Service.py"
Cohesion: 0.18
Nodes (16): executable_price_from_fill_payload(), fetch_live_fills_range(), fetch_live_fills_since(), is_benign_ws_error(), is_ws_abnf_frame(), load_leader_fills(), normalise_side(), parse_api_leader_fill() (+8 more)

### Community 10 - "Bootstrap"
Cohesion: 0.33
Nodes (5): Architect bootstrap, Bootstrap, Controller bootstrap, Current first gate: BUILD3_SOURCE_BASELINE_IMPORT_1, Hermes bootstrap

### Community 11 - "Any"
Cohesion: 0.23
Nodes (10): Any, extract_ws_fills(), extract_ws_fills_with_meta(), fetch_public_executable_quote(), normalize_live_wallet_config(), parse_l2_level_price(), should_write_would_send(), wire_safe_float() (+2 more)

### Community 12 - "inum"
Cohesion: 0.40
Nodes (5): force_fetch_hl_perp_meta(), get_hl_perp_meta_by_coin(), inum(), resolve_hl_perp_symbol(), should_recover_ws_snapshot_fill()

### Community 13 - "Hyperliquid Build 3 Repair"
Cohesion: 0.40
Nodes (4): Hyperliquid Build 3 Repair, Immediate state, Read order, Roles

### Community 14 - "prepare_hl_order_numbers"
Cohesion: 0.60
Nodes (6): floor_decimal_to_places(), prepare_hl_order_numbers(), round_price_hl_perp(), round_size_hl_perp(), size_increment_for_places(), Decimal

### Community 15 - "send_hyperliquid_order"
Cohesion: 0.40
Nodes (5): _is_reduce_only_full_close_bypass(), parse_hl_order_status(), Return True iff the $10 min-notional preflight should be bypassed. Hyperliquid…, response_has_order_error(), send_hyperliquid_order()

## Knowledge Gaps
- **30 isolated node(s):** `Product-preservation presumption`, `Objective`, `Known failure`, `Trading-authority precedence (Gate 1 freeze — Architect ruling `B3-A2C-GATE0-PASS-G1-1`)`, `Non-negotiable invariants` (+25 more)
  These have ≤1 connection - possible missing edges or undocumented components.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `DryRunLiveCopyService` connect `DryRunLiveCopyService` to `self_test`, `DedicatedLiveWSManager`, `manual_send_one_intent`, `HL_Live_Copy_Service.py`, `Any`?**
  _High betweenness centrality (0.083) - this node is a cross-community bridge._
- **Why does `self_test()` connect `self_test` to `DryRunLiveCopyService`, `DedicatedLiveWSManager`, `manual_send_one_intent`, `HL_Live_Copy_Service.py`, `Any`, `inum`, `prepare_hl_order_numbers`, `send_hyperliquid_order`?**
  _High betweenness centrality (0.065) - this node is a cross-community bridge._
- **Why does `DedicatedLiveWSManager` connect `DedicatedLiveWSManager` to `HL_Live_Copy_Service.py`, `inum`, `self_test`?**
  _High betweenness centrality (0.031) - this node is a cross-community bridge._
- **What connects `Product-preservation presumption`, `Objective`, `Known failure` to the rest of the system?**
  _30 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `DryRunLiveCopyService` be split into smaller, more focused modules?**
  _Cohesion score 0.13953488372093023 - nodes in this community are weakly interconnected._
- **Should `self_test` be split into smaller, more focused modules?**
  _Cohesion score 0.12535612535612536 - nodes in this community are weakly interconnected._
- **Should `Architecture Contract — Hyperliquid Build 3 Repair` be split into smaller, more focused modules?**
  _Cohesion score 0.13333333333333333 - nodes in this community are weakly interconnected._