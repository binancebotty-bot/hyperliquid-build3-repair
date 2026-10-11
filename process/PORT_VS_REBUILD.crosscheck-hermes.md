> Independent cross-check by a second lane. The spec-path deliverable is `process/PORT_VS_REBUILD.md`
> (already on this branch, 72 lines). This file is my own row-by-row audit produced from the same sources
> without reading that file first; where the two disagree, reconcile them rather than silently replacing one.

# PORT_VS_REBUILD - old (May) build vs this week's rebuild, row by row (REVIEW ONLY, advisory)

**Job PA** (spec `PORT_AUDIT_SPEC.md`). Branch `hermes/port-audit`. **Model: deepseek-flash** (Hermes session, all
parts; no worker - the only reachable delegation route is the excluded config model). Read-only: nothing was modified
or run; the old-build files were opened read-only and no key file was opened.

**Sources read** - current (repo `main` at clone time): `_archive/hl_stage2/HL_Live_Copy_Service_Core.py` (11,662 lines),
`catchup_plan.py`, `test_*.py`. Old build: `Hyperliquid scanner/_archive/hl_stage2/
HL_Live_Copy_Service_Core.py.bak_pre_convergence_wiring_20260602` (7,705 lines - the master doc records this backup as
*the engine that traded* in May, SHA-256 `5bda57be...`), `Hyperliquid scanner/WALLET FINDER/HL_Copy_Engine_SSOT.py`
(3,348), `build3-live-screen-0513-view/hl_stage2/HL_Copy_App_SSOT.py` (7,243, the certified 13 May UI), and
`hl-build3-testnet-cert-evidence/RUN{1,3,4,5}_FINDINGS.md`. **`history/BUILD_HISTORY_REVIEW.md` is NOT on this PC** and
no old-build run artifacts survive here, so "worked in the old build" below rests on that provenance plus the code -
never on a measurement. Say it plainly: the old build has no measured evidence on this machine.

**Graphify**: the clone ships `graphify-out/graph.json`; queries for "missed trade replay cursor", "send mode switch
close only" and "prewarm hot path workers" were run against it. It pointed at `HL_Live_Copy_Service.py` L2949
("Effective UI-gate mode for a wallet: ON | OFF | CLOSE_ONLY") - which is how the per-wallet three-state gate was
found to PREDATE this week - and at the SSOT service layer for the exchange snapshot; the row-level file:line below
then came from targeted search of the two engines.

## Headline

1. **Nothing in the old build is worth porting wholesale.** Five rows have no equivalent at all (convergence,
   liquidation parity) or a version ours was rebuilt from *and then extended* (send idempotency, prewarm, atomic write).
2. **The two rows where the old build is genuinely different are DUST and the SWITCH** - and in both the old behaviour
   is worse: it allowed ANY sub-min exit (the dust runs 4/5 measured) and had only a per-wallet
   ON/CLOSE_ONLY/OFF, no global tri-state.
3. **Porting would trade measured behaviour for unmeasured** - every number we have (runs 1-5, the RE3 replay, the dust
   and disk-full tests) is about OUR version; the old build's record here is provenance, not evidence.

## Rows

### 1. Outage / missed-trade replay + cursor
| | |
|---|---|
| old location | `..._20260602: ServiceStateWriter` cursor persistence **L5704-5732** (`last_leader_poll_cursor_ms` kept across fast cycles); missed-entry terminal mapping **L333-345**; `DedupeStore` **L1980**; pre-send idempotency seed **L5759-5768** |
| worked in old build? | Shipped in the traded engine (provenance). **No measurement on this PC** - no replay test, no outage run. |
| differences vs ours | Ours adds the restart-replay **floor** (`leader_cursor_next` refuses to pass an unprocessed fill), `merged_fill_ids` absorption, `already_closed_late_entries` (60 s age rule) and the RE3 outage replay + `OUTAGE_RESULT` evidence (720 missed, 0 replayed twice). Old had a cursor but no stated guarantee. |
| recommendation | **KEEP OURS** - porting the old cursor drops the floor and the only measured replay result we have. |
| risk | High if ported: silent window loss after a restart (exactly the R3 risk in `CATCHUP_WIRING_REVIEW.md`). |

