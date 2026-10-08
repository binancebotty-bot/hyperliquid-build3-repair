# Graph Report - b3-main  (2026-10-08)

## Corpus Check
- 11 files · ~27,503 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 239 nodes · 670 edges · 13 communities
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS · INFERRED: 3 edges (avg confidence: 0.8)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `1f5cc723`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- HL_Live_Copy_Service.py
- DryRunLiveCopyService
- utc_now_iso
- exchange_truth.py
- Path
- Architecture Contract — Hyperliquid Build 3 Repair
- test_g3_exchange_truth.py
- Operating Protocol
- convergence_shadow.py
- Build 3 — Product Semantics, Non-Goals and Measurable DONE (Gate 1 freeze)
- Bootstrap
- Hyperliquid Build 3 Repair
- FixedModeAuthorityConflict

## God Nodes (most connected - your core abstractions)
1. `self_test()` - 50 edges
2. `DryRunLiveCopyService` - 37 edges
3. `LeaderFill` - 29 edges
4. `fnum()` - 26 edges
5. `utc_now_iso()` - 24 edges
6. `manual_send_one_intent()` - 20 edges
7. `LiveWalletConfig` - 20 edges
8. `inum()` - 17 edges
9. `DedicatedLiveWSManager` - 15 edges
10. `append_csv()` - 13 edges

## Surprising Connections (you probably didn't know these)
- `main()` --calls--> `fresh()`  [INFERRED]
  _archive/hl_stage2/test_g2_copy_correctness.py → _archive/hl_stage2/test_g3_exchange_truth.py

## Import Cycles
- None detected.

## Communities (13 total, 0 thin omitted)

### Community 0 - "HL_Live_Copy_Service.py"
Cohesion: 0.12
Nodes (50): Any, append_send_attempt(), classify_ignored_ws_message(), extract_ws_fills(), extract_ws_fills_with_meta(), fetch_live_fills_range(), fetch_live_fills_since(), fetch_public_executable_quote() (+42 more)

### Community 1 - "DryRunLiveCopyService"
Cohesion: 0.09
Nodes (28): adverse_diff_pct(), append_csv(), audit_notes_for_fill(), audit_reason_for_fill(), dry_run_intent_audit_decision(), DryRunLiveCopyService, event_authorised_desired_net(), executable_price_from_fill_payload() (+20 more)

### Community 2 - "utc_now_iso"
Cohesion: 0.22
Nodes (8): build_ws_health_snapshot(), DedicatedLiveWSManager, main(), Write health file before sockets open so every subscribed wallet has an entry., utc_now_iso(), utc_now_ms(), write_ws_health(), write_ws_health_initial()

### Community 3 - "exchange_truth.py"
Cohesion: 0.16
Nodes (17): identity_ok(), list_perp_dexes(), master_account_net(), master_userfills(), _match(), _post(), G3 EXCHANGE_TRUTH / SETTLEMENT seam (ruling B3-A2C-G2-PASS-G3-1). Read-only…, Clear an in-flight reservation ONLY from independent MASTER evidence for this… (+9 more)

### Community 4 - "Path"
Cohesion: 0.14
Nodes (15): atomic_write_json(), configure_paths(), count_csv_data_rows(), ensure_csv_header(), ensure_csv_schema(), ensure_dirs(), last_csv_row(), load_auto_send_attempt_ids() (+7 more)

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

## Knowledge Gaps
- **30 isolated node(s):** `Product-preservation presumption`, `Objective`, `Known failure`, `Trading-authority precedence (Gate 1 freeze — Architect ruling `B3-A2C-GATE0-PASS-G1-1`)`, `Non-negotiable invariants` (+25 more)
  These have ≤1 connection - possible missing edges or undocumented components.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `DryRunLiveCopyService` connect `DryRunLiveCopyService` to `HL_Live_Copy_Service.py`, `utc_now_iso`, `Path`?**
  _High betweenness centrality (0.081) - this node is a cross-community bridge._
- **Why does `self_test()` connect `HL_Live_Copy_Service.py` to `DryRunLiveCopyService`, `utc_now_iso`, `Path`?**
  _High betweenness centrality (0.052) - this node is a cross-community bridge._
- **Why does `DedicatedLiveWSManager` connect `utc_now_iso` to `HL_Live_Copy_Service.py`?**
  _High betweenness centrality (0.029) - this node is a cross-community bridge._
- **What connects `Product-preservation presumption`, `Objective`, `Known failure` to the rest of the system?**
  _30 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `HL_Live_Copy_Service.py` be split into smaller, more focused modules?**
  _Cohesion score 0.11623376623376623 - nodes in this community are weakly interconnected._
- **Should `DryRunLiveCopyService` be split into smaller, more focused modules?**
  _Cohesion score 0.0936026936026936 - nodes in this community are weakly interconnected._
- **Should `Path` be split into smaller, more focused modules?**
  _Cohesion score 0.13970588235294118 - nodes in this community are weakly interconnected._