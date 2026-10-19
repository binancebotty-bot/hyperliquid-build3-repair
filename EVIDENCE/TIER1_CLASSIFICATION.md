# TIER-1 — what can actually be closed by a card, and what cannot

Measured against `origin/main` @ 76dfaa26 by reading each row's own `execution_proof`.

    Tier-1 rows:                      66
    already PASS:                     16
    not PASS:                         50
      execution_proof needs runtime:  35   <- a card CANNOT close these
      offline-decidable:              7   <- cards can close these
      unclear from the row text:      8

## Why this matters

`t_a83b717e` returned TN-F05, F09, F10, F11 and F12 all NOT_TESTED, and every gap it named was the same one:
the row's proof requires *"a predeclared Phase 6T-style scenario on testnet through the production engine path
only"*. The worker was right — no clone can produce that. It is a property of the row, not a defect in the card.

So the Tier-1 remainder is not one queue. It is two:

| class | rows | who can close it |
|---|---:|---|
| offline-decidable | 7 | a kanban card with a clean clone |
| runtime / testnet | 35 | only the running engine + testnet execution (Codex lane) |

## Runtime-bound rows (cannot be carded)

- `ENG-INV-01` (ENGINE) — One process.
- `ENG-INV-03` (ENGINE) — No new dependency without Architect approval.
- `ENG-INV-04` (ENGINE) — No new authoritative persistent trading-state store.
- `ENG-INV-05` (ENGINE) — No Build 4 control-plane/platform import.
- `ENG-INV-07` (ENGINE) — Leader mutable state is isolated by (wallet, coin).
- `ENG-INV-08` (ENGINE) — Startup/recovery truth includes all relevant perp DEX scopes (default + HIP-3/builder); missing requ
- `ORD-010` (ORDER) — For every copy order the delay from the leader's trade to our send is measured and recorded. An ENTR
- `RISK-013` (RISK) — Testnet and mainnet cannot be confused; dry-run/paper sends nothing; mode change itself creates zero
- `SET-001` (SETTLE) — In-flight remains blocking after API ACK until independent MASTER userFills plus resulting position 
- `SET-002` (SETTLE) — userFillsByTime queried per perp DEX scope with dex param; deterministic dedupe; missing scope fails
- `SET-003` (SETTLE) — Clear requires exchange-derived terminal rejection plus post-attempt MASTER no-fill across all scope
- `SET-004` (SETTLE) — Ownership advances only by confirmed fill; residual authorised delta remains; no duplicate quantity 
- `SET-005` (SETTLE) — Crash between send and oid persistence reconciles from started_ms + intent attributes and stays bloc
- `SET-006` (SETTLE) — MASTER net = unattributed baseline + confirmed engine-owned actual +/- unresolved reserved, within t
- `SET-007` (SETTLE) — All REAL_TESTNET_ENTRY sub-gates: genuine post-start leader OPEN/INCREASE observed, fill identity ve
- `SET-008` (SETTLE) — All REAL_TESTNET_EXIT sub-gates: genuine reduction/close observed, reduction fraction correct, attri
- `SET-009` (SETTLE) — Every follower fill on the exchange reaches the engine ledger; the ledger's net position per coin al
- `TN-F01` (RISK) — Leader capital used for an OPEN/INCREASE is proven fresh at the send boundary (Build 4: exchange clo
- `TN-F02` (RISK) — Projected post-trade liquidation distance is checked against the MAX distance across contributing le
- `TN-F05` (ORDER) — The minimum order notional is enforced at the true execution authority for every OPEN/INCREASE; the 
- `TN-F06` (RISK) — Backstop limits (per-order, per-wallet, total, daily count) block the whole order; they never resize
- `TN-F07` (RISK) — Margin consumed by the follower's other positions is included in the post-trade safety projection.
- `TN-F08` (RISK) — Account value used for safety is resolved from exchange truth; unresolved means refuse the entry.
- `TN-F09` (SETTLE) — HIP-3 / builder-DEX symbols are exact and DEX-scoped everywhere (sizing, orders, ownership, truth, U
- `TN-F10` (SETTLE) — An ambiguous submission (timeout, 429, unknown result) is never retried blind; it is resolved from e
- `TN-F11` (SETTLE) — Ownership attribution never fails open across any crash point; missing ownership truth refuses new e
- `TN-F12` (SETTLE) — Outside-tolerance divergence is surfaced for manual reconciliation and never auto-closed or auto-ado
- `TN-F13` (SETTLE) — Within tolerance follows the normal path; outside tolerance sends nothing; a position difference wit
- `TN-F16` (RISK) — Follower account truth used for an entry decision is fresh at the send boundary; otherwise the entry
- `TN-F18` (SETTLE) — Fills are keyed by exchange identity (Build 4: HL_FILL:<oid>:<tid>:WALLET:<addr>); duplicates, recov
- `TN-F19` (LIFECYCLE) — STARTUP_UNINTENDED_ORDERS = 0 at every boundary (cold start, restart, crash recovery, config reload)
- `TN-F20` (LIFECYCLE) — At most one sender can submit; a stale holder is fenced out.
- `TN-F21` (RISK) — No entry-side safety failure (stale capital, risk truth, budget) can block a REDUCE/CLOSE.
- `TN-F26` (RISK) — Allocation is a sizing basis, not a cumulative budget (Reading A, F26.A-H); safe exact orders are no
- `TN-F27` (RISK) — A leader margin/leverage change is risk authority only, never a trade.

## Offline-decidable rows (card them)

- `ORD-007` (ORDER) — HL_LIVE_AUTO_SEND_MAX_PER_RUN (default 1) and HL_LIVE_AUTO_SEND_WALLET restriction behave as configu
- `RISK-006` (RISK) — gcCloseAdv -> max_close_adverse_diff_pct. Saved value must be enforced by the running engine without
- `RISK-010` (RISK) — max_diff_pct applied as the entry price bound for that wallet.
- `RISK-011` (RISK) — At most 10 service-eligible wallets; 11th is rejected with MAX_WALLETS_EXCEEDED and config unchanged
- `RISK-015` (RISK) — No control closes positions unless explicitly intended; no control bypasses convergence or the singl
- `RISK-016` (RISK) — HL_LIVE_MAX_MANUAL_ORDER_NOTIONAL_USD (default 25) caps manual sends.
- `TN-PS1` (RISK) — Every OPEN/INCREASE needs both exact sizing and a projected post-trade portfolio within every risk/l

## Unclear — the row text does not say which

- `LIFE-002` (LIFECYCLE) — Stop leaves zero unresolved submissions or reports them; no orders sent during stop.
- `LIFE-003` (LIFECYCLE) — Restart recovers from external truth with zero new authority (see ENG-007).
- `LIFE-006` (LIFECYCLE) — Cutover cannot create duplicate send authority or stale replay; old process stopped and proven gone 
- `LIFE-009` (LIFECYCLE) — After a crash the engine recovers only into a non-sending or explicitly safe state; operator action 
- `ORD-001` (ORDER) — Every exchange-client order call is dominated by one disable switch and one sender (TEST-007).
- `ORD-006` (ORDER) — Unresolved reservation persisted in SERVICE_STATE_FILE before exchange.order, oid/status attached af
- `ORD-008` (ORDER) — Orders violating exchange semantics are rejected before the exchange call.
- `ORD-009` (ORDER) — Before any order, the engine confirms via userRole on the follower network that its signing key is t

## The ask

Confirm the split, and confirm that the runtime-bound rows are Codex's lane rather than mine. If they are mine,
they need an engine path and a testnet scenario per row — which is a different kind of work from a card, and I would
want that stated before I keep queueing cards that cannot finish.