### 2. Switch states OFF / CLOSE ONLY / ON
| | |
|---|---|
| old location | `ConfigManager.wallet_mode` **L1906-1913** (per-wallet ON / CLOSE_ONLY / OFF), `effective_wallet_action` **L1874-1880**, `wallet_mode_counts` **L1862-1872**, global `auto_send_enabled` / `MASTER_REAL_ORDERS_OFF` **L1848-1860** |
| worked in old build? | Yes - shipped, and the 13 May UI copy uses LIVE / CLO / OFF (provenance + code). |
| differences vs ours | Ours adds a **global** tri-state (`send_mode_now`/`master_switch_now`), **withdraws resting entry limits on CLOSE** (S9) and never sends a queued order after a switch to OFF (D2). Old: per-wallet only, and disarm latency was never addressed (run 4 R5 was about ours). |
| recommendation | **KEEP OURS**; MERGE IDEA: reuse the old LIVE/CLO/OFF label set if the UI needs it - cosmetic only. |
| risk | Low for the cosmetic merge; high if the old per-wallet model replaced the global gate (loses the global kill). |

### 3. Convergence
| | |
|---|---|
| old location | **None.** 0 hits for converge / convergence / target_position / sync_position in the 7,705-line engine; only the ledger-level `_merge_fresh_disk_before_save` **L2220-2254**. The backup's own filename says *pre-convergence-wiring*. |
| worked in old build? | N/A - absent. |
| differences vs ours | Ours has ~55 references (convergence pass, standing recovery closes, `CLOSE_RECOVERY_*` terminals, `STANDING_CLOSES_FILE`). |
| recommendation | **KEEP OURS** - there is nothing to port. |
| risk | Porting backwards = reinstating pre-wiring behaviour; no upside. |

### 4. Dust close
| | |
|---|---|
| old location | `ConfigManager.min_notional` **L1925**, block at **L2439** (`copy_notional < min and lifecycle in {"ENTRY","ADD"}`), `DUST_BELOW_MIN_NOTIONAL` mapping **L325**, uplift `cfg_min_for_uplift` **L3218** |
| worked in old build? | Shipped - and it produced the dust: the old gate blocks only ENTRY/ADD, so **any** sub-min exit went out, which is the behaviour runs 4/5 measured (dust persisting at each sample). |
| differences vs ours | Ours allows a sub-min order **only** when it closes the WHOLE account position (reduce-only, ledger must agree with the exchange), else blocks and records `DUST_BELOW_MIN_NOTIONAL` + `HOLD_DUST_OR_AGGREGATE`. |
| recommendation | **KEEP OURS** - porting the old rule re-opens the measured dust defect. |
| risk | High if ported; the F1 test (`test_core_dust_rules.py`, 11 checks) pins ours. |

