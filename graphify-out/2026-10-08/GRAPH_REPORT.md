# Graph Report - b3-main  (2026-10-08)

## Corpus Check
- 13 files · ~57,223 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 490 nodes · 1693 edges · 24 communities (22 shown, 2 thin omitted)
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS · INFERRED: 1 edges (avg confidence: 0.8)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `b64f9a47`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- HL_Live_Copy_Service.py
- DryRunLiveCopyService
- DedicatedLiveWSManager
- exchange_truth.py
- Path
- Architecture Contract — Hyperliquid Build 3 Repair
- get
- Operating Protocol
- convergence_shadow.py
- Build 3 — Product Semantics, Non-Goals and Measurable DONE (Gate 1 freeze)
- Bootstrap
- Hyperliquid Build 3 Repair
- HL_Copy_App_SSOT.py
- _live_audit_summary
- load_json
- Any
- render_home
- atomic_write_json
- utc_now_iso
- master_net_snapshot
- fnum
- block_num
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
Cohesion: 0.12
Nodes (49): append_send_attempt(), build_ws_health_snapshot(), classify_ignored_ws_message(), extract_ws_fills(), extract_ws_fills_with_meta(), fetch_live_fills_range(), fetch_live_fills_since(), fetch_public_executable_quote() (+41 more)

### Community 1 - "DryRunLiveCopyService"
Cohesion: 0.12
Nodes (18): adverse_diff_pct(), audit_reason_for_fill(), dry_run_intent_audit_decision(), DryRunLiveCopyService, executable_price_from_fill_payload(), fnum(), LeaderFill, LiveWalletConfig (+10 more)

### Community 2 - "DedicatedLiveWSManager"
Cohesion: 0.21
Nodes (6): DedicatedLiveWSManager, FixedModeAuthorityConflict, main(), The intended fixed-mode target exposure cannot be proven from durable evidence., write_ws_health(), Exception

### Community 3 - "exchange_truth.py"
Cohesion: 0.07
Nodes (33): _fill_key(), identity_ok(), list_perp_dexes(), master_account_net(), master_userfills(), master_userfills_all_dexes(), _match(), G3 EXCHANGE_TRUTH / SETTLEMENT seam (ruling B3-A2C-G2-PASS-G3-1). Read-only… (+25 more)

### Community 4 - "Path"
Cohesion: 0.15
Nodes (15): atomic_write_json(), configure_paths(), count_csv_data_rows(), ensure_csv_header(), ensure_csv_schema(), last_csv_row(), load_leader_fills(), load_local_env_file() (+7 more)

### Community 5 - "Architecture Contract — Hyperliquid Build 3 Repair"
Cohesion: 0.13
Nodes (14): Architect's job, Architecture Contract — Hyperliquid Build 3 Repair, Automatic Architect escalation, Build 4 requirements source set, Chosen repair, Completion definition, Conflict rule, Full project acceptance scope (+6 more)

### Community 6 - "get"
Cohesion: 0.12
Nodes (57): _post(), Read-only POST to /info; `fetcher` is injected so tests use offline fixtures., _active_live_copy_wallet_count(), add_live_config_wallet(), admin_purge_wallet(), api_equity(), api_get_ui_state(), api_metrics() (+49 more)

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
Cohesion: 0.09
Nodes (41): alignment_status_for_key(), _apply_price_model(), block(), bps_fee(), build_model_state(), build_portfolio_history(), calc_unrealized(), _clean_wallet_include() (+33 more)

### Community 13 - "_live_audit_summary"
Cohesion: 0.12
Nodes (31): _account_reconciliation_baseline_timestamp(), _append_exchange_history(), _archive_manual_reconciliation_ledger_row(), _build_account_reconciliation(), _build_execution_quality_rows(), _build_execution_quality_summary(), _build_live_wallet_rows(), _build_recent_send_warning_groups() (+23 more)

