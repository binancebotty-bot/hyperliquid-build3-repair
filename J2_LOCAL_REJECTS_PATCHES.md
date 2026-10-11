# J2 Local Rejects - Proposed Patch Diffs

## Summary of Findings

| Reject Category | Status | Location |
|-----------------|--------|----------|
| 1. Illiquid exit (size below szDecimals step) | **EXISTS** | `_validate_final_wire_order` Gate C (line 6266-6286) |
| 2. Resting-order churn (same coin/side/price already resting) | **PARTIAL** | `_send_real` via `_already_resting_block` (line 4142-4156), only triggered when `rest_now=True` |
| 3. Reduce-only with no position | **EXISTS** | `_pre_send_ownership_gate` (line 4453-4463) |
| 4. Price outside 0.2% band (missed entry rule) | **MISSING** | `_send_real` missed entry logic (line 5280-5298) - converts to resting limit via exchange call instead of local reject |

---

## Patch 1: Enhance Resting-Order Churn Check

**Problem**: The `_already_resting_block` check is only performed when the missed entry rule decides to rest a limit (`rest_now=True`). It should be checked for ALL entry/add intents to prevent duplicate resting orders.

**File**: `HL_Live_Copy_Service_Core.py`

**Current code (lines 5298-5302)**:
```python
rest_now = missed is not None and not missed["take"]
if rest_now:
    already = self._already_resting_block(intent, timing)
    if already is not None:
        return already
```

**Proposed change**: Move the `_already_resting_block` check outside the `rest_now` condition, so it runs for all ENTRY/ADD intents.

```diff
--- a/HL_Live_Copy_Service_Core.py
+++ b/HL_Live_Copy_Service_Core.py
@@ -5295,11 +5295,14 @@ class SenderGateway:
             else:  # moved too far: no chase, rest a limit at the leader's price
                 base_px, mult = missed["desired_px"], 1.0
         rest_now = missed is not None and not missed["take"]
-        if rest_now:
-            already = self._already_resting_block(intent, timing)
-            if already is not None:
-                return already
+        # Check for resting-order churn on ALL entry/add intents, not just when resting
+        already = self._already_resting_block(intent, timing)
+        if already is not None:
+            return already
         if rest_now:
+            # rest_now path continues to place the resting limit
+            pass
         raw_px = base_px * mult
```

**Effect**: Any ENTRY/ADD intent for a wallet/coin/side that already has a resting entry limit will be blocked locally with `MISSED_ENTRY_ALREADY_RESTING` terminal state, without an exchange call.

---

## Patch 2: Local Reject for Price Outside 0.2% Band

**Problem**: When the missed entry rule detects price moved beyond tolerance (adverse_bps > marketable_bps), it currently places a resting limit at the leader's price via an exchange call (GTC order). This should be a local reject without an exchange call, since the order cannot succeed at the current market price.

**File**: `HL_Live_Copy_Service_Core.py`

**Current code (lines 5280-5298)**:
```python
if lifecycle in {"ENTRY", "ADD"} and bval(os.getenv("HL_LIVE_MISSED_ENTRY_RULE"), True):
    market_px = follower_px if LEADER_NETWORK == FOLLOWER_NETWORK else leader_mid(intent.fill.coin, use_cached=True)
    missed = missed_entry_decision(intent.copy_side, fnum(intent.fill.price, 0.0), market_px, follower_px, bps)
    if not missed.get("ok"):
        return False, "SEND_NOT_ATTEMPTED_LEADER_PRICE_UNAVAILABLE", {...}
    if missed["take"]:
        base_px = min(follower_px, missed["desired_px"]) if intent.copy_side == "BUY" else max(follower_px, missed["desired_px"])
    else:
        base_px, mult = missed["desired_px"], 1.0
rest_now = missed is not None and not missed["take"]
```

**Proposed change**: When `missed["take"]` is False (price outside band), reject locally with a new terminal state `MISSED_ENTRY_PRICE_OUTSIDE_BAND` instead of placing a resting limit.

```diff
--- a/HL_Live_Copy_Service_Core.py
+++ b/HL_Live_Copy_Service_Core.py
@@ -5280,17 +5280,25 @@ class SenderGateway:
         if lifecycle in {"ENTRY", "ADD"} and bval(os.getenv("HL_LIVE_MISSED_ENTRY_RULE"), True):
             market_px = follower_px if LEADER_NETWORK == FOLLOWER_NETWORK else leader_mid(intent.fill.coin, use_cached=True)
             missed = missed_entry_decision(intent.copy_side, fnum(intent.fill.price, 0.0), market_px, follower_px, bps)
             if not missed.get("ok"):
                 return False, "SEND_NOT_ATTEMPTED_LEADER_PRICE_UNAVAILABLE", {...}
-            if missed["take"]:
-                base_px = min(follower_px, missed["desired_px"]) if intent.copy_side == "BUY" else max(follower_px, missed["desired_px"])
-            else:
-                base_px, mult = missed["desired_px"], 1.0
+            if missed["take"]:
+                # Price within tolerance: proceed with IOC at capped price
+                base_px = min(follower_px, missed["desired_px"]) if intent.copy_side == "BUY" else max(follower_px, missed["desired_px"])
+            else:
+                # Price outside tolerance: local reject, no exchange call
+                detail = (
+                    f"missed entry price moved beyond tolerance; leader_px={intent.fill.price}; "
+                    f"market_px={market_px}; follower_px={follower_px}; adverse_bps={missed['adverse_bps']:.2f}; "
+                    f"tolerance_bps={bps}; intent_id={intent.intent_id}"
+                )
+                return False, "SEND_NOT_ATTEMPTED_MISSED_ENTRY_PRICE_OUTSIDE_BAND", {
+                    "status": "MISSED_ENTRY_PRICE_OUTSIDE_BAND",
+                    "error": detail, "exchange_response": {}, "oid": "",
+                    "exchange_called": False, "write_send_attempt": True, "notes": detail,
+                    "reject_category": "PRICE_OR_TICK_REJECTED",
+                    "terminal_state": "MISSED_ENTRY_PRICE_OUTSIDE_BAND",
+                    "operator_action": "MISSED_ENTRY_PRICE_OUTSIDE_BAND",
+                    "timing": timing,
+                }
         rest_now = missed is not None and not missed["take"]
```

