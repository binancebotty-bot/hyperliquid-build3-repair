# Architecture Contract — Hyperliquid Build 3 Repair

## Objective
Restore the actual Build 3 Hyperliquid copy engine to correct target-vs-actual convergence while preserving its proven runtime and exchange plumbing.

This is a **repair of Build 3**, not a new engine.

## Known failure
Build 3 copied a fixed follower notional for each qualifying leader entry fill. Repeated leader ADD fills therefore created repeated follower ADDs without account-level desired-vs-actual convergence.

## Chosen repair
Maintain authoritative current leader position by `(wallet, coin)`, derive each follower sleeve from leader position × copy scale, sum sleeves to desired account-net per coin, compare against follower actual/in-flight, and reuse the existing convergence planner and single sender.

## Non-negotiable invariants
1. **One process.**
2. **One physical production `.order()` call site.**
3. **No new dependency without Architect approval.**
4. **No new authoritative persistent trading-state store.**
5. **No Build 4 control-plane/platform import.**
6. **No new engine/runtime around Build 3.**
7. Leader mutable state is isolated by `(wallet, coin)`.
8. Default Hyperliquid account state is not complete for HIP-3/builder DEXes; startup/recovery truth must include all relevant perp DEX scopes.
9. Exchange truth outranks local replay. The old manual follower-position file is not authoritative.
10. API acknowledgement is not settlement. Physical sends require independent MASTER-account fill/position verification.
11. MASTER/trading account and API signer are distinct identities. Balance/fills/positions are verified on MASTER.
12. Convergence orders move actual toward desired; they must not blindly flatten unrelated pre-existing inventory.
13. Restart/recovery establishes current authority from fresh external snapshots, current cohort and current scales.
14. No mainnet/LIVE activation without explicit Richard approval.

## Scope budget
Normal repair budget:
- target: ~200–260 genuinely new production LOC;
- production files: <=2;
- processes: 1;
- new dependencies: 0;
- new authoritative persistent state: 0;
- physical production order sites: 1.

The LOC ceiling is an **architectural tripwire**, not a reason to ship an incomplete repair.

## Automatic Architect escalation
Hermes or Controller MUST stop and raise `ARCHITECT_REVIEW_REQUIRED` before proceeding if any of these becomes true:
- proposed new production LOC >260;
- >2 production files must be changed;
- a second process is proposed;
- a new runtime dependency is proposed;
- a new persistent authority/state database is proposed;
- a second physical order-send path is proposed;
- any invariant above must change;
- the same bounded gate fails twice for materially the same reason;
- new evidence disproves the chosen target/convergence architecture;
- repair begins requiring broad rewrite rather than bounded surgery.

Architect does **not** wake on a timer and does not review ordinary commits.

## Completion definition
The project is complete only when:
1. Build 3 source is tracked from a provenance-verified untouched baseline.
2. Fixed-per-fill sizing is no longer authoritative.
3. Unit semantics from target delta to exchange order size are proven.
4. Multi-DEX leader/follower snapshot truth is proven.
5. Restart/gap recovery resets from external truth without local-position replay.
6. Testnet proves repeated leader ADDs converge toward target rather than repeatedly minting fixed notionals.
7. Testnet settlement is independently confirmed through MASTER userFills and position state.
8. Pre-existing unrelated inventory is preserved.
9. Exactly one physical production order site remains.
10. Controller reviews the exact final commit and executed evidence.
11. Richard explicitly decides whether to authorize LIVE/mainnet.

## Architect's job
Protect these invariants and the project boundary. Do not micromanage implementation, reread history hourly, or invent improvements not required to complete the objective.
