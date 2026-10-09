# Master Product Invariants and Certification Contract

**Product:** Hyperliquid Copy Engine (Build 3 Repair)
**Status:** DRAFT v0.5 (v0.4 added the certified 13 May UI, the missed-entry rule and a route census of the live UI; v0.5 marks which requirements only mainnet can prove). It grants no authority, closes no gate and authorises no code change.
**Companion files:** `certification_matrix.json` (machine-readable, 832 records), `certification_matrix.csv` (same records, spreadsheet form), `open_decisions.json` (§6 in machine-readable form), `gen_matrix.py` (regenerates all three from the source documents). Start at `README.md` in this folder.

## 1. Purpose

This contract lets someone with no project history certify the whole product without making assumptions. It consolidates the requirements already written across three repositories into one list. Each requirement has an ID, a cited source, an applicability decision, an execution proof path, an independent oracle, negative tests and a result field.

It adds no product semantics. Where the sources conflict or a requirement is still unresolved, the item is entered in the Open Decisions register (§6) and left undecided.

Build 3's own contract sets the scope of certification:

> "The engine is not complete merely because the core copy loop works. It is complete only when the full engine + UI + wallet controls + global risk controls + lifecycle/cutover behaviour have passed the applicable invariant/test matrix and the Controller has reviewed the exact evidence." (ARCHITECTURE.md, Full project acceptance scope §7)

This document and its matrix are that "applicable invariant/test matrix".

## 2. Provenance

All sources are copied unchanged into the project's `source-docs/` folder (`/mnt/project-files/source-docs/` in the Claude project). They are not committed to this repository; the Build 4 and Mission Control repositories are private and the local evidence is large. Their SHA-256 hashes are recorded in `certification_matrix.json → source_sha256`.

| Repository | Pinned at | How obtained | Documents |
|---|---|---|---|
| Build 3 Core engine | `HL_Live_Copy_Service_Core.py.bak_pre_convergence_wiring_20260602`, 7,705 lines, SHA-256 `5bda57be3fbf8766c0d19b7380e451e22342bf953ed97e10d3fa43e191b1f848` | Local backup on Boss's PC, copied to project `history/evidence/` (see `history/BUILD_HISTORY_REVIEW.md` §7) | The engine that traded; the certified base (§5) |
| `binancebotty-bot/hyperliquid-build3-repair` | `main` @ `5599415` (CONTROL_STATE refreshed 2026-10-09T09:53Z) | GitHub (public) | ARCHITECTURE.md, PRODUCT_SEMANTICS.md, CONTROL_STATE.json, OPERATING_PROTOCOL.md, BOOTSTRAP.md, README.md, `_archive/hl_stage2/HL_Copy_App_SSOT.py`, `test_g4_ui_controls.py`, `evidence/G4_C2A_MARK_SOURCE_INVENTORY.md` |
| Hyperliquid Build 4 | `e67abeb2` (`origin/build4-final-recovery-20260923`) | Git objects from the local clone at `C:\Users\wigmore\b4_hotfix_clone` (repo not reachable from GitHub in this session) | GUT_CONTRACT.md, FAILURES.md, ACCEPTANCE.md, BUILD4_FINAL_AUTHORITY_MAP.md, OPERATIONS.md, AGENT_START_HERE.md, MISSION.md, NO_SEND_GATE.md, PROOF_MODE_ARCHITECTURE.md |
| `binancebotty-bot/richard-mission-control-template` | INVARIANTS.md, PROJECT_GATES.md, README.md, BOOTSTRAP.md: local working tree (`feature/generic-wake-controller` @ `5de53fa`). COMPANY_CONTROL_PROTOCOL.md: `origin/control-mailbox` @ `f26c4fc`. | Local clone at `C:\Users\wigmore\richard-mission-control-template` | as listed; also `INVARIANTS__origin-control-mailbox-f26c4fc.md` (a different version, see OD-15) |

Build 4 working-tree copies at `C:\Users\wigmore\b4-verify-clean` match `e67abeb2` apart from CRLF line endings. Checked for GUT_CONTRACT, FAILURES, ACCEPTANCE and OPERATIONS. `COMPANY_CONTROL_PROTOCOL.md` is not on `main` in the local Mission Control clone. It exists on `origin/main` (`0df93c7`) and `origin/control-mailbox` (`f26c4fc`). The copy here is the later `f26c4fc` version, which adds a "Control plane v1 assimilation" pointer section.

**Local-trading evidence (v0.2).** `source-docs/local-trading/` holds 405 files copied from `C:\Users\wigmore\trading_stack` (see its INDEX.md). They are evidence, not authority, and rank with Build 4 in §4.1. Used here: Build 4's predeclared Phase 6T testnet protocol (F1–F27 scenario matrix, transport requirements T1–T17 and A1–A8, F26 Reading A, PS1), the frozen milestones and the reviewer (WA) verdicts in `hl-build4-final-closeout/proofs/build4_completion/`; the Build 4 UI control and value audits (`codex_product_closure_20260716_001233`) and F26H UI allocation audit; and Build 3's money-incident trail and 2026-05-11 dashboard field proof in `Hyperliquid scanner/_archive/`. Every record added from them cites the file.

## 3. How to use this contract

### 3.1 Record fields (matrix schema `hl_certification_matrix_v1`)

