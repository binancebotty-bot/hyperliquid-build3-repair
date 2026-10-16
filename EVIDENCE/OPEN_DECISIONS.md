# OPEN DECISIONS — parked list (controller routing, 2026-10-16)

Source: `certification/open_decisions.json` (26 entries; **3 decided/struck**, **23 OPEN**).
Owner + affected records are from that file. **No card can clear an open decision** — these need the owner.
The controller takes the engine-behaviour ones and puts to Boss only those that need him.

Format: `ID | owner | affected records — one-line question`.

| ID | owner | affected | question |
|---|---|---|---|
| OD-02 | Architect | ENG-003, UI-WALLET-006/008 | Fixed-mode intended target exposure — HOLD fail-closed pending G4 product evidence. |
| OD-03 | Controller/Architect (Richard if needed) | CTRL-BIND + all CONTROL records depending on a correct wake | Controller binding identity: three distinct UUID values appear. |
| OD-04 | Controller (escalating if needed) | F-TEST-001, B4-R01, F-PROCESS-002 | Applicability of Build-4 items written for the event-driven, no-target engine. |
| OD-05 | Architect (product), Richard (operator surface) | RISK-012/013, UI-WALLET-014, B4-I12 | Mode model and global safe stop — three overlapping surfaces (per-wallet LIVE/CLO/OFF, legacy ON/OFF/CLOSE_ONLY, …). |
| OD-06 | Architect (scope/LOC), Controller | RISK-001..008 | Global Controls not all enforced (Boss: they must all function; values retunable). |
| OD-07 | Architect/Controller | RISK-009, UI-LCC-ADD | Per-wallet daily loss limit — accepted by UI, not referenced by the Core engine. |
| OD-08 | Architect | NET-001/003/006, ORD-004, UI-LCC-POS, SET-* | Network configuration contract (Boss settled switchability; remaining detail open). |
| OD-09 | Architect | ORD-003, B4-I13, TN-F05 | Minimum order notional — B4 operator min USD 30 + buffer vs Core `HL_LIVE_MIN_NOTIONAL`. |
| OD-10 | Architect | PRICE-003/4/7/8, RISK-005/006/010 | Entry price bound and slippage parameters (partly decided: unset slippage 0.2%). |
| OD-11 | Architect | B4-I26, F-TEST-010, F-VERIFY-008, F-EXC-017 | Runtime independent oracle — required by GUT I26 / FAILURES rows; `independent_oracle.py` was deleted. |
| OD-12 | Architect | LIFE-*, F25-* | Build-3 lifecycle mechanism — proof of launch/start/stop/restart/version/cutover/rollback/config migration. |
| OD-13 | Architect | UI-WALLET-002/015, B4-I18 | Wallet removal with owned exposure — Archive vs admin PURGE semantics. |
| OD-14 | Controller | RISK-011 | 10-wallet cap — Core truncates the leader WS list to `HL_LIVE_WS_MAX_WALLETS` (default 10). |
| OD-15 | MD (#50) / Richard | CTRL-I1..I23 | Which Mission Control INVARIANTS.md is canonical (local I1–I23 vs `origin/control-mailbox`). |
| OD-16 | Controller | ORD-007 | Auto-send scope limits — legacy one-wallet/one-order-per-run vs Core behaviour. |
| OD-17 | Richard | F-PRODUCT-001 | Wallet-selection gating (MTM Calmar ≥ 1.0 etc.) — is it a Build-3 product requirement? |
| OD-18 | Architect | UI-SSOT-* | Two UIs in one app — analytics dashboard vs operator surface. |
| OD-19 | Richard | ENG-012 | Low-latency bound — "low-latency" required but no number stated. |
| OD-20 | Architect / Richard | UI-TRUTH-004, HEALTH-003, INC-11 | At-a-glance system health — which metrics must be visible at a glance. |
| OD-22 | Architect | TN-F01, TN-F03, TN-F26 | Copy-scale denominator — `norm_base / leader_equity_base` (legacy L2022; Core L2416–2419). |
| OD-23 | Architect / Richard | TN-F02/07/08/27, TN-PS1, ENG-VAL-04 | Resulting-portfolio / liquidation safety gate — PS1 projected post-trade check. |
| OD-24 | Architect | TN-F06, TN-F13, TN-F24 | Build-4 numeric thresholds — reconciliation USD 30, 300 s freshness, 10k/50k backstops. |
| OD-25 | Architect / Richard | INC-15, UI-WALLET-005 | Operator close of owned exposure in CLOSE_ONLY — sleeve left open with no zero-target. |

*(A 26th entry triples as decided/struck: OD-01 mark-price authority — decided 2026-10-09 §5. Others struck: see the file's `~~…~~` entries.)*

## Why this matters for certification

Workers probing honestly keep landing on these: **CONTROL** (OD-03), **`F-TEST-010`/`F-VERIFY-008`/`F-EXC-017`**
(OD-11), **`INC-11`** (OD-20). Each is recorded `NOT_TESTED` or `BLOCKED` **with the OD id named** — which is the
correct outcome. **They are not environment failures and cannot be carded away.**

## Change log

| date | change |
|---|---|
| 2026-10-16 | created — 23 open decisions parked at controller request, for routing/Architect decision |
