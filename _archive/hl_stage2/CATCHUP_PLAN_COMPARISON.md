# E2 comparison: net catch-up plan vs the engine's current merge (HL_Live_Copy_Service_Core.py)

Engine today (per worker batch): `_plan_batch` drops already-handled fills, groups by (wallet, coin), merges only
CONSECUTIVE runs where `mergeable_fills` is true (same side AND same raw "dir") and the run stays inside the
per-order notional room, then sends EXIT-lifecycle groups first. Prices are the size-weighted average of the run
(`merge_leader_fills`); the merged fill takes the LAST fill's timestamp and the FIRST fill's id. Late entries whose
leader went flat in the same window are skipped by a SEPARATE pass, `already_closed_late_entries` (needs
startPosition on every fill of that wallet/coin and a >60 s age; a reducing/flipping fill is never skipped).

Net plan (`catchup_plan.plan_catchup`, pure, one coin/window):
 1. Order count: the net plan emits ONE order per (wallet, coin) window (signed net delta). The engine emits one
    per direction-RUN, so open(BUY) then reduce(SELL) is 2 engine orders but 1 net order (size = the difference).
 2. Skip rule: the net plan skips late entries when the leader returns to flat INSIDE the batch, using the batch's
    own timeline; the engine uses a 60 s age vs wall clock and needs startPosition on every fill. Same intent,
    different trigger; the net plan also skips the closing fill when the engine held nothing (engine: nothing to do).
 3. Flip: the net plan emits CLOSE(held_before) then ENTRY(remainder) from the computed net. The engine emits the
    exit run and the entry run as two orders too, but driven by "dir"/ledger classify, not by a computed close of
    the engine's sleeve size.
 4. Price: engine = size-weighted average; net plan carries OLDEST entry price and NEWEST price and prices the
    order at the newest. Different fill price for the same window.
 5. Cap: engine caps a merged run at max_order_notional (room per run). The net plan has NO cap check, so a big
    window can produce a net order larger than the per-order cap - it must be re-checked before wiring.
 6. Idempotency: engine drops already-handled fills first; the net plan has no dedupe layer.
 7. Fallback: with an unknown startPosition the engine still merges by dir; the net plan stops netting and emits a
    FILL step per fill (no skipping, no netting).
Not in the prototype: multi-coin worker batching, priority lanes, queue/backpressure, ownership gate, order-cap
room, size rounding, and the audit trail - all still the engine's job if this is ever wired in.
