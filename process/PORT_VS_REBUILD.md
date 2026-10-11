# PORT_VS_REBUILD.md — port-vs-rebuild audit (REVIEW ONLY, advisory, no code changes)

Job: `claude-build3-PA-1791709533` · TARGET_LOGICAL_ROLE=hermes:implementation-owner
Fresh clone: `binancebotty-bot/hyperliquid-build3-repair` @ `4f1c779` → `C:/Users/wigmore/trading_stack/hl-build3-hermes-PA` (core.autocrlf=false), branch `hermes/port-audit`.

## Headline (3 lines)
1. The old build already had three wheels ours just rebuilt: per-wallet **CLOSE_ONLY** (`wallet_mode`/`effective_wallet_action`), a **persisted leader-poll cursor + stale-replay guard** (`run_cycle`, `stale_snapshot_replay_reason`), and **ledger repair / ownership gating** (`repair_flat_ledger_only_positions`, `_pre_send_ownership_gate`) — ours are broader and test-backed, so porting nothing here is safe.
2. Three whole features have **no old-build equivalent** — **convergence**, **liquidation parity**, **client-order-id (cloid) send idempotency** — they are new in ours and must stay ours; there is nothing to port.
3. Net recommendation: **PORT nothing wholesale; MERGE two small ideas** (old's explicit `DUST_BELOW_MIN_NOTIONAL` terminal taxonomy; old's targeted flat-close repair) and **KEEP OURS** everywhere else — the old paths were more permissive (ignore-stale, in-process-only dedupe) and carry re-send/desync risk ours already closes.