### Community 14 - "load_json"
Cohesion: 0.11
Nodes (19): attach_send_result(), audit_notes_for_fill(), clear_unresolved_send(), ensure_dirs(), load_auto_send_attempt_ids(), load_csv_ids(), load_json(), load_unresolved_sends() (+11 more)

### Community 15 - "Any"
Cohesion: 0.15
Nodes (25): active_wallet(), active_wallet_row(), contract_money_equal(), core_missing(), core_td(), css_class(), dual_cell_core(), enforce_live_wallet_limit() (+17 more)

### Community 16 - "render_home"
Cohesion: 0.17
Nodes (21): avg(), dash_td(), dual(), dual_or_dash(), fmt_dual_or_dash(), fmt_money_or_dash(), format_dd(), get_max_dd() (+13 more)

### Community 17 - "atomic_write_json"
Cohesion: 0.26
Nodes (17): atomic_write_csv(), atomic_write_json(), backup_purge_files(), invalidate_model_cache(), load_local_env_file(), load_purged_wallets(), normalise_wallet_for_purge(), persist_model_state() (+9 more)

### Community 18 - "utc_now_iso"
Cohesion: 0.21
Nodes (6): append_csv(), NO-SEND recovery/baseline boundary: freeze UNATTRIBUTED_BASELINE[coin] =…, Semantics 6: before convergence may authorise a send, MASTER truth must…, should_write_would_send(), utc_now_iso(), BaseException

### Community 20 - "fnum"
Cohesion: 0.21
Nodes (15): _build_live_leader_performance(), _build_live_wallet_derived(), _build_manual_reconciliation_rows(), _build_real_copy_positions(), fnum(), iter_manual_wallet_positions(), _manual_live_summary(), _manual_position_sleeves() (+7 more)

### Community 21 - "block_num"
Cohesion: 0.36
Nodes (8): block_num(), dd_current(), dd_max(), get_current_dd(), latest_history_block_dd(), max_history_block_dd(), Read numeric metric fields with legacy alias fallback., Return latest combined curve DD when the rendered block lacks it. Used only as…

### Community 22 - "event_authorised_desired_net"
Cohesion: 0.33
Nodes (6): event_authorised_desired_net(), proportional_sleeve_scale(), Proportional sleeve scale: leader position x scale = copied exposure., Map an event-authorised leader signed position to this wallet's copied sleeve.…, Aggregate same-coin wallet sleeves into ONE signed account-net desired value.…, sleeve_from_leader_event_position()

## Knowledge Gaps
- **30 isolated node(s):** `Product-preservation presumption`, `Objective`, `Known failure`, `Trading-authority precedence (Gate 1 freeze — Architect ruling `B3-A2C-GATE0-PASS-G1-1`)`, `Non-negotiable invariants` (+25 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **2 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `_post()` connect `get` to `exchange_truth.py`, `_live_audit_summary`?**
  _High betweenness centrality (0.411) - this node is a cross-community bridge._
- **Why does `DryRunLiveCopyService` connect `DryRunLiveCopyService` to `HL_Live_Copy_Service.py`, `DedicatedLiveWSManager`, `utc_now_iso`, `load_json`?**
  _High betweenness centrality (0.069) - this node is a cross-community bridge._
- **Why does `_archive_manual_reconciliation_ledger_row()` connect `_live_audit_summary` to `get`, `HL_Copy_App_SSOT.py`, `Any`, `atomic_write_json`, `fnum`?**
  _High betweenness centrality (0.047) - this node is a cross-community bridge._
- **What connects `Product-preservation presumption`, `Objective`, `Known failure` to the rest of the system?**
  _30 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `HL_Live_Copy_Service.py` be split into smaller, more focused modules?**
  _Cohesion score 0.12191582002902758 - nodes in this community are weakly interconnected._
- **Should `DryRunLiveCopyService` be split into smaller, more focused modules?**
  _Cohesion score 0.12173913043478261 - nodes in this community are weakly interconnected._
- **Should `exchange_truth.py` be split into smaller, more focused modules?**
  _Cohesion score 0.07396870554765292 - nodes in this community are weakly interconnected._