| Field | Meaning |
|---|---|
| `id` | Stable requirement ID (e.g. `UI-WALLET-004`). Never reused. |
| `area` | ENGINE, PRICING, ORDER, SETTLE, RISK, WALLET, UI, LIFECYCLE, NETWORK, HEALTH, CONTROL, REGRESSION |
| `feature` | What is being certified |
| `expected_behaviour` | The requirement, quoted or closely paraphrased from the source |
| `sources` | Exact document and clause, in the precedence order of §4 |
| `applicability` | `APPLIES`, `APPLIES_PROPOSED`, `ADAPTED_PROPOSED`, `SUPERSEDED` or `OPEN_DECISION` (defined in §4.2) |
| `proof_network` | `TESTNET` (provable on the testnet follower) or `MAINNET` (price quality, slippage, or markets absent on testnet; PASS only from a mainnet-follower run, see §5) |
| `open_decisions` | OD-xx items (§6) that affect the record |
| `execution_proof` | The chain that must be shown end to end, e.g. *UI action → config → running engine → testnet behaviour* |
| `independent_oracle` | Evidence produced without engine code, e.g. *exchange positions, orders and fills* |
| `negative_tests` | Failure conditions the record must also survive |
| `prior_evidence` | Existing tests or rulings. Recorded for information only; they never set `result` |
| `result` | `NOT_TESTED` / `PASS` / `FAIL` / `BLOCKED`. Every record starts at `NOT_TESTED` |
| `evidence_ref`, `tested_commit`, `tested_at_utc` | Filled in when executed: path or SHA of the evidence, the exact engine commit, UTC time |

Boss's worked example appears in the matrix exactly as given:

| Field | Value |
|---|---|
| Invariant ID | UI-WALLET-004 |
| Feature | Disable a leader wallet |
| Expected behaviour | New entries blocked; existing owned exposure remains safely managed |
| Execution proof | UI action → config → running engine → testnet behaviour |
| Independent oracle | Exchange positions, orders and fills |
| Negative tests | Restart, stale configuration, rejected update, API failure |
| Result | NOT_TESTED |

### 3.2 Evidence rules ("everything proven, nothing assumed")

1. **PASS needs executed evidence on the exact commit under test.** Prose, a commit, a sent report or a passing unit test is not a PASS (OPERATING_PROTOCOL Evidence discipline; Mission Control I15). Unit and in-process tests go in `prior_evidence` and never set `result`.
2. **The oracle must be independent.** It reads the exchange (testnet info API for the follower, mainnet info API for leaders) or the OS, and it does not import engine or UI code (FAILURES VERIFY-008).
3. **These claims are never accepted as evidence.** The list is FAILURES "Hard forbidden claims", entered as `F-CLAIM-01..08`: GREEN because unit tests passed, local ledger reconciled, a WS event was seen, an order/fill row exists, a dashboard row is clean, one copied example worked. SAFE because auto_send is disabled, or because recovery handles it.
4. **One example is not health.** A PASS on a trading record needs the account-level invariant to hold over the whole test window, not just one transaction chain (FAILURES LOGIC-014, VERIFY-007).
5. **Proof tests must be non-vacuous.** Each static census (single order site, no new dependency, etc.) must also be shown to FAIL against a deliberately mutated copy (pattern from Build 4 `test_f25_not_vacuous.py`).
6. **A record is BLOCKED, not FAIL, while one of its OPEN_DECISION items is unruled.** Testing it on a guessed ruling is forbidden.
7. **Results are written into the matrix by regenerating it, not by hand-editing a copy.** Store executed results in a separate results file keyed by `id` + `tested_commit`, so the requirement list stays version-controlled and reviewable.

### 3.3 What "certified for mainnet" means

Every record with applicability `APPLIES`, `APPLIES_PROPOSED` (once confirmed) or `ADAPTED_PROPOSED` (once confirmed) shows `PASS` on one certified commit. For `proof_network = MAINNET` records, that PASS comes from a mainnet-follower run on the same commit. No record is `FAIL` or `BLOCKED`. Every OD-xx is ruled, and the Controller has reviewed the exact evidence (DONE-09). Mainnet activation then remains Richard's explicit decision (ARCH inv14, DONE-10). The engine must not need a code change between certification and mainnet, only configuration and credentials (NET-001, NET-005).

## 4. Precedence and applicability

### 4.1 Precedence (highest first)

1. Richard's explicit operator rulings (ARCHITECTURE.md Conflict rule 4).
2. Recorded Architect rulings for this project (`B3-A2C-*`), and PRODUCT_SEMANTICS.md (the Gate 1 freeze).
3. Build 3 ARCHITECTURE.md, CONTROL_STATE.json (current state only) and OPERATING_PROTOCOL.md.
4. Mission Control company invariants, which govern agent control only.
5. Build 4 named documents, as a requirements and evidence source only ("not permission to import its platform/control-plane architecture wholesale", ARCHITECTURE.md). The order within Build 4 is GUT_CONTRACT A0 (its own conflict resolution), then BUILD4_FINAL_AUTHORITY_MAP, ACCEPTANCE, FAILURES and OPERATIONS. Later documents supersede earlier ones **only where they say so explicitly**.

Where precedence is not explicit, the rule is `ARCHITECT_REVIEW_REQUIRED` (ARCHITECTURE.md Conflict rule 3). This contract records those cases as OD-xx and does not pick a side.

### 4.2 Applicability values

| Value | Meaning | Count |
|---|---|---|
| `APPLIES` | Binding: stated in Build 3 documents, or an exact Build 3 equivalent is cited | 576 |
| `APPLIES_PROPOSED` | Inherited from Build 4. No conflict with Build 3 was found, but no document explicitly adopts it. The Controller must confirm. | 171 |
| `ADAPTED_PROPOSED` | The intent applies but the Build 4 mechanism does not (Build 3 forbids importing it). The Controller must confirm the Build 3 equivalent. | 24 |
| `SUPERSEDED` | Explicitly superseded by a cited later document | 23 |
| `OPEN_DECISION` | The requirement itself depends on an unruled decision | 38 |