## Sources & method
- **old core** = `HL_Live_Copy_Service_Core.py.bak_pre_convergence_wiring_20260602` (7,705 lines) — *history/evidence/* in spec; on disk: `Hyperliquid scanner/_archive/hl_stage2/`.
- **old screen** = `HL_Copy_App_SSOT_20260513.py` (7,243 lines) — *source-docs/* in spec; on disk: `build3-live-screen-0513-view/hl_stage2/HL_Copy_App_SSOT.py`.
- **old wallet-finder** = `WALLET FINDER HL_Copy_Engine_SSOT.py` (3,348 lines) — read-only, not modified.
- **ours** = repo `_archive/hl_stage2/` (`HL_Live_Copy_Service_Core.py` 11,662 lines, `catchup_plan.py`, `outage_classify.py`, `exchange_truth.py`, `headroom.py`, `convergence_shadow.py`, `test_*.py`).
- **Graphify used FIRST, as required**: read `graphify-out/GRAPH_REPORT.md` (built from `81c394bd`; repo HEAD is `4f1c779`, so the graph is ~stale — treated as a navigation map, every claim re-verified against raw source by grep). Graphify located the god nodes (`self_test`, `build_model_state`, `_live_audit_summary`, `manual_send_one_intent`, `LiveWalletConfig`) and the community split (CORE = `HL_Live_Copy_Service.py`, SSOT = `HL_Copy_App_SSOT.py`, `convergence_shadow.py` isolated hub) that told me *where* each row lives before any broad read; the per-row `file:function` greps below were then done directly.
- Context read: `RUN1/RUN3/RUN4/RUN5_FINDINGS.md` (only RUN*_ on disk; `history/BUILD_HISTORY_REVIEW.md` is **absent** — see Evidence-thinness note).
- **No orders. Nothing touched**: live engine checkout, ports 8012/8014/8031, WALLET FINDER, keys/.env all untouched; only reads + this file.

## Row-by-row

### Row 1 — outage / missed-trade replay + cursor
| Old location (file:function) | Worked in old build? | Differences vs ours | Recommendation |
|---|---|---|---|
| old-core `run_cycle` (`_leader_poll_cursors`, `last_leader_poll_cursor_ms`, `POLL_OVERLAP_MS`), `stale_snapshot_replay_reason`, `_process_leader_fill`; wallet-finder `ingest_real_fills_window`, `fetch_fills_range`, `ingest_fetched_rows` | **Yes, with runtime evidence** — per-wallet cursor persisted to state; wallet-finder logs (`hl_copy_engine_ssot.log`) show live `REAL_FILL_INGEST_START/…DONE reason=restart_catchup|drift_recovery` through 2026-10-08 | Ours: dedicated `catchup_plan.py` + `outage_classify.py` (defer/replay/… ), cursor in CORE, `test_core_r1_cursor.py`/`test_core_outage_replay.py`/`outage_defer.py`. Old **ignored** stale snapshots/replays (`STALE_REPLAY_IGNORED`) rather than planning them; old cursor logic was inline in the monolith | **KEEP OURS** — same shape, but old's "ignore stale" could silently drop genuine fills; ours is planned + tested. Risk if ported: lost fills. |

### Row 2 — switch states OFF / CLOSE ONLY / ON
| Old location (file:function) | Worked in old build? | Differences vs ours | Recommendation |
|---|---|---|---|
| old-core `wallet_mode` + `effective_wallet_action` (ON→COPYING, CLO→CLOSE_ONLY, else WALLET_OFF); old-screen `api_get_ui_state`, `_build_live_wallet_rows` | **Yes (code + UI)** — explicit 3-state normaliser `{ON,CLO,OFF}`, dashboard reads `CLOSE_ONLY` | Ours adds a **global** `global_controls.send_mode` (OFF/CLOSE_ONLY/ON) that CLOSE blocks entries+adds and withdraws resting entry limits (commit `b0dda8a`, 2026-10-10), plus per-wallet modes; `test_core_switch_states.py`. Old was per-wallet only, no global gate | **MERGE IDEAS** — ours is a superset and is the operative switch; borrow old's per-wallet granularity if single-wallet CLOSE is ever needed. Risk: low. |

### Row 3 — convergence
| Old location (file:function) | Worked in old build? | Differences vs ours | Recommendation |
|---|---|---|---|
| old-core: **none** (`convergence|converge` = 0 hits). wallet-finder `bootstrap_wallet_from_exchange` (1 incidental hit, not convergence logic) | **No evidence** — feature did not exist | Ours: `convergence_shadow.py` (`compute_convergence_order`) + CORE `converge_once` (23 refs), `start_convergence_thread`; `test_core_run5_converge.py` | **KEEP OURS** — no old equivalent to port. Risk if ported: none (nothing exists). |

### Row 4 — dust close
| Old location (file:function) | Worked in old build? | Differences vs ours | Recommendation |
|---|---|---|---|
| old-core `classify_terminal_state` (`DUST_BELOW_MIN_NOTIONAL`, `BELOW_SYMBOL_MIN_EXCEEDS_MAX_ORDER`), `_validate_final_wire_order` Gate B (min-notional for all lifecycles); old-screen: none (0) | **Partial** — old detects/blocks dust explicitly, but no evidence of a dedicated *dust-close* action | Ours: dust rules + close handling in CORE (20 refs), `test_core_dust_rules.py` | **MERGE IDEAS** — adopt old's explicit `DUST_BELOW_MIN_NOTIONAL` terminal taxonomy into our audit vocabulary (clearer post-hoc reads); keep our close logic. Risk: low. |

### Row 5 — liquidation parity
| Old location (file:function) | Worked in old build? | Differences vs ours | Recommendation |
|---|---|---|---|
| old-core: **none** (`liquidat|liq_` = 0). wallet-finder: 1 incidental `__bool__` hit | **No evidence** — feature did not exist | Ours: `_try_apply_liquidation`, `_is_liquidation_fill`, `liq_parity_block`, `project_liquidation_px`, `_prewarm_with_parity` (72/39 refs), `test_core_liq_parity.py`/`test_core_liq_isolated.py`/`test_core_liq_projection.py` | **KEEP OURS** — no old equivalent. Risk if ported: none. |

### Row 6 — ledger repair / ownership
| Old location (file:function) | Worked in old build? | Differences vs ours | Recommendation |
|---|---|---|---|
| old-core `audit_orphan_attribution`, `repair_flat_ledger_only_positions`, `_try_apply_proven_xyz_flat_close`, `append_live_fill_repair_close`, `_apply_oid_matched_copy_fill`, `_pre_send_ownership_gate`, `_has_pending_exit_guard_proof`; wallet-finder `audit_position_drift_only` (epoch-aware) | **Yes, with runtime evidence** — ledger/ownership/reconcile is the heaviest block in old-core (ledger 234, ownership 63, reconcil 124; run_self_test exercises ledger 82×/ownership 16×); wallet-finder drift_recovery live in logs | Ours: 377/79/166 refs, epoch-aware, `test_core_ledger_repair.py`. RUN5 shows ours applied 22/22 repairs offline but **refused 1 (RESOLV, "unowned fill")** — old had `_try_apply_proven_xyz_flat_close`/`repair_flat_ledger_only_positions` for exactly the flat-position case | **MERGE IDEAS** — ours is stronger overall; borrow old's *proven-flat-close* repair shape to reduce our "unowned fill" refusals. Risk: ownership — any ported repair must keep the sender-lease/ownership gate. |

### Row 7 — send path (idempotency, cloid)
| Old location (file:function) | Worked in old build? | Differences vs ours | Recommendation |
|---|---|---|---|
| old-core `_process_leader_fill` pre-send guard (`_idem_lock`, `_idem_accepted`, guard key = fill_id or stable_hash, blocks same-fill send); old-screen `_row_client_id` | **Partial** — in-process duplicate-fill guard only; **no exchange-level client order id** (cloid = 0 in old-core) | Ours: cloid-based idempotency (`_sdk_cloid`, `_engine_owned_cloids_and_oids`, `_begin_pending_send`, `startup_orphan_order_check`, `_adopt_orphan_order`, 85 refs), `test_t1a_cloid_pending_row.py`/`test_t1b_startup_orphan.py`. Old's guard lived only in RAM → re-send risk across restart | **KEEP OURS** — old cannot survive a restart mid-send; ours can (cloid + orphan adoption). Risk if ported: duplicate orders after crash. |

### Row 8 — hot-path latency / prewarm
| Old location (file:function) | Worked in old build? | Differences vs ours | Recommendation |
|---|---|---|---|
| old-core `__init__` (prewarm) + `run_self_test` (prewarm 2×); wallet-finder: 0 | **Weak/inconclusive** — a minimal `__init__` prewarm only; no keep-alive session | Ours: `_early_prewarm`, `_warm_parity`, `_prewarm_with_parity`, plus a **shared keep-alive HTTP session** for info reads with warm connection between trades (commit `881df9f`, 2026-10-11); `test_http_keepalive.py`, `test_hotpath_replay_bench.py` | **KEEP OURS** — ours is the shared-session warm path the old build lacked. Risk if ported: re-introduces cold-connection latency. |

### Row 9 — audit-write / disk-full
| Old location (file:function) | Worked in old build? | Differences vs ours | Recommendation |
|---|---|---|---|
| old-core `_merge_fresh_disk_before_save`, `atomic_write_json`, `save`/`_load` (disk 19); old-screen `flush`/disk (15/8) | **Partial** — atomic writes + merge-on-save present; **no ENOSPC/disk-full handling or test** (`ENOSPC|no space` = 0) | Ours: disk handling (27 refs) + explicit `test_core_disk_full.py` (20 KB suite); append-only send log (commit `abcf828`) | **KEEP OURS** — ours is the only one with a disk-full test; old had no coverage of the failure mode. Risk if ported: unproven disk-full path. |

## Evidence-thinness (honest)
- `history/BUILD_HISTORY_REVIEW.md` and a dedicated `source-docs/hyperliquid-build3-repair/` tree named in the spec are **not present on this machine**; I mapped them to the on-disk equivalents above. If those exact paths exist elsewhere, rows 1/6 "worked?" verdicts stand on code + wallet-finder logs, not on that review.
- "Worked in old build" = *code present + self-tests + (where noted) live logs*. I did **not** run the old build, so per-row "Yes" means *demonstrably implemented and exercised*, not *re-benchmarked today*. Rows 3/5 are definitively absent.

## Model used (named per part)
- Parts 1–9 (all rows), source mapping, graphify navigation and this write-up: **deepseek-flash (Hermes `deepseek` route)** — free compute, single worker; no OpenRouter nemotron / no zen models used. No paid route touched.