### 5. Liquidation parity (+ cross 3x)
| | |
|---|---|
| old location | **None.** 0 hits for liquidation / liquidationPx / update_leverage / cross in the old engine. |
| worked in old build? | N/A - absent (the feature is this week's, PR #41). |
| differences vs ours | Ours: `updateLeverage` cross once per asset before its first order, a projected follower liquidation compared with the SAFEST leader, fail-closed when unprovable. |
| recommendation | **KEEP OURS** - nothing to port. |
| risk | N/A (the gap is that ours has no live evidence yet - see the F2/J4 gap list, not a porting question). |

### 6. Ledger repair / ownership
| | |
|---|---|
| old location | ownership-gate vocabulary **L1087-1132** (`OWNERSHIP_GATE_ACCOUNT_RESIDUAL`, `..._SIGN_CONFLICT`, `..._UNRESOLVED_SYMBOL`), hard-copy counters incl. `VALID_BLOCKED_BY_OWNERSHIP_GATE` **L1107**, `_merge_fresh_disk_before_save` **L2220-2254** (keeps newer on-disk repairs over a stale in-memory sleeve) |
| worked in old build? | Shipped (provenance). The ownership vocabulary in ours is visibly its descendant. |
| differences vs ours | Ours adds T2 adoption **by exchange order id** (`--adopt-oid`, refuses without the flag, no exchange write), the repair commands (`--repair-ledger-catch-up`, `--repair-flat-ledger-only`), refused-coin isolation, archived-residual accounting and `unowned` detection (28 refs). |
| recommendation | **KEEP OURS**; MERGE IDEA: read the old disk-mtime merge idea explicitly against our repair paths (it is the same intent as our "never clobber newer disk truth"). |
| risk | Medium: porting the old ownership gate wholesale would drop the audited adoption guards that runs 3-6 were built around. |

### 7. Send path: idempotency, cloid
| | |
|---|---|
| old location | pre-send idempotency guard **L5759-5768** (plain `Lock`, `_idem_accepted` seeded from `SEND_ATTEMPTS_CSV`, `_idem_duplicate_audited`), `DedupeStore` **L1980**, `attempt_id` 4 refs |
| worked in old build? | Yes - shipped; its own comments describe the restart / cross-instance race it was built for. |
| differences vs ours | Ours keeps that guard and adds a **deterministic cloid** per intent and a **pending_send row written BEFORE the exchange call** (T1a, shared attempt_id), so an order the exchange accepted just before a crash is identifiable. **The old engine has 0 cloid references** - that failure mode was unhandled there. |
| recommendation | **KEEP OURS** (it *is* the old guard, extended). |
| risk | High if ported: unidentifiable resting orders after a crash. |

### 8. Hot-path latency / prewarm
| | |
|---|---|
| old location | `warm_symbol_cache()` / `warm_exchange_client()` **L5775-5778** (gated on `auto_send_enabled` + `HL_LIVE_PREWARM_SYMBOL_META`/`..._SDK_CLIENT`), hot queue maxsize 50 000 **L5770**, `hot_send_workers` **L5771**, `_hot_send_loop` threads **L5787-5790** |
| worked in old build? | Shipped (provenance); no latency measurement survives on this PC. |
| differences vs ours | Ours adds the **parity-gate leader read** to the prewarm (entries/adds only), gate/parity timing stamps, a tunable worker count and the hot-path bench (whose p90 limits are already measured). |
| recommendation | **KEEP OURS**; the old prewarm is the same idea one generation earlier - nothing to gain. |
| risk | Low either way; porting would lose the parity warm and the stamps the bench reads. |

### 9. Audit-write / disk-full
| | |
|---|---|
| old location | `atomic_write_json` **L644-672** (the same 8-attempt `PermissionError` retry loop ours still carries, plus per-write `record_core_phase` markers), `append_csv` **L720**, disk refs **L2029-2043** |
| worked in old build? | The atomic write shipped and is still ours. **Disk-full was never handled**: 0 hits for rotation, ENOSPC or "no space" in the old engine - and no test. |
| differences vs ours | Ours removed the three per-write phase markers (cost, run 5), added **rotation** (`_rotate_audit_file`, `AUDIT_ROTATE_BYTES`/`KEEP` for the two files that grew 0.1-0.2 GB/h), append-only tail readers, and the J1 disk-full test + patch. |
| recommendation | **KEEP OURS** - porting the old write path would delete rotation and reinstate unbounded growth. |
| risk | High if ported; the J1 findings show even OURS needed the patch (`DISK_FULL_PATCH_PROPOSAL.diff`). |

## Bottom line for the Boss condition

No porting should start. Where the old build has an equivalent, ours is the same code extended with the guards the runs
demanded; where it does not (rows 3, 5) there is nothing to port; and the two genuinely different rows (4 dust, 2
switch) are different in the direction we fixed. The honest limit: the old build's "it worked" rests on the master
doc's provenance (the backup is the engine that traded) and on the code, because `BUILD_HISTORY_REVIEW.md` and any old
run artifacts are absent from this PC - so a port would trade measured behaviour for unmeasured.

_Model used: deepseek-flash (Hermes session, `deepseek-flash` route). Review only - no code changed, nothing run,
no key file opened, the live engine checkout, ports 8012/8014/8031 and the Wallet Finder untouched._
