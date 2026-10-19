# TIER-1 PROPOSAL — blocking certification set (57 rows)

Controller ruling 6270025570 item 2: *"Tier 1 is ENG-INV-01..08 plus the safety-critical rows Hermes
proposes, at most about 60. Tier 2 is the rest, tracked and not blocking the soak. The gate reports the
tiers separately."*

**Status: PROPOSAL — awaiting approval. No register change made by this document.**

## Proposed composition

| group | rows | why it is blocking |
|---|---:|---|
| `ENG-INV-01..08` | 8 | the eight certification invariants |
| `RISK` | 26 | order sizing, caps, leverage, liquidation parity — the paths that decide how much is sent |
| `ORDER` | 9 | order construction, side/size/price correctness |
| `SETTLE` | 14 | settlement, reconciliation and position truth |
| **total** | **57** | inside the ~60 ceiling |

## Current state of those 57 rows

```
  PASS         28
  NOT_TESTED   18
  FAIL         9
  BLOCKED      2
```

So the blocking tier is **29 rows from complete** (29 not PASS).

## The 29 rows that are not PASS

**FAIL — 9**

- `ORD-001` (ORDER) — Every exchange-client order call is dominated by one disable switch and one sender (TEST-007).
- `ORD-002` (ORDER) — Reductions are reduce_only, capped by actual account-net, cannot flip.
- `ORD-006` (ORDER) — Unresolved reservation persisted in SERVICE_STATE_FILE before exchange.order, oid/status attached after respon
- `ORD-008` (ORDER) — Orders violating exchange semantics are rejected before the exchange call.
- `TN-F05` (ORDER) — The minimum order notional is enforced at the true execution authority for every OPEN/INCREASE; the execution 
- `TN-F09` (SETTLE) — HIP-3 / builder-DEX symbols are exact and DEX-scoped everywhere (sizing, orders, ownership, truth, UI); no bar
- `TN-F10` (SETTLE) — An ambiguous submission (timeout, 429, unknown result) is never retried blind; it is resolved from exchange tr
- `TN-F11` (SETTLE) — Ownership attribution never fails open across any crash point; missing ownership truth refuses new exposure.
- `TN-F12` (SETTLE) — Outside-tolerance divergence is surfaced for manual reconciliation and never auto-closed or auto-adopted.

**BLOCKED — 2**

- `ENG-INV-07` (ENGINE) — Leader mutable state is isolated by (wallet, coin).
- `ENG-INV-08` (ENGINE) — Startup/recovery truth includes all relevant perp DEX scopes (default + HIP-3/builder); missing required scope

**NOT_TESTED — 18**

- `ENG-INV-01` (ENGINE) — One process.
- `ORD-003` (ORDER) — Orders below the exchange/configured minimum are not sent and do not create target authority or silent residue
- `ORD-004` (ORDER) — Size quantised to asset szDecimals from the SAME network's meta; zero after rounding -> no order.
- `ORD-005` (ORDER) — One canonical logical event identity and one deterministic execution identity; ambiguous submission stays UNRE
- `ORD-007` (ORDER) — HL_LIVE_AUTO_SEND_MAX_PER_RUN (default 1) and HL_LIVE_AUTO_SEND_WALLET restriction behave as configured and ar
- `RISK-009` (RISK) — daily_loss_limit stops new entries for that wallet when breached, or is labelled display-only. Source census: 
- `RISK-010` (RISK) — max_diff_pct applied as the entry price bound for that wallet.
- `RISK-011` (RISK) — At most 10 service-eligible wallets; 11th is rejected with MAX_WALLETS_EXCEEDED and config unchanged.
- `RISK-012` (RISK) — One operator action stops all new sends account-wide and is acknowledged by the running engine; it creates zer
- `RISK-013` (RISK) — Testnet and mainnet cannot be confused; dry-run/paper sends nothing; mode change itself creates zero orders.
- `TN-F01` (RISK) — Leader capital used for an OPEN/INCREASE is proven fresh at the send boundary (Build 4: exchange clock, 300 s 
- `TN-F02` (RISK) — Projected post-trade liquidation distance is checked against the MAX distance across contributing leaders, nev
- `TN-F07` (RISK) — Margin consumed by the follower's other positions is included in the post-trade safety projection.
- `TN-F08` (RISK) — Account value used for safety is resolved from exchange truth; unresolved means refuse the entry.
- `TN-F13` (SETTLE) — Within tolerance follows the normal path; outside tolerance sends nothing; a position difference without genui
- `TN-F26` (RISK) — Allocation is a sizing basis, not a cumulative budget (Reading A, F26.A-H); safe exact orders are not rejected
- `TN-F27` (RISK) — A leader margin/leverage change is risk authority only, never a trade.
- `TN-PS1` (RISK) — Every OPEN/INCREASE needs both exact sizing and a projected post-trade portfolio within every risk/liquidation

## What this excludes, and why that is safe

Tier 2 = 733 rows: UI 400, REGRESSION 148, CONTROL 54, ENGINE 33, NETWORK 33, LIFECYCLE 31, WALLET 19, PRICING 8, HEALTH 7.

`UI` (400 rows) is the bulk of Tier 2 and is render-only on `:8023`; state-changing UI rows move to `:8031`
per ruling item 5, after the UI-save fix merges and the controller restarts it. `REGRESSION` (148) and
`CONTROL` (54) stay tracked and non-blocking.

## Decisions needed

1. **Approve or amend this 57-row set.** In particular: should `ENG-INV-09..14` (6 rows, all NOT_TESTED) stay
   Tier 2, and is any `LIFECYCLE` or `WALLET` row safety-critical enough to displace a `SETTLE` row?
2. **Confirm the gate reads tiers separately.** Today `completion_gate.load_requirements` loads all 790 records
   and reports them as one set, so a Tier-1/Tier-2 split needs a register field the gate honours — otherwise
   the guard keeps reporting all 790 every turn regardless of the ruling.

That second point matters mechanically: without a tier marker the ruling changes intent but not the gate's
behaviour. I can propose the field (`tier: 1|2` on each record, with the gate filtering to tier 1 for the
completion verdict) — but changing the gate is outside my repo, same as the dispatcher defects.
