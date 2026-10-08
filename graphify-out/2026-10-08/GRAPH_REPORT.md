# Graph Report - b3-main  (2026-10-08)

## Corpus Check
- 24 files · ~65,163 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 513 nodes · 1736 edges · 21 communities (17 shown, 4 thin omitted)
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS · INFERRED: 2 edges (avg confidence: 0.8)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `1bb7a406`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- HL_Live_Copy_Service.py
- fnum
- DedicatedLiveWSManager
- exchange_truth.py
- DryRunLiveCopyService
- Architecture Contract — Hyperliquid Build 3 Repair
- get
- Operating Protocol
- convergence_shadow.py
- Build 3 — Product Semantics, Non-Goals and Measurable DONE (Gate 1 freeze)
- Bootstrap
- Hyperliquid Build 3 Repair
- load_json
- append_csv
- parse_leader_fill_row
- HL_Copy_App_SSOT.py
- test_g4_order_cap.py
- self_test
- .convergence_notional_for_fill
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

## Communities (21 total, 4 thin omitted)

### Community 0 - "HL_Live_Copy_Service.py"
Cohesion: 0.10
Nodes (53): append_send_attempt(), attach_send_result(), clear_unresolved_send(), extract_ws_fills(), extract_ws_fills_with_meta(), fetch_live_fills_range(), fetch_live_fills_since(), fetch_public_executable_quote() (+45 more)

### Community 1 - "fnum"
Cohesion: 0.20
Nodes (12): adverse_diff_pct(), audit_reason_for_fill(), dry_run_intent_audit_decision(), executable_price_from_fill_payload(), fnum(), LeaderFill, LiveWalletConfig, Mutate the genuine post-baseline leader EVENT lineage for (wallet, coin). The… (+4 more)

### Community 2 - "DedicatedLiveWSManager"
Cohesion: 0.18
Nodes (10): build_ws_health_snapshot(), DedicatedLiveWSManager, FixedModeAuthorityConflict, main(), Write health file before sockets open so every subscribed wallet has an entry., The intended fixed-mode target exposure cannot be proven from durable evidence., utc_now_ms(), write_ws_health() (+2 more)

### Community 3 - "exchange_truth.py"
Cohesion: 0.07
Nodes (35): _fill_key(), identity_ok(), list_perp_dexes(), master_account_net(), master_userfills(), master_userfills_all_dexes(), _match(), G3 EXCHANGE_TRUTH / SETTLEMENT seam (ruling B3-A2C-G2-PASS-G3-1). Read-only… (+27 more)

### Community 4 - "DryRunLiveCopyService"
Cohesion: 0.11
Nodes (11): DryRunLiveCopyService, Release the in-flight reservation ONLY for its own intent and ONLY on a…, Clear an in-flight reservation ONLY from independent MASTER evidence (semantics…, NO-SEND recovery/baseline boundary: freeze UNATTRIBUTED_BASELINE[coin] =…, Semantics 6: before convergence may authorise a send, MASTER truth must…, Operator global control max_order_notional_usd, read from the EXISTING…, Explicit fail-closed status when a NEW ENTRY exceeds the operator cap, else "".…, READ-ONLY UI compatibility bridge (restored Build3 UI -> repaired engine). The… (+3 more)

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

### Community 14 - "parse_leader_fill_row"
Cohesion: 0.50
Nodes (4): load_leader_fills(), parse_leader_fill_row(), parse_raw_json(), trade_delta_from_side()

### Community 15 - "HL_Copy_App_SSOT.py"
Cohesion: 0.05
Nodes (123): active_wallet(), active_wallet_row(), alignment_status_for_key(), _append_exchange_history(), _apply_price_model(), avg(), block(), block_num() (+115 more)

### Community 17 - "self_test"
Cohesion: 0.13
Nodes (23): atomic_write_json(), audit_notes_for_fill(), classify_ignored_ws_message(), configure_paths(), count_csv_data_rows(), ensure_csv_header(), ensure_csv_schema(), ensure_dirs() (+15 more)

### Community 22 - ".convergence_notional_for_fill"
Cohesion: 0.11
Nodes (13): event_authorised_desired_net(), proportional_sleeve_scale(), Persisted attributed fixed-sleeve magnitude for (wallet, coin) - EXISTING state…, A ledger entry is AUTHORITATIVE only when well formed AND side-consistent. -…, ONLY wallets with a VALID attributed sleeve ledger are released from the hold.…, Authoritative ACCOUNT-NET follower exposure (signed). G2 has no live plumbing…, Frozen unattributed (unowned) same-coin inventory. Attribution only - never…, Desired (event-authorised) vs ACCOUNT-NET actual -> the single safe next order. (+5 more)

## Knowledge Gaps
- **31 isolated node(s):** `Product-preservation presumption`, `Objective`, `Known failure`, `Trading-authority precedence (Gate 1 freeze — Architect ruling `B3-A2C-GATE0-PASS-G1-1`)`, `Non-negotiable invariants` (+26 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **4 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `_post()` connect `get` to `exchange_truth.py`, `load_json`?**
  _High betweenness centrality (0.402) - this node is a cross-community bridge._
- **Why does `DryRunLiveCopyService` connect `DryRunLiveCopyService` to `HL_Live_Copy_Service.py`, `fnum`, `DedicatedLiveWSManager`, `append_csv`, `self_test`, `.convergence_notional_for_fill`?**
  _High betweenness centrality (0.091) - this node is a cross-community bridge._
- **Why does `_archive_manual_reconciliation_ledger_row()` connect `load_json` to `get`, `HL_Copy_App_SSOT.py`?**
  _High betweenness centrality (0.046) - this node is a cross-community bridge._
- **What connects `Product-preservation presumption`, `Objective`, `Known failure` to the rest of the system?**
  _31 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `HL_Live_Copy_Service.py` be split into smaller, more focused modules?**
  _Cohesion score 0.09935064935064936 - nodes in this community are weakly interconnected._
- **Should `exchange_truth.py` be split into smaller, more focused modules?**
  _Cohesion score 0.06829268292682927 - nodes in this community are weakly interconnected._
- **Should `DryRunLiveCopyService` be split into smaller, more focused modules?**
  _Cohesion score 0.11083743842364532 - nodes in this community are weakly interconnected._