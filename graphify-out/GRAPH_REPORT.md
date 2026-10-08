# Graph Report - b3-main  (2026-10-08)

## Corpus Check
- 21 files · ~62,055 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 505 nodes · 1720 edges · 26 communities (22 shown, 4 thin omitted)
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS · INFERRED: 2 edges (avg confidence: 0.8)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `8d93c500`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- HL_Live_Copy_Service.py
- fnum
- DedicatedLiveWSManager
- exchange_truth.py
- DryRunLiveCopyService
- Architecture Contract — Hyperliquid Build 3 Repair
- JSONResponse
- Operating Protocol
- convergence_shadow.py
- Build 3 — Product Semantics, Non-Goals and Measurable DONE (Gate 1 freeze)
- Bootstrap
- Hyperliquid Build 3 Repair
- build_model_state
- _archive_manual_reconciliation_ledger_row
- .__init__
- HL_Copy_App_SSOT.py
- Any
- self_test
- render_home
- .settle_from_master_evidence
- fnum
- block_num
- .convergence_notional_for_fill
- test_g4_fixed_slices.py
- .wallet_gate
- test_g4_ui_controls.py

## God Nodes (most connected - your core abstractions)
1. `fnum()` - 55 edges
2. `self_test()` - 50 edges
3. `DryRunLiveCopyService` - 47 edges
4. `build_model_state()` - 34 edges
5. `fnum()` - 33 edges
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

## Communities (26 total, 4 thin omitted)

### Community 0 - "HL_Live_Copy_Service.py"
Cohesion: 0.11
Nodes (49): attach_send_result(), build_ws_health_snapshot(), clear_unresolved_send(), fetch_live_fills_since(), fetch_public_executable_quote(), fixed_notional_buffered_cap(), floor_decimal_to_places(), force_fetch_hl_perp_meta() (+41 more)

### Community 1 - "fnum"
Cohesion: 0.16
Nodes (16): adverse_diff_pct(), audit_notes_for_fill(), audit_reason_for_fill(), dry_run_intent_audit_decision(), executable_price_from_fill_payload(), fnum(), LeaderFill, LiveWalletConfig (+8 more)

### Community 2 - "DedicatedLiveWSManager"
Cohesion: 0.21
Nodes (5): DedicatedLiveWSManager, FixedModeAuthorityConflict, The intended fixed-mode target exposure cannot be proven from durable evidence., write_ws_health(), Exception

### Community 3 - "exchange_truth.py"
Cohesion: 0.07
Nodes (35): _fill_key(), identity_ok(), list_perp_dexes(), master_account_net(), master_userfills(), master_userfills_all_dexes(), _match(), G3 EXCHANGE_TRUTH / SETTLEMENT seam (ruling B3-A2C-G2-PASS-G3-1). Read-only… (+27 more)

### Community 4 - "DryRunLiveCopyService"
Cohesion: 0.16
Nodes (13): append_csv(), append_send_attempt(), DryRunLiveCopyService, fetch_live_fills_range(), load_json(), main(), NO-SEND recovery/baseline boundary: freeze UNATTRIBUTED_BASELINE[coin] =…, Semantics 6: before convergence may authorise a send, MASTER truth must… (+5 more)

### Community 5 - "Architecture Contract — Hyperliquid Build 3 Repair"
Cohesion: 0.13
Nodes (14): Architect's job, Architecture Contract — Hyperliquid Build 3 Repair, Automatic Architect escalation, Build 4 requirements source set, Chosen repair, Completion definition, Conflict rule, Full project acceptance scope (+6 more)

### Community 6 - "JSONResponse"
Cohesion: 0.12
Nodes (48): _post(), Read-only POST to /info; `fetcher` is injected so tests use offline fixtures., add_live_config_wallet(), admin_purge_wallet(), api_equity(), api_get_ui_state(), api_metrics(), api_norm() (+40 more)

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

### Community 12 - "build_model_state"
Cohesion: 0.09
Nodes (40): alignment_status_for_key(), _apply_price_model(), atomic_write_csv(), atomic_write_json(), avg(), backup_purge_files(), block(), bps_fee() (+32 more)

### Community 13 - "_archive_manual_reconciliation_ledger_row"
Cohesion: 0.16
Nodes (18): _account_reconciliation_baseline_timestamp(), _append_exchange_history(), _archive_manual_reconciliation_ledger_row(), _build_account_reconciliation(), _earliest_real_order_filled_ms(), _fetch_exchange_account_snapshot(), _fetch_user_fills_by_time(), _fetch_user_realized_pnl_snapshot() (+10 more)

