# Graph Report - b3-main  (2026-10-07)

## Corpus Check
- 8 files · ~21,146 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 179 nodes · 547 edges · 10 communities
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `2d8f111c`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- DryRunLiveCopyService
- HL_Live_Copy_Service.py
- DedicatedLiveWSManager
- Any
- Architecture Contract — Hyperliquid Build 3 Repair
- Operating Protocol
- Build 3 — Product Semantics, Non-Goals and Measurable DONE (Gate 1 freeze)
- convergence_shadow.py
- Bootstrap
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
- `main()` --calls--> `configure_paths()`  [EXTRACTED]
  _archive/hl_stage2/HL_Live_Copy_Service.py → _archive/hl_stage2/HL_Live_Copy_Service.py  _Bridges community 1 → community 2_
- `append_send_attempt()` --calls--> `utc_now_iso()`  [EXTRACTED]
  _archive/hl_stage2/HL_Live_Copy_Service.py → _archive/hl_stage2/HL_Live_Copy_Service.py  _Bridges community 0 → community 3_
- `build_ws_health_snapshot()` --calls--> `utc_now_iso()`  [EXTRACTED]
  _archive/hl_stage2/HL_Live_Copy_Service.py → _archive/hl_stage2/HL_Live_Copy_Service.py  _Bridges community 0 → community 2_
- `parse_api_leader_fill()` --calls--> `utc_now_ms()`  [EXTRACTED]
  _archive/hl_stage2/HL_Live_Copy_Service.py → _archive/hl_stage2/HL_Live_Copy_Service.py  _Bridges community 2 → community 3_

## Import Cycles
- None detected.

## Communities (10 total, 0 thin omitted)

### Community 0 - "DryRunLiveCopyService"
Cohesion: 0.19
Nodes (13): adverse_diff_pct(), append_csv(), audit_reason_for_fill(), dry_run_intent_audit_decision(), DryRunLiveCopyService, executable_price_from_fill_payload(), fnum(), LeaderFill (+5 more)

### Community 1 - "HL_Live_Copy_Service.py"
Cohesion: 0.12
Nodes (37): atomic_write_json(), audit_notes_for_fill(), classify_ignored_ws_message(), configure_paths(), count_csv_data_rows(), ensure_csv_header(), ensure_csv_schema(), ensure_dirs() (+29 more)

### Community 2 - "DedicatedLiveWSManager"
Cohesion: 0.25
Nodes (7): build_ws_health_snapshot(), DedicatedLiveWSManager, main(), Write health file before sockets open so every subscribed wallet has an entry., utc_now_ms(), write_ws_health(), write_ws_health_initial()

### Community 3 - "Any"
Cohesion: 0.13
Nodes (32): Any, append_send_attempt(), fetch_live_fills_range(), fetch_live_fills_since(), fetch_public_executable_quote(), fixed_notional_buffered_cap(), floor_decimal_to_places(), force_fetch_hl_perp_meta() (+24 more)

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

### Community 10 - "Bootstrap"
Cohesion: 0.33
Nodes (5): Architect bootstrap, Bootstrap, Controller bootstrap, Current first gate: BUILD3_SOURCE_BASELINE_IMPORT_1, Hermes bootstrap

### Community 13 - "Hyperliquid Build 3 Repair"
Cohesion: 0.40
Nodes (4): Hyperliquid Build 3 Repair, Immediate state, Read order, Roles

## Knowledge Gaps
- **30 isolated node(s):** `Product-preservation presumption`, `Objective`, `Known failure`, `Trading-authority precedence (Gate 1 freeze — Architect ruling `B3-A2C-GATE0-PASS-G1-1`)`, `Non-negotiable invariants` (+25 more)
  These have ≤1 connection - possible missing edges or undocumented components.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `self_test()` connect `HL_Live_Copy_Service.py` to `DryRunLiveCopyService`, `DedicatedLiveWSManager`, `Any`?**
  _High betweenness centrality (0.063) - this node is a cross-community bridge._
- **Why does `DryRunLiveCopyService` connect `DryRunLiveCopyService` to `HL_Live_Copy_Service.py`, `DedicatedLiveWSManager`, `Any`?**
  _High betweenness centrality (0.034) - this node is a cross-community bridge._
- **Why does `DedicatedLiveWSManager` connect `DedicatedLiveWSManager` to `HL_Live_Copy_Service.py`, `Any`?**
  _High betweenness centrality (0.031) - this node is a cross-community bridge._
- **What connects `Product-preservation presumption`, `Objective`, `Known failure` to the rest of the system?**
  _30 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `HL_Live_Copy_Service.py` be split into smaller, more focused modules?**
  _Cohesion score 0.11875843454790823 - nodes in this community are weakly interconnected._
- **Should `Any` be split into smaller, more focused modules?**
  _Cohesion score 0.12605042016806722 - nodes in this community are weakly interconnected._
- **Should `Architecture Contract — Hyperliquid Build 3 Repair` be split into smaller, more focused modules?**
  _Cohesion score 0.13333333333333333 - nodes in this community are weakly interconnected._