# HARVEST SPEC — the 35 runtime-bound Tier-1 rows

Controller ruling 6271553509 item 2: the runtime-bound rows are **Codex's lane**, harvested from the **live engine's own
append-only files** — not from synthetic scenarios. Testnet funds cannot be topped up, so no extra orders are placed beyond
the engine's own copy flow.

For each group: which audit rows or log fields prove it, and what the pass condition looks like. Grouped by shared evidence
so **one harvest covers several rows**.

Evidence root:

    C:/Users/wigmore/trading_stack/hl-build3-testnet-cert/_archive/hl_stage2/hl_live_copy_audit_testnet/append_only/
      order_intents.csv · send_attempts.csv · live_fills.csv · errors.csv · core_fatal_errors.csv

State (not append-only, but readable): `SERVICE_STATE_FILE`, `live_config.json`, `wallet_gate.json`.

---

## GROUP A — the leader→MASTER chain (8 rows)

**Rows:** `ENG-INV-07`, `ENG-INV-08`, `SET-007`, `SET-008`, `TN-F01`, `TN-F16`, `TN-F27`, `ORD-010`

**Evidence:** `order_intents.csv` (leader event → intent), `send_attempts.csv` (the send), `live_fills.csv` (MASTER fill).
Join key: `intent_id`, with `exchange_order_id` carrying it from send to fill.

**Pass condition, per row:**
- `ENG-INV-07` — one joined event where the sent size equals the planner delta for that (wallet, coin), AND a second
  wallet on the same coin produces a *different* desired net with no contamination between them.
- `ENG-INV-08` — the same join for an event on a non-default perp DEX scope, proving the read covered it.
- `SET-007` — a genuine post-start leader OPEN/INCREASE → follower entry, end to end.
- `SET-008` — a genuine leader reduction/close → follower reduction, reduce-only, end to end.
- `TN-F01` — leader capital value at the send boundary, timestamped within the freshness window.
- `TN-F16` — follower account truth at the send boundary, same freshness test.
- `TN-F27` — a leader margin/leverage change that produced NO order (risk authority only).
- `ORD-010` — measure the delta between leader trade timestamp and our send timestamp for every copy order; report p50/p90/max.

**Blocking risk:** the audit files must span a period where the engine actually sent. If the current window has no sends,
say so — the soak has to produce them, and a harvest on an empty window proves nothing.

---

## GROUP B — in-flight, ownership and reconciliation (11 rows)

**Rows:** `SET-001`, `SET-003`, `SET-004`, `SET-005`, `SET-006`, `SET-009`, `TN-F10`, `TN-F11`, `TN-F12`, `TN-F13`, `TN-F18`

**Evidence:** `SERVICE_STATE_FILE` snapshots (in-flight reservations), `live_fills.csv`, `errors.csv`.

**Pass condition, per row:**
- `SET-001` — an intent whose API ACK arrived but whose MASTER fill had not: it must remain *blocking* (in-flight), not be
  treated as done. Show the reservation still present with the ACK time recorded.
- `SET-003` — a terminal rejection: exchange-derived rejection + a post-attempt MASTER read agreeing. Show the clear.
- `SET-004` — ownership advances only on a confirmed fill; residual authorised delta remains. Show both in one intent.
- `SET-005` — a crash between send and oid persistence: recovery reconciles from `started_ms`. Needs a restart in the
  window — if none occurred, NOT_TESTED with that stated.
- `SET-006` — MASTER net = unattributed baseline + engine-owned actual ± unattributed deltas. Reproduce the arithmetic from
  one snapshot.
- `SET-009` — every follower fill on the exchange appears in the engine ledger; compare `userFills` against
  `live_fills.csv` for a window.
- `TN-F10` — an ambiguous outcome (timeout / 429 / unknown) appears in `errors.csv` and its intent is NOT marked filled.
- `TN-F11` — ownership never fails open across a crash point: any intent without confirmed ownership must be unresolved.
- `TN-F12` — a divergence outside tolerance is surfaced (manual reconciliation marker), not silently absorbed.
- `TN-F13` — a divergence inside tolerance follows the normal path with no flag.
- `TN-F18` — fill identity is `HL_FILL:<oid>:<tid>:<WALLET>`; show the key present and well-formed in `live_fills.csv`.

**Blocking risk:** `SET-005`, `TN-F10`, `TN-F11` need a crash or an ambiguous outcome in the window. If none occurred,
NOT_TESTED — do not manufacture one against the live engine.

---

## GROUP C — perp DEX scope correctness (2 rows)

**Rows:** `SET-002`, `TN-F09`

**Evidence:** the `userFillsByTime` call shape (dex param) recorded in logs/`errors.csv`, plus `live_fills.csv` scope column if
present.

**Pass condition:** every fill query is dex-scoped; no bare-symbol path exists that could resolve to the wrong dex. For
`TN-F09`, show a HIP-3 symbol resolving to its own scope everywhere it is used.

---

## GROUP D — risk gates at send time (8 rows)

**Rows:** `RISK-013`, `TN-F02`, `TN-F05`, `TN-F06`, `TN-F07`, `TN-F08`, `TN-F21`, `TN-F26`

**Evidence:** blocked decisions recorded in `errors.csv` or the intent log with a reason string; `live_config.json` for the
limits in force.

**Pass condition:** for each gate, one recorded BLOCK with its reason, plus the limit value from config that produced it.
`TN-F05` (minimum notional at the true execution authority) needs a below-minimum intent that was blocked **before** the
send, visible as no `send_attempts.csv` row for that intent.

**Blocking risk:** gates only fire when their condition arises. A clean window may simply not contain a block. Where a gate
never fired, NOT_TESTED with `no_block_in_window` — which is an honest and useful result.

---

## GROUP E — genuinely static (3 rows) — NOT runtime after all

**Rows:** `ENG-INV-03`, `ENG-INV-04`, `ENG-INV-05`

I classified these as runtime because their proof text says "static source census ... **plus**", but the invariant itself is
an AST property: no new third-party dependency, no authoritative persistent state store, no Build-4 import. **They belong in
the offline set and a card can decide them** with the row-bound oracle that already exists
(`certification/results/rowbound_oracle.py`). Flagging rather than silently moving them.

---

## GROUP F — single instance and startup (3 rows)

**Rows:** `ENG-INV-01`, `TN-F20`, `TN-F19`

**Evidence:** live process list + lock holder; `order_intents.csv` across a restart boundary.

- `ENG-INV-01` — guard merged at `5dddc8e2`; needs the engine running that commit and a second instance refused with the
  holder named. Card `t_d25048f4` checks which code the live engine runs and stops honestly if pre-guard.
- `TN-F20` — at most one sender; a stale holder is fenced. Show the lease holder and that a stale one cannot submit.
- `TN-F19` — `STARTUP_UNINTENDED_ORDERS = 0` at every boundary: count `order_intents.csv` rows within N seconds of each
  process start with no corresponding leader event. Must be zero.

---

## What Codex needs at the minimum

One soak window in which the engine **itself** produces:
1. at least one leader OPEN and one leader CLOSE (GROUP A/B)
2. at least one startup boundary (GROUP F)
3. `SERVICE_STATE_FILE` snapshots preserved across that window (GROUP B)

Everything else is either static (GROUP E) or contingent on a gate firing (GROUP D), and both can be answered without new
orders.

## Ordering

Per ruling item 4: **Codex gets this only after the new-build latency table is posted.** The restart and latency window come
first. Nothing here asks for an extra order.