### Community 14 - ".__init__"
Cohesion: 0.25
Nodes (6): ensure_dirs(), load_auto_send_attempt_ids(), load_csv_ids(), load_unresolved_sends(), A persisted lineage checkpoint is valid only if durably coupled to the…, Unresolved send reservations from the EXISTING service-state file (durable…

### Community 15 - "HL_Copy_App_SSOT.py"
Cohesion: 0.12
Nodes (41): _active_live_copy_wallet_count(), _build_execution_quality_rows(), _build_execution_quality_summary(), _build_live_leader_performance(), _build_live_wallet_derived(), _build_live_wallet_rows(), build_portfolio_history(), _build_recent_send_warning_groups() (+33 more)

### Community 16 - "Any"
Cohesion: 0.14
Nodes (28): active_wallet(), active_wallet_row(), contract_money_equal(), _copy_cost_bps(), _copy_friction_bps(), core_missing(), core_td(), css_class() (+20 more)

### Community 17 - "self_test"
Cohesion: 0.16
Nodes (20): atomic_write_json(), classify_ignored_ws_message(), configure_paths(), count_csv_data_rows(), ensure_csv_header(), ensure_csv_schema(), extract_ws_fills(), extract_ws_fills_with_meta() (+12 more)

### Community 18 - "render_home"
Cohesion: 0.30
Nodes (15): dash_td(), dual(), format_dd(), get_current_dd(), get_max_dd(), inum(), Validate dashboard cell contract. Returns list of error strings; never throws., render_home() (+7 more)

### Community 20 - "fnum"
Cohesion: 0.15
Nodes (18): _build_manual_reconciliation_rows(), _build_real_copy_positions(), _clean_wallet_config(), effective_wallet_ui(), fnum(), health_status_label(), _manual_position_sleeves(), model_copy_notional() (+10 more)

### Community 21 - "block_num"
Cohesion: 0.43
Nodes (7): block_num(), dd_current(), dd_max(), latest_history_block_dd(), max_history_block_dd(), Read numeric metric fields with legacy alias fallback., Return latest combined curve DD when the rendered block lacks it. Used only as…

### Community 22 - ".convergence_notional_for_fill"
Cohesion: 0.11
Nodes (13): event_authorised_desired_net(), proportional_sleeve_scale(), Persisted attributed fixed-sleeve magnitude for (wallet, coin) - EXISTING state…, A ledger entry is AUTHORITATIVE only when well formed AND side-consistent. -…, ONLY wallets with a VALID attributed sleeve ledger are released from the hold.…, Authoritative ACCOUNT-NET follower exposure (signed). G2 has no live plumbing…, Frozen unattributed (unowned) same-coin inventory. Attribution only - never…, Desired (event-authorised) vs ACCOUNT-NET actual -> the single safe next order. (+5 more)

## Knowledge Gaps
- **30 isolated node(s):** `Product-preservation presumption`, `Objective`, `Known failure`, `Trading-authority precedence (Gate 1 freeze — Architect ruling `B3-A2C-GATE0-PASS-G1-1`)`, `Non-negotiable invariants` (+25 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **4 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `_post()` connect `JSONResponse` to `exchange_truth.py`, `_archive_manual_reconciliation_ledger_row`?**
  _High betweenness centrality (0.408) - this node is a cross-community bridge._
- **Why does `DryRunLiveCopyService` connect `DryRunLiveCopyService` to `HL_Live_Copy_Service.py`, `fnum`, `DedicatedLiveWSManager`, `.__init__`, `self_test`, `.settle_from_master_evidence`, `.convergence_notional_for_fill`, `.wallet_gate`?**
  _High betweenness centrality (0.087) - this node is a cross-community bridge._
- **Why does `_archive_manual_reconciliation_ledger_row()` connect `_archive_manual_reconciliation_ledger_row` to `JSONResponse`, `build_model_state`, `HL_Copy_App_SSOT.py`, `Any`, `fnum`?**
  _High betweenness centrality (0.047) - this node is a cross-community bridge._
- **What connects `Product-preservation presumption`, `Objective`, `Known failure` to the rest of the system?**
  _30 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `HL_Live_Copy_Service.py` be split into smaller, more focused modules?**
  _Cohesion score 0.10522496371552975 - nodes in this community are weakly interconnected._
- **Should `exchange_truth.py` be split into smaller, more focused modules?**
  _Cohesion score 0.06829268292682927 - nodes in this community are weakly interconnected._
- **Should `Architecture Contract — Hyperliquid Build 3 Repair` be split into smaller, more focused modules?**
  _Cohesion score 0.13333333333333333 - nodes in this community are weakly interconnected._