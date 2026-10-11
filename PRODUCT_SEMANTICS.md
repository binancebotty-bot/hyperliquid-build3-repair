# Build 3 — Product Semantics, Non-Goals and Measurable DONE (Gate 1 freeze)

Authority: Architect ruling `B3-A2C-GATE0-PASS-G1-1` (Gate 0 PASS, G1 released), delivered to Hermes as
Controller directive `B3-C2H-G1-1`. This document freezes intent only; it changes no production code.
It is the normative companion to `ARCHITECTURE.md` ("Trading-authority precedence").

## 1. Preserved product behaviour (must survive the repair)
Build 3 is treated as an almost-complete operating product (**preserve unless disproved**).
- Low-latency copy of MAINNET leader activity to the follower, driven by the single existing sender.
- **Proportional mode** (sleeve = leader position × copy scale) proven end-to-end.
- **Fixed mode** proven end-to-end using recovered intended semantics — **never** the old
  fixed-notional-per-fill defect.
- Multi-wallet aggregation; per-`(wallet, coin)` isolation of leader state.
- Multi-DEX / HIP-3 truth (default account state is incomplete); recovery boundaries use snapshot truth.
- Restart / gap recovery that re-establishes truth from external state without local-position replay.
- Settlement verification on the MASTER account (API ack is not settlement).
- Pre-existing unrelated inventory is preserved.
- One process; one physical production `.order()` call site.
- The existing Build 3 **UI, wallet controls, global controls and lifecycle operations**, re-proven
  against engine/exchange truth (no cosmetic "green" may outrank engine truth).

## 2. Trading-authority model (the frozen semantics)
- **B1.** The frozen baseline plus **genuine post-baseline leader events are the ONLY trading authority**;
  desired exposure derives from that event lineage.
- **B2.** **Current leader position / restart / snapshot create ZERO new trade authority** — a snapshot
  must never, by itself, mint a new desired target or new orders.
- **B3.** **Follower exchange state is authoritative for ACTUAL exposure and settlement measurement.**
- **B4.** Snapshots/current positions are for verification, reconciliation and divergence detection; a
  divergence between the event lineage and a snapshot is surfaced for adjudication, not converted into a
  fresh trading decision.

This section removes the previously ruled current-position-derived target/convergence authority conflict.

## 3. Explicit non-goals
- No Build 5.
- No new engine or runtime around Build 3.
- No new authoritative persistent trading-state store.
- No Build 4 control-plane/platform import (Build 4 material is a requirements/evidence source only).
- No second physical order-send path; no bypass of convergence or the single send authority.
- No new runtime dependency without Architect approval.
- No redesign of the (now commissioned) PURE_GIT control transport.
- No LIVE/mainnet activation without explicit Richard approval.
- No uncontrolled scope expansion; >260 new production LOC, >2 production files, or a second process
  is an architectural escalation (`ARCHITECT_REVIEW_REQUIRED`), not an implementation choice.

## 4. Measurable downstream DONE (project completion)
DONE only when, on the exact final candidate and with executed evidence:
1. Build 3 source is tracked from a provenance-verified untouched baseline (DONE, `cea4beb`).
2. Fixed-per-fill sizing is no longer authoritative; target delta → order size unit semantics are proven.
3. Multi-DEX leader/follower snapshot truth is proven.
4. Restart/gap recovery resets from external truth without local-position replay, and mints no new
   desired exposure (B2).
5. Testnet proves repeated leader ADDs converge toward target instead of minting fixed notionals.
6. Testnet settlement is independently confirmed via MASTER userFills and position state.
7. Pre-existing unrelated inventory is preserved; exactly one physical production order site remains.
8. UI/wallet/global/lifecycle controls are exercised and tied to explicit acceptance tests.
9. Controller reviews the exact final commit and executed evidence.
10. Richard explicitly decides LIVE/mainnet.

## 5. Open items this freeze does NOT resolve (carried forward, not silently merged)
- Exact unit-mapping proof (2) and multi-DEX proof (3) are G2/G3 implementation gates.
- Any contradiction found between pinned Build 4 requirement docs is escalated, never silently merged.
- FIXED-MODE HOLD (Architect ruling `B3-A2C-G2-AUTHORITY-RULING-1`): the intended target exposure of a
  `copy_mode="fixed"` wallet is NOT derivable from the config contract. Fixed mode is therefore HELD
  fail-closed (`FIXED_MODE_AUTHORITY_HOLD`, ZERO orders) and the unresolved product requirement is
  carried to **G4** for Build 3 UI/config/product evidence. This is a temporary hold, not a redesign.
- EVENT-LINEAGE PERSISTENCE = `ALLOWED_WITH_RULES_ONLY`: the signed leader-event lineage may persist
  only inside the existing `SERVICE_STATE_FILE`, as a checkpoint durably coupled to the processed-event
  identity. Snapshot / current leader position / follower truth / reconciliation may NEVER seed, top-up,
  rewrite or infer it; missing/corrupt/stale/inconsistent ⇒ fail closed with ZERO order authority until
  deterministic replay reconstructs it.
- ACCOUNT-NET TRUTH: actual-net is ACCOUNT-NET follower exposure. G2 has no live account-net plumbing
  (G3), so where authoritative truth is unavailable the service holds (`ACCOUNT_NET_TRUTH_UNAVAILABLE`);
  wallet-local simulated state is never treated as truth.