Boss's note said every inherited requirement needs an explicit applicability decision. The 195 `*_PROPOSED` records are that decision put forward for one bounded Controller review. They are not self-certified.

## 5. Settled decisions (recorded so they are not reopened)

| Decision | Ruling | Source |
|---|---|---|
| Repair Build 3, do not rebuild | `REPAIR_BUILD3`. Preserve unless disproved; any rewrite of working functionality escalates | ARCHITECTURE.md Product-preservation; CONTROL_STATE `architecture_decision` |
| Trading authority | Frozen baseline plus genuine post-baseline leader events are the only trade authority. Snapshot, restart and current position create zero authority. Follower exchange state is the only actual. | PRODUCT_SEMANTICS §2 B1–B4; Architect `B3-A2C-GATE0-PASS-G1-1` |
| Desired-vs-actual convergence | Required for this repair. It supersedes, **for this project**, the Build 4 final authority map's "no desired target, no convergence" engine | ARCHITECTURE.md Chosen repair; Boss's note (2026-10-09) |
| Build 4 platform | Not imported (inv 5). Build 4 is a requirements and evidence source only | ARCHITECTURE.md inv5, Build 4 requirements source set |
| Event-lineage persistence | `ALLOWED_WITH_RULES_ONLY`, inside the existing SERVICE_STATE_FILE only | `B3-A2C-G2-AUTHORITY-RULING-1` |
| G3 exchange truth / in-flight | PASS. DURABLE_IN_FLIGHT_STATE_CLOBBER corrected in `4a41f33` | `B3-C2A-G3-PASS-ARCHITECT-GATE-1` |
| Provenance baseline | PASS at `cea4beb` | CONTROL_STATE `last_controller_ruling` |
| Hermes reporting convention | Routine reports go to the Controller, not Richard | OPERATING_PROTOCOL.md (Richard, Oct 2026) |
| adjudication_log entries | Retained as an INVALIDATED dated record, not authority. The scheduled task that produced them was deleted. | CONTROL_STATE `adjudication_log_disposition` |
| Network switching (owner decision) | Mainnet and testnet must be substitutable at will, per side, so the engine works the same on either network and can run on both in parallel. This settles the requirement in OD-08; the code change and its proof are still outstanding | Boss, project chat 2026-10-09T12:21Z; NET-001, NET-003, NET-006 |
| Certification leaders (owner decision) | Certification copies real, ideally active, MAINNET leader wallets. The only difference from production is that orders go to our TESTNET follower account. No self-controlled testnet leader is used | Boss, project chat 2026-10-09T12:21Z; NET-007 |
| Global Controls must work (owner decision) | The Global Controls that do not govern the engine must be made to function. Their values may be retuned to the risk Boss wants to tolerate. This settles the "wire or present as inactive" choice in OD-06 | Boss, project chat 2026-10-09T12:21Z; RISK-001..008 |
| Engine base (owner decision) | Certification targets the engine that actually traded: the 7,705-line `HL_Live_Copy_Service_Core.py` (surviving copy `.bak_pre_convergence_wiring_20260602`, SHA-256 `5bda57be3fbf8766c0d19b7380e451e22342bf953ed97e10d3fa43e191b1f848`), not the legacy `HL_Live_Copy_Service.py` that G1–G4 were built on. Core enters the repo as its own reviewable step; the network switch and Global Controls work build on it. Resolves OD-26 | Boss, decision card 2026-10-09T12:30Z; `history/BUILD_HISTORY_REVIEW.md` §7 |
| Entry pricing (owner decision) | OPEN/INCREASE/FLIP are priced from a fresh follower-market mid at most 5 s old. With no fresh mid, no order is sent. Resolves OD-01 | Boss, Network switch thread 2026-10-09T13:26Z ("yes fresh price"); implemented in PR #6 |
| Default slippage (owner decision) | Unset marketable slippage defaults to 0.2%. Resolves the slippage part of OD-10 | Boss, Network switch thread 2026-10-09T13:26Z ("0.2"); implemented in PR #6 |
| Certified UI (owner decision) | The UI under certification is the 13 May "Live Copy Command Centre" (`/live-copy`) version of `HL_Copy_App_SSOT.py`: source `_archive\_CLEANUP_QUARANTINE_\tier4_deadcode\…\HL_Copy_App_SSOT.py`, SHA-256 `fad19d220d7af13d48a3eec664c56a32b31624d671b00e2f80ec2dc9062a29b0`, 7,243 lines, restored on branch `claude/restore-live-screen-0513` (`38776e0`, byte-for-byte; `91e9980` had line endings normalised). The previously tracked file (SHA-256 `c0f9e508…`) is the walletproof modelling screen. Resolves OD-21 | Boss, project chat 2026-10-09T15:07Z |
| Missed entries (owner decision) | A missed leader entry is taken if the follower's price is the same, better or within tolerance. Otherwise a diff is reported in the UI and a limit order at the desired price is placed meanwhile (ENG-017). This replaces Build 4 F13's "send nothing outside tolerance" | Boss, project chat 2026-10-09T15:07Z |
| Opposite-direction leaders (owner decision) | When leaders trade opposite ways in one coin, the shared account nets as the exchange does. The engine's ledger follows the exchange's net, per-leader attribution is kept and shown on screen, and opposite entries are not skipped (ENG-018) | Boss, decision card 2026-10-09T15:46Z; testnet run 3 finding F3 |
| What testnet can prove (owner decision) | Most testnet markets are illiquid, so testnet runs prove latency, accounting, wiring and controls only. Slippage and price quality cannot be judged there. The 20 records about price quality, slippage, or XYZ/HIP-3 markets absent on testnet are marked `proof_network = MAINNET`. They reach PASS only from a run whose follower is on mainnet. A testnet run may prove their mechanism, but the status table shows that as NEEDS_MAINNET, never PASS | Boss, project chat 2026-10-09T18:07Z; `RUN_STATUS.md` |
| Diff handling in the UI (owner decision) | The UI must report every diff (UI-DIFF-01) but need not offer a way to fix it; Boss reconciles on the exchange | Boss, project chat 2026-10-09T15:07Z |
| PROCESS-002 "rebuild if foundation unsuitable" | Superseded for this project by the product-preservation presumption | ARCHITECTURE.md |