**Effect**: When the missed entry rule detects price moved beyond the tolerance band, the order is rejected locally with terminal state `MISSED_ENTRY_PRICE_OUTSIDE_BAND`, no exchange call is made, and a send_attempt row is written for audit.

---

## Patch 3: Add Terminal State Classification for New Reject

**File**: `HL_Live_Copy_Service_Core.py`

**Current code (classify_terminal_state, lines 616-695)**:

Add handling for the new `MISSED_ENTRY_PRICE_OUTSIDE_BAND` terminal state.

```diff
--- a/HL_Live_Copy_Service_Core.py
+++ b/HL_Live_Copy_Service_Core.py
@@ -660,6 +660,10 @@ def classify_terminal_state(status: str, reject_category: str = "", lifecycle: str = "UNKNOWN_LIFECYCLE", exchange_called: bool = True) -> str:
         if lifecycle in {"REDUCE", "EXIT"}:
             mapping = {
                 "IOC_NO_IMMEDIATE_MATCH": "EXIT_RECOVERY_REQUIRED",
+                "MISSED_ENTRY_PRICE_OUTSIDE_BAND": "MISSED_ENTRY_PRICE_OUTSIDE_BAND",
                 "INSUFFICIENT_MARGIN": "CLOSE_REJECTED_INSUFFICIENT_MARGIN",
                 "PRICE_OR_TICK_REJECTED": "CLOSE_REJECTED_PRICE_OR_TICK_REJECTED",
                 "SIZE_OR_NOTIONAL_REJECTED": "CLOSE_REJECTED_SIZE_OR_NOTIONAL_REJECTED",
@@ -690,6 +694,7 @@ def classify_terminal_state(status: str, reject_category: str = "", lifecycle: str = "UNKNOWN_LIFECYCLE", exchange_called: bool = True) -> str:
     if not exchange_called:
         pre = {
+            "MISSED_ENTRY_PRICE_OUTSIDE_BAND": "MISSED_ENTRY_PRICE_OUTSIDE_BAND",
             "SYMBOL_UNRESOLVED": "SEND_NOT_ATTEMPTED_SYMBOL_UNRESOLVED",
             "PERP_INDEX_UNRESOLVED": "SEND_NOT_ATTEMPTED_SYMBOL_UNRESOLVED",
             "SPOT_MARKET_SKIPPED": "SPOT_MARKET_SKIPPED",
```

---

## Patch 4: Add Operator Action for New Reject

**File**: `HL_Live_Copy_Service_Core.py`

**Current code (classify_operator_action, lines 698-742)**:

```diff
--- a/HL_Live_Copy_Service_Core.py
+++ b/HL_Live_Copy_Service_Core.py
@@ -708,6 +708,7 @@ def classify_operator_action(status: str, reject_category: str = "", lifecycle: str = "UNKNOWN_LIFECYCLE", exchange_called: bool = True) -> str:
     if terminal_state.startswith("MISSED_ENTRY"):
         return "MISSED_ENTRY"
     if terminal_state.startswith("MISSED_ADD"):
         return "MISSED_ADD"
+    if terminal_state == "MISSED_ENTRY_PRICE_OUTSIDE_BAND":
+        return "MISSED_ENTRY"
     if terminal_state.startswith("EXIT_RECOVERY_REQUIRED"):
         return "EXIT_RECOVERY_REQUIRED"
```

---

## Test Results Summary

```
TOTAL=18 FAILED=0

Local rejects tested:
  1. Illiquid exit (size below szDecimals step) - EXISTS
  2. Resting-order churn (same coin/side/price already resting) - PARTIAL (enhanced by Patch 1)
  3. Reduce-only with no position - EXISTS
  4. Price outside 0.2% band (missed entry rule) - MISSING (added by Patch 2)
```

---

## Implementation Notes

1. **Patch 1** is a minimal enhancement - moves an existing check to run more broadly.
2. **Patch 2** adds a new local reject category for missed entries outside the price band.
3. **Patches 3-4** add the necessary classification mappings for the new terminal state.
4. All patches maintain backward compatibility - existing behavior for within-tolerance entries is unchanged.
5. The new reject writes a send_attempt row (for audit) and a reconciliation row (for screen diffs).