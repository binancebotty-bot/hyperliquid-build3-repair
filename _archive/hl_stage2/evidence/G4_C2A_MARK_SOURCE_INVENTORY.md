# G4-C2A — READ-ONLY MARK SOURCE INVENTORY (Architect F3)

Task: B3-C2H-G4-C2A-MARK-SOURCE-INVENTORY-1 (control-mailbox commit 6a4030463bde53f81e40b42e755f2fa6ae9f5c12)
Scope: read-only trace. NO production code change, no new data source/store, no trading or UI change.

## Question
Does Build3 production have a verifiably CURRENT authoritative mark usable for OPEN / INCREASE / FLIP,
with an age/freshness proof? Do not call leader `fill.price` or `limit_price` a fresh mark without proof.

## Answer
NO, not for the paths that matter. A real fresh-quote source exists and carries an explicit TTL age
proof, but the OPEN/INCREASE/FLIP decision paths use the LEADER FILL PRICE as the mark with no age
check. The TTL proof covers only the cached public quote, which those paths do not consult.

## Trace table
| Concern | Actual field / path | Clock or timestamp | Freshness validation | Failure behaviour |
|---|---|---|---|---|
| Leader event input | `LeaderFill.price`, `timestamp_ms`, `timestamp_iso`, `source`, `recording_method`, `raw` (`HL_Live_Copy_Service.py` L1517) | leader fill time | NONE - it is a fill, not a mark | n/a |
| Public quote source | `get_public_quote(coin, side)` -> `fetch_public_executable_quote()`; cache `self.quote_cache[coin_key] = {"ts_ms": now, "quote": ...}` (L2166) | `utc_now_ms()` | `now - ts_ms <= LIVE_QUOTE_CACHE_TTL_MS` (env `HL_LIVE_QUOTE_CACHE_TTL_MS`, default 1000 ms, L129) | cache miss -> refetch; unusable quote -> quote error / EXECUTABLE_QUOTE_UNAVAILABLE |
| Decision: reducing/exit and `ws` / `live_ws` / `live_ws_snapshot` | `dry_run_intent_audit_decision()`: `executable_price = fill.price`, `suggested_limit_price = fill.price`, `market_data_source = "LEADER_FILL_PRICE"` (L1827-1863) | leader fill time | NONE | leader fill price is used as the mark |
| Decision: `live_poll` | `executable_price_from_fill_payload(fill)` (payload ask/bid), else `quote_getter` -> `hyperliquid_l2book` (L1863-1872) | payload / quote ts | payload quote has none; quote TTL applies only when the getter is used | falls back to the public quote only when payload price <= 0 |
| FIXED sleeve magnitude | 8014 attributed-slice unit SUM persisted in `SERVICE_STATE_FILE`, maintained only in `apply_leader_event`; `sleeve_from_leader_event_position()` (L832) | event time | ledger required | raises `FixedModeAuthorityConflict` without the ledger (hold preserved) |

## Consequences
- The only existing freshness proof in the mark path is the public-quote TTL (default 1000 ms). It is a
  genuine age check, but it is not on the OPEN/INCREASE/FLIP decision path.
- On `ws`/`live_ws`/`live_ws_snapshot` and on reducing/exit, the mark is `fill.price` with no clock or age
  assertion, so "current" cannot be asserted for those paths from the code as written.
- `adverse_diff_pct(fill, executable_price)` compares the leader fill price against the executable price;
  when executable price IS the fill price the adverse measure is structurally 0 and proves nothing.

## Precise blocker for Architect ruling
Decide which of these is the authoritative mark for OPEN/INCREASE/FLIP, and what age bound applies:
1. `fill.price` from the leader event (no age proof), or
2. the payload ask/bid via `executable_price_from_fill_payload` (no age proof), or
3. the cached public executable quote under `LIVE_QUOTE_CACHE_TTL_MS` (has an age proof, not currently
   consulted on those paths).
Until that is ruled, production has no verifiably current authoritative mark for OPEN/INCREASE/FLIP.
No code was changed by this inventory.