## 6. Open decisions register

Each item names who rules it under the existing protocol. Matrix records that depend on an item list it in `open_decisions`.

| ID | Decision needed | Evidence | Owner | Records affected |
|---|---|---|---|---|
| OD-01 | ~~Authoritative mark price for OPEN/INCREASE/FLIP and its age bound.~~ **Decided 2026-10-09 (§5): a fresh follower-market mid, at most 5 s old; no fresh mid means no order.** Original question: Options as inventoried: (1) leader `fill.price` (no age proof); (2) payload ask/bid (no age proof); (3) cached public quote under `HL_LIVE_QUOTE_CACHE_TTL_MS` (age proof, not currently consulted on these paths) | CONTROL_STATE `current_blocker`; escalation `B3-C2A-G4-F3-MARK-AUTHORITY-RULING-1` (raised 2026-10-08T22:22Z, **unanswered**); G4_C2A_MARK_SOURCE_INVENTORY.md | Architect | 19 (PRICE-*, B4-I20/I21, UI-LCC-EXQ) |
| **OD-02** | **Fixed-mode intended target exposure.** Fixed mode is HOLD fail-closed (`FIXED_MODE_AUTHORITY_HOLD`, zero orders) pending G4 product evidence. The 8014 slice-semantics ruling `B3-A2C-G4-8014-SLICE-SEMANTICS-RULING-1` exists in the outbox, but CONTROL_STATE still records the hold | PRODUCT_SEMANTICS §5; CONTROL_STATE `fixed_mode_hold` | Architect | ENG-003, UI-WALLET-006, -008 |
| **OD-03** | **Controller binding identity.** Three distinct values appear: `bindings.gpt:reviewer-controller.uuid = 6ac6427b-8df0-83**eb**-beb8-3b6e8796d1e1`; `controller_uuid_dispute.control_state_says = 6ac6427b-8df0-83**ed**-beb8-3b6e8796d1e1` (differs in one character from the line above in the same file); `control_contract_says = 6ac7a51f-d400-83ed-b035-f520ef747394`, the one observed to verify in practice (`B3-H2C-TASK-DROPPED-FAILURE-1`). Hermes deliberately did not choose | CONTROL_STATE `bindings` | Controller/Architect (Richard if needed) | CTRL-BIND and every CONTROL record that depends on a correct wake |
| OD-04 | Applicability of Build 4 items written for the event-driven, no-target engine. Convergence itself is settled (§5); still open are FAILURES TEST-001 (replays historical leader-*position* snapshots, which conflicts with B2 as worded) and the R01 coverage mapping | GUT_CONTRACT A0; BUILD4_FINAL_AUTHORITY_MAP "The engine in one paragraph" | Controller, escalating if needed | F-TEST-001, B4-R01, F-PROCESS-002 |
| OD-05 | **Mode model and global safe stop.** Build 3 has three overlapping surfaces: per-wallet `LIVE/CLO/OFF` in live_config.json; legacy `ON/OFF/CLOSE_ONLY` in wallet_gate.json (`/api/set-wallet-mode`, `/api/set-all-modes`, read by `apply_wallet_gate`); and the process-wide env `HL_LIVE_AUTO_SEND_ENABLED`. Build 4 has a runtime-acknowledged global `OFF/CLOSE_ONLY/LIVE`, and its GUT I12 includes `PAPER`, which its later authority map deletes. Needed: the canonical global safe-stop control and the paper/testnet/live boundary for Build 3 | HL_Copy_App_SSOT.py routes; HL_Live_Copy_Service.py L141, `apply_wallet_gate`; GUT I12; AUTHORITY_MAP Modes | Architect (product), Richard (operator surface) | RISK-012, RISK-013, UI-WALLET-014, B4-I12 |
| OD-06 | **Global Controls not all enforced.** *Boss decided on 2026-10-09 (§5) that they must all function; values may be retuned.* In the Core engine (code-read, unconfirmed by run), five of the eight are read and applied: max per-order notional (L1935, L2441, L3250), max per-wallet exposure (L1931, L2444), symbol allowlist and blocklist (L1944, L2430) and marketable bps (L1939, L3210). Three are not enforced: max total live exposure has an accessor (L1929) with no caller, adverse close diff is only reported in status (L5675), and max per-asset directional exposure is not referenced. (The earlier "seven of eight" finding was read from the legacy file.) Still open: Architect scope approval, values, and proof by execution | Core source census (§8) | Architect (scope/LOC), Controller | RISK-001..008 |
| OD-07 | **Per-wallet daily loss limit.** The UI accepts it, but the Core engine does not reference daily loss anywhere | Core source census | Architect/Controller | RISK-009, UI-LCC-ADD |
| **OD-08** | **Network configuration contract.** *Requirement settled by Boss on 2026-10-09 (§5): each side's network is switchable and mainnet and testnet can run in parallel.* In the Core engine the info, WS and exchange URLs come from env vars `HL_INFO_URL`, `HL_LIVE_WS_URL` and `HL_LIVE_ORDER_ENDPOINT` (L132–134), defaulting to mainnet. A single `HL_INFO_URL` serves both leader and follower reads, so pointing it at testnet would also move leader reads off mainnet. Still open: the per-side split in code and its testnet proof | Core L132–134; PRODUCT_SEMANTICS §1 | Architect | NET-001, NET-003, NET-006, ORD-004, UI-LCC-POS, SET-* (indirectly) |
| OD-09 | **Minimum order notional.** Build 4 I13 sets an operator minimum of USD 30 with an execution buffer of USD 12. The Core engine uses `HL_LIVE_MIN_NOTIONAL` (default 10, L138), overridable by global `min_notional` (L1926), and checks it for ENTRY/ADD only (L2439). Preserve-unless-disproved points to the Core value, but no ruling records it | GUT I13; Core L138, L1926, L2439 | Architect | ORD-003, B4-I13, TN-F05 |
| OD-10 | **Entry price bound and slippage parameters.** *Partly decided 2026-10-09 (§5): unset marketable slippage defaults to 0.2%. Still open (and needed for the missed-entry tolerance in ENG-017): the entry price bound (Build 4 I20's 0% default vs Build 3 `max_diff_pct`) and the close adverse diff value.* Build 4 I20 sets 0% adverse entry movement by default, enforced in the order itself. Build 3 has per-wallet `max_diff_pct` (default 0.1), marketable offset `HL_LIVE_AUTO_SEND_MARKETABLE_BPS` 5, close adverse diff 0.25%, and UI global overrides. Depends on OD-01 | GUT I20/I21; service constants L133, L144 | Architect | PRICE-003/4/7/8, RISK-005/006/010 |
| OD-11 | **Runtime independent oracle.** GUT I26, FAILURES VERIFY-008/TEST-010/EXC-017 require one. The Build 4 final authority map deleted `independent_oracle.py`. Build 3 documents are silent. (An independent oracle is in any case required as a *certification* method by this contract, §3.2) | GUT I26; AUTHORITY_MAP "What was deleted" | Architect | B4-I26, F-TEST-010, F-VERIFY-008, F-EXC-017 |
| OD-12 | **Build 3 lifecycle mechanism.** ARCHITECTURE requires proof of launch, start, stop, restart, version identification, cutover, rollback and config migration. Build 4's mechanism (stable launcher, `current_release.json`, watchdog, cold LIVE lifecycle, F25 identity contract) cannot be imported (inv 5/6), and no Build 3 document in the source set names the canonical start command, lock or version source | ARCH Full scope 5; Build 4 OPERATIONS.md, FAILURES F25 | Architect | LIFE-*, F25-* |
| OD-13 | **Wallet removal with owned exposure.** The UI offers Archive (moves the wallet to `archived_wallets` with mode OFF) and admin PURGE (deletes it from app and engine-loaded files, including `engine_truth.json` and live config). GUT I18 requires an ownership tombstone until the position is legitimately closed. Needed: whether PURGE is refused, or proven safe, while exposure is owned | `purge_wallet_everywhere`; GUT I18 | Architect | UI-WALLET-002, -015, B4-I18 |
| OD-14 | **10-wallet cap.** The Core engine truncates the leader WS subscription list to `HL_LIVE_WS_MAX_WALLETS` (default 10, L145, L4537, L5757), so an 11th wallet would be silently unsubscribed rather than refused. Build 4 deleted its hard-coded count of 10. Needed: whether the cap stays and how an excess wallet is refused visibly | Core; AUTHORITY_MAP "What was deleted" | Controller | RISK-011 |
| OD-15 | **Which Mission Control INVARIANTS.md is canonical.** The local working tree has I1–I23 (the version Boss cited). `origin/control-mailbox` @ `f26c4fc` has a different A1–A17 file plus a COMPANY_CONTROL_PROTOCOL pointer section. The intent largely overlaps but the numbering and some rules differ | both files in source-docs | MD (#50) / Richard | CTRL-I1..I23 |
| OD-16 | **Auto-send scope limits.** The legacy service restricted auto-send to one wallet (`HL_LIVE_AUTO_SEND_WALLET`) and one order per run. The Core engine has neither setting, so this may be moot; confirm there is no other per-run or single-wallet restriction | legacy service L142–143; Core census | Controller | ORD-007 |
| OD-17 | **Wallet-selection gating (FAILURES PRODUCT-001: MTM Calmar ≥ 1.0 etc.).** It is unclear whether this is a Build 3 product requirement | FAILURES PRODUCT-001 | Richard | F-PRODUCT-001 |
| OD-18 | **Two UIs in one app.** The analytics dashboard (top bar Normalisation Base / Mode / Fixed $ / Fee bps / Friction, 9 cards, 23-column table) shows an *app-derived model* of copy performance. The Live Copy Command Centre shows real-account truth. FAILURES UI-001 / PRODUCT-002 require every value to carry its truth tier, so a model value cannot be read as live truth. Needed: how the model view is labelled while Build 3 is preserved | HL_Copy_App_SSOT.py docstring "Performs ALL post-fact modelling"; HTML_TEMPLATE | Architect | UI-SSOT-* |
| OD-19 | **Low-latency bound.** "Low-latency" is required (PRODUCT_SEMANTICS §1) but no number is given. Certification needs a stated leader-event-to-wire bound | — | Richard | ENG-012 |
| OD-20 | **At-a-glance system health.** The project topic requires key wallet metrics, portfolio performance and system health visible at a glance. The Build 3 UI shows WS health and a "DB HEALTH" card, but a source search found no engine heartbeat, last-cycle age or current-blocker indicator in HL_Copy_App_SSOT.py. Needed: which health facts the at-a-glance view must show (a UI addition would be scope, so it goes to the Architect) | source census (§8) | Architect / Richard | UI-TRUTH-004, HEALTH-003, INC-11 |
| OD-21 | ~~Which UI version is the Build 3 UI under certification.~~ **Decided 2026-10-09 (§5): the 13 May Live Copy Command Centre file.** UI records derived from the previously tracked file were re-checked against it: elements still present were re-pointed, absent ones marked SUPERSEDED (the old positions table and modelling-page cards), and evidence from tests run against the old file is void. The 11 May field-proof records (UI-FP) now certify against the 13 May file; a few element ids they name (`lcCoreChip`, `lcWsChip`, `lcStatsBanner`) are not in it, so those fields are found by their data | `HL_Copy_App_SSOT.py` 13 May vs tracked; dashboard_field_proof_20260511 | Boss | — |
| **OD-22** | **Copy-scale denominator.** Build 3 sizes proportional fills from `norm_base / leader_equity_base` (legacy service L2022; Core L2416–2419), where `leader_equity_base` is a per-wallet config value that defaults to 10,000 when unset (legacy L106, L1278; Core L2419, where `norm_base` also falls back to `fixed_notional`, L2418). Build 4 froze a different contract: copy scale = configured follower capital / *fresh* leader capital proven at the trade boundary, refused if unproven (MILESTONE_01/02, Phase 6T F1/F3, F26 Reading A). Needed: whether Build 3 keeps its configured denominator, and whether an unset value may fall back to 10,000 | source; MILESTONE_01, MILESTONE_02; PHASE_6T_C_MATRIX_F01_F09 | Architect | TN-F01, TN-F03, TN-F26 |
| OD-23 | **Resulting-portfolio / liquidation safety gate.** Build 4's operator ruling PS1 (2026-08-22) requires every OPEN/INCREASE to pass a projected post-trade portfolio check (liquidation distance vs the leaders' max, other-position margin, resolved account value, margin-change handling). No Build 3 document has an equivalent; adding it is new semantics | INVARIANT_PS1_PORTFOLIO_SAFETY.md; Phase 6T F2/F7/F8/F27 | Architect / Richard | TN-F02, -F07, -F08, -F27, TN-PS1, ENG-VAL-04 |
| OD-24 | **Build 4 numeric thresholds.** Reconciliation tolerance USD 30 at current mark (MILESTONE_03), 300 s freshness ceiling, backstops 10k per order / 50k per wallet / 100k total / 100 orders per day, and the 1200 WU/min rate-limit partition. Build 3 has its own constants or none. Needed: which values Build 3 certifies against | MILESTONE_03; Phase 6T F1, F6, F13, F24 | Architect | TN-F06, TN-F13, TN-F24 |
| OD-25 | **Operator close of owned exposure in CLOSE_ONLY.** Build 4's final UI audit failed because Close-only persisted but left the sleeve open with no zero-target close command. Build 3 ARCHITECTURE allows emergency stop/close "only where explicitly intended". Needed: whether Build 3 CLOSE_ONLY only mirrors leader reductions, or also offers an operator close | UI_CONTROL_MATRIX.json `stop_blocker`; ARCHITECTURE Full scope | Architect / Richard | INC-15, UI-WALLET-005 |
| OD-26 | ~~Which engine file is certified.~~ **Decided 2026-10-09 (§5): the real Core engine, `HL_Live_Copy_Service_Core.py` (7,705 lines, SHA-256 `5bda57be…f848`).** It is brought into the repo as its own reviewable step. Matrix records citing the legacy `HL_Live_Copy_Service.py` keep that reference as history and say where the Core reference differs | `history/BUILD_HISTORY_REVIEW.md` §7 | Boss | — |

## 7. Requirement areas

Every record is in `certification_matrix.json`. This section maps the areas.

| Area | Records | ID prefixes | What it covers | Main sources |
|---|---|---|---|---|
| ENGINE | 44 | ENG-INV-01..14, ENG-SEM-B1..B4, ENG-001..019, ENG-VAL-01..04, TN-F03/F04/F17 | Build 3's 14 invariants, frozen trading authority, repeated-ADD convergence, proportional/fixed, units, multi-wallet net, multi-DEX, restart at every lifecycle point, unrelated inventory, lineage, in-flight, latency, audit trail, event chaos, flips, Build 4 leftovers on the shared account (ENG-016), missed entries (ENG-017), opposite-direction leaders (ENG-018), loop throughput with 10 busy leaders (ENG-019) | ARCHITECTURE, PRODUCT_SEMANTICS, CONTROL_STATE |
| PRICING | 8 | PRICE-001..008 | Mark authority, quote TTL, entry bound, PRICE_WAIT, exits never trapped, adverse-diff meaningfulness, slippage, close diff | G4_C2A inventory, GUT I20–I22 |
| ORDER | 11 | ORD-001..010, TN-F05 | Single sender, reduce_only, minimums, rounding, exactly-once, pre-send reservation, per-run limits, preflight, signing key valid on the follower network (ORD-009), leader-to-send delay and 30 s stale-entry cutoff (ORD-010) | ARCH, GUT, FAILURES |
| SETTLE | 15 | SET-001..009, TN-F09..F13, TN-F18 | ACK ≠ settlement, MASTER all-DEX fills, terminal reject, partial fill, crash before oid, reconciliation gate, the Build 4 ACCEPTANCE testnet entry and exit gates in full | CONTROL_STATE G3, Build 4 ACCEPTANCE |
| RISK | 26 | RISK-001..016, TN-F01/F02/F06/F07/F08/F16/F21/F26/F27, TN-PS1 | Each of the 8 global-control fields, daily loss, max diff, wallet cap, safe stop, mode boundaries, stale containment, emergency close, manual cap | HL_Copy_App_SSOT.py, ARCH Full scope 4 |
| WALLET | 19 | UI-WALLET-001..019 | Add, remove/archive, enable, **disable (004)**, close-only, copy model, N/F/B fields, status, persistence, invalid input, USER wallet, two mode writers, purge, INC, meta, re-add, subscription coverage | ARCH Full scope 3, GUT I17–I19 |
| UI | 436 | UI-LCC-*, UI-SSOT-*, UI-TRUTH-*, UI-FP-001..197, UI-ROUTE-01..35, UI-DIFF-01, TN-F14/F22/F23, INC-13..17 | **Every** header pill, button, card, graph control, table column, tab, modal field and endpoint in HL_Copy_App_SSOT.py, one record each, plus 5 cross-cutting truth rules | HL_Copy_App_SSOT.py (13 May certified version, §5), ARCH Full scope 2 and 6, FAILURES UI-001..003. UI-ROUTE covers every endpoint of the 13 May file |
| LIFECYCLE | 31 | LIFE-001..009, F25-P01..10, F25-X01..08, TN-F19/F20/F25, INC-18 | Start, stop, restart, status, version, cutover, rollback, migration, crash; the Build 4 F25 deployment-identity proofs and auto-fail conditions (adapted) | ARCH Full scope 5, Build 4 OPERATIONS and F25 |
| NETWORK | 33 | NET-001..007, TN-T1..T17, TN-A1..A8, TN-F24 | Credential-only mainnet switch, signer vs MASTER, per-side network selection, parallel mainnet/testnet instances, real mainnet leaders for certification, LIVE activation gate, same-SHA promotion | ARCH inv11/14, ACCEPTANCE promotion gates |
| HEALTH | 7 | HEALTH-001..005, TN-F15, INC-11 | WS health, truth freshness, current blocker, local failure isolation, diagnostics never blocking | GUT I10/I16, FAILURES EXC-001/009/019 |
| CONTROL | 54 | CTRL-I1..I23, CTRL-GATE0/BIND/HWM/EVID/ESC, DONE-01..10, TN-CAMP-01..09, HARN-01..07 | The agent control system, Gate 0, binding identity, high-water discipline, evidence and escalation rules, measurable DONE | Mission Control INVARIANTS/PROJECT_GATES, OPERATING_PROTOCOL, PRODUCT_SEMANTICS §4 |
| REGRESSION | 148 | B4-I01..I26, B4-R01..R25, F-*, F-CLAIM-*, INC-01..10, INC-12 | Build 4 frozen invariants with per-item applicability, the R01–R25 catalogue, every FAILURES.md taxonomy entry (ARCH, LOGIC, EXC, UI, VERIFY, PROCESS, PRODUCT, TEST), GREEN-ONLY-001, forbidden claims | GUT_CONTRACT, FAILURES |

### 7.0 What the local-trading evidence added (v0.2)

| Group | Records | What it adds | Source |
|---|---|---|---|
| TN-F01..F27, TN-PS1 | 28 | Build 4's 27 predeclared testnet failure scenarios and the portfolio-safety invariant, each with Build 3 applicability. Five liquidation/allocation scenarios and the sizing denominator are OPEN (OD-22, OD-23) | PHASE_6T_C_MATRIX_F01..F27, INVARIANT_PS1 |
| TN-CAMP-01..09 | 9 | How the testnet campaign itself is run: bounds frozen before the first order, flat start, allowlist, ambiguity stop, cleanup scope, abort conditions, environment identity, per-class exchange parity, testnet coverage gaps (no XYZ markets on testnet) | PHASE_6T_C_COMPREHENSIVE_TESTNET_PROTOCOL |
| TN-T1..T17, TN-A1..A8 | 25 | Testnet transport isolation and hostile-origin cases. They reinforce OD-08 | PHASE_6T_C_TRANSPORT_REQUIREMENTS |
| HARN-01..07 | 7 | Rules for the certification harness: no direct `exchange.order` in proof scripts, census covers proofs, one engine for both networks, no secret leaks, no overclaims, false-control census, no shared worktree | WA_ONE_ENGINE_VERDICT_a8d0641, TESTNET_MAINNET_ENGINE_PARITY, false_control_audit.json, worker_conflict_20260930.json |
| ENG-VAL-01..04 | 4 | Input validation failures reviewers found: fabricated defaults, NaN, malformed tiers skipped, approximated maintenance margin | WA_VERDICT_04/05J, WA_REMEDIATION_04 |
| INC-01..18 | 18 | Build 3 money incidents and Build 4 UI findings as regressions: hidden large position, shared-symbol exposure, ledger rows the exchange does not support, duplicate fills, HIP-3 namespace and price source, unknown meta, unproven sends, engine death shown as healthy, dust, ungated targets displayed, false budget, close-only visibility, metric source, fee basis, operator launcher | `_archive/hl_stage2/hl_live_copy_audit/*`, LIVE_MONEY_REVIEW_FINDINGS, HYPERLIQUID_FAILURE_ANALYSIS, F26H_UI_ALLOCATION_AUDIT, UI_CONTROL_MATRIX, FINDING_P1 |
| UI-FP-001..197 | 197 | Build 3's 2026-05-11 field-by-field dashboard proof (source key, formula, provenance, send impact). Prior verdict is carried in `prior_evidence`: 189 PASS, 7 FAIL, 1 NOT_PROVEN. The UI version it tested is OD-21 | dashboard_field_proof_20260511_124846.csv |

Already covered before v0.2 and not duplicated: the F25 identity proofs, ACCEPTANCE testnet gates, the one-order-site rule, ACK ≠ settlement, B1–B4 authority.

### 7.1 Build 4 frozen invariants: proposed applicability

| ID | Proposed | Note |
|---|---|---|
| I02, I07, I23, I24, I25 | APPLIES | Exact Build 3 equivalents cited (B2/inv13, G3 semantics, inv12) |
| I01, I03–I06, I10, I11, I14–I19, I22 | APPLIES_PROPOSED | No conflict found |
| I08 | APPLIES_PROPOSED | Met by one process plus one order site; the Build 4 lease is not imported |
| I09 | ADAPTED_PROPOSED | Build 3 equivalent: SERVICE_STATE_FILE as the sole durable store |
| I12 | OPEN (OD-05) | PAPER/mode model conflict |
| I13 | OPEN (OD-09) | Minimum notional conflict |
| I20, I21 | OPEN (OD-10) | Mark source ruled (OD-01); the entry bound is still open |
| I26 | OPEN (OD-11) | Runtime oracle deleted in Build 4 final |

## 8. Source-derived findings for the certification plan

These come from reading the Core engine, `HL_Live_Copy_Service_Core.py` (7,705-line copy, SHA-256 `5bda57be…f848`), plus the UI at Build 3 `main` @ `5599415`. They are **inferences, not test results**. Each must be confirmed or refuted by execution, which is why each one maps to matrix records rather than to a verdict. None was acted on. Findings first written against the legacy `HL_Live_Copy_Service.py` were re-checked against Core; where they differ, Core wins.

**Status at `main` @ `114e8b4`:** PRs #4, #6 and #7 have since changed the code behind findings 1–6: one order call site (L2716), separate leader and follower networks (L97–146), all Global Controls read including a global `max_daily_loss_usd`, and the 10,000 leader-equity fallback removed (L2620). None of this is proven by a run yet; the findings below describe the 2 Jun backup and stay as the regression list.

1. **Three of eight Global Controls are not enforced (OD-06).** Max total exposure (accessor, no caller), adverse close diff (status only) and per-asset directional exposure (absent). The other five reach decisions.
2. **Four order call sites, not one.** Core calls `exchange.order()` at L2726, L2843 (recovery), L3350 and L3379 (retry), behind one gate at L4036. ARCHITECTURE requires one physical order site (ORD-001).
3. **One info URL for both leader and follower (OD-08).** All endpoints are env-configurable, but there is no per-side network split, so a testnet follower would also read leaders from testnet.
4. **Daily loss limit is not implemented (OD-07).**
5. **Copy scale falls back to a 10,000 leader equity (OD-22).** An unset `leader_equity_base` becomes 10,000 (L2419), and `norm_base` falls back to `fixed_notional` (L2418). Build 4's reviewers failed exactly this pattern, so ENG-VAL-01 tests it whatever OD-22 decides.
6. **Wallets beyond 10 are silently dropped from the leader stream (OD-14).** L4537 truncates the subscription list.
7. **The fixed-notional-per-fill defect lives at `fixed_notional()` L1922 (ENG-003, OD-02).**
8. **Two wallet-mode writers (OD-05).** `wallet_gate.json` is reloaded each cycle (L6049) alongside `live_config.json`; CLOSE_ONLY maps to CLO, which blocks ENTRY/ADD (L2428).
9. **The "Live Exposure" card shows `manual_live_exposure_estimate`**, a sum over the manual ledger, not MASTER exchange exposure (UI-LCC-CARD-05). UI finding, unchanged.
10. **Controller UUID recorded inconsistently inside CONTROL_STATE.json itself** (`83eb` vs `83ed`) as well as against CONTROL_CONTRACT (OD-03).
11. **No engine heartbeat or current-blocker indicator in the UI (OD-20).** The 2026-05-17 death-attribution snapshot shows this mattered: the core process was gone while the app's status fields read OK (INC-11).
12. **The audited Build 3 UI is not the tracked file (OD-21).** The May 2026 field proof and Playwright run reference elements absent from the tracked `HL_Copy_App_SSOT.py`.
13. **Build 3's earlier fix for oversizing was a clamp.** Phase 3B added a post-sizing clamp to stop a USD 19M desired target on a USD 10k follower. Build 4 F6 later ruled clamps unsafe (block whole). TN-F06 and INC-13 cover both the behaviour and the display.
14. **Two scenario classes cannot be fully proven on testnet.** Testnet had no XYZ HIP-3 markets, so namespace scenarios (TN-F09, INC-07/08) need a mainnet read-only verification step (TN-CAMP-09).

## 9. Maintenance

* This folder lives at `certification/` in the Build 3 repository (Boss approved the commit on 2026-10-09).
* `gen_matrix.py` rebuilds the JSON and CSV from the source-docs folder: `HL_CERT_SOURCE_DOCS=<path to source-docs> python3 certification/gen_matrix.py`. If a source document changes, re-copy it at the new pinned commit, re-run, and review the diff. Requirement IDs are stable; withdrawn requirements are marked SUPERSEDED, never deleted.
* When an OD-xx is ruled, record the ruling message ID in §6, update the affected records' `applicability`, and regenerate.
