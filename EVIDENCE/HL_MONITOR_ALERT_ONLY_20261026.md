# hl_monitor.py: alert-only invariant, and the queue move (2026-10-26 01:07-01:08Z)

Deposited so this can be reviewed although the file lives outside the repo
(`C:/Users/wigmore/trading_stack/_tools/hl_monitor.py`).

**What the change does:** the engine-restart branch of `hl_monitor.py` used to queue a runner
action with payload `[{"do":"restart"},{"do":"arm"}]` - i.e. start the engine AND turn sending
on. On 2026-10-26 that payload was found pending as `AUTO-restart-110928` while the engine was
deliberately stopped, so a monitor was able to undo a deliberate stop. It now only alerts.

Files: `hl_monitor.py.bak_20261026T010751Z_alertonly` (before, 29,834 bytes) -> `hl_monitor.py`
(after, 30,686 bytes, mtime 01:08:01Z).

## Unified diff (backup vs current, no secrets)

```diff
--- hl_monitor.py.bak_20261026T010751Z_alertonly	2026-10-26 01:07:51.709562400 +0000
+++ hl_monitor.py	2026-10-26 01:08:01.192378200 +0000
@@ -614,10 +614,18 @@
         if engine_live is None and not engine_stale_for_restart:
             pass
         else:
-            queue_runner_action(
-                config, state, now, "engine_restart", "AUTO-restart",
-                [{"do": "restart"}, {"do": "arm"}], alerts, actions, agent_alerts,
-            )
+            # INVARIANT (controller ruling 2026-10-26): a watchdog may ALERT, never restart or arm.
+            # This block used to queue [restart, arm], i.e. start the engine AND turn sending on.
+            # On 2026-10-26 that payload was found pending as AUTO-restart-110928 while the engine
+            # was deliberately stopped. Alert only; the 15-minute throttle lives in notify_agent.
+            alert = ("engine restart condition detected (engine_live=%s, ws_age=%s); ALERT ONLY - "
+                     "this monitor never restarts or arms the engine" % (engine_live, ws_age))
+            alerts.append(alert)
+            actions.append({"type": "engine_restart", "status": "alert_only", "ts": utc_now()})
+            append_action_log(alert, "engine_restart_alert_only", state, now)
+            add_agent_alert(agent_alerts, "engine_restart_alert_only", alert,
+                            "alert only by invariant; no runner item queued",
+                            "start the engine deliberately if that is what is wanted")
 
     if isinstance(live_config, dict):
         live_wallet_count = count_live_wallets(live_config)
```

## Queue-file move record

The pending action was removed from the runner queue and the file preserved:

- `test_queue.json` - 18160 bytes, sha256 decb0f5969b423d4
```json
[
 {
  "id": "Q1-latest",
  "status": "done",
  "steps": [
   {
    "do": "pull"
   },
   {
    "do": "restart"
   },
   {
    "do": "arm"
   },
   {
    "do": "timing",
    "min": 15
   },
   {
    "do": "memory"
   },
   {
    "do": "liqparity"
   },
   {
    "do": "outage",
    "down_min": 5,
    "settle_min": 10
   },
   {
    "do": "memory"
   }
  ],
  "started": "13:13:24Z",
  "finished": "13:55:48Z"
 },
 {
  "id": "Q2-timing",
  "status": "done",
  "steps": [
   {
    "do": "timing",
    "min": 15
   },
   {
    "do": "memory"
   },
   {
    "do": "liqparity"
   }
  ],
  "started": "13:55:49Z",
  "finished": "14:10:59Z"
 },
 {
  "id": "Q3-outage-timing",
  "status": "done",
  "steps": [
   {
    "do": "pull"
   },
   {
    "do": "restart"
   },
   {
    "do": "arm"
   },
   {
    "do": "outage",
    "down_min": 5,
    "settle_min": 10
   },
   {
    "do": "timing",
    "min": 15
   },
   {
    "do": "memory"
   },
   {
    "do": "liqparity"
   }
  ],
  "started": "15:09:17Z",
  "finished": "15:44:47Z"
 },
 {
  "id": "Q4-outage-detail",
  "status": "done",
  "steps": [
   {
    "do": "pull"
   },
   {
    "do": "restart"
   },
   {
    "do": "arm"
   },
   {
    "do": "outage
```

- `test_queue.json.bak_20261026T010751Z` - 15606 bytes, sha256 237b2b90be6fb949
```json
[
 {
  "id": "Q1-latest",
  "status": "done",
  "steps": [
   {
    "do": "pull"
   },
   {
    "do": "restart"
   },
   {
    "do": "arm"
   },
   {
    "do": "timing",
    "min": 15
   },
   {
    "do": "memory"
   },
   {
    "do": "liqparity"
   },
   {
    "do": "outage",
    "down_min": 5,
    "settle_min": 10
   },
   {
    "do": "memory"
   }
  ],
  "started": "13:13:24Z",
  "finished": "13:55:48Z"
 },
 {
  "id": "Q2-timing",
  "status": "done",
  "steps": [
   {
    "do": "timing",
    "min": 15
   },
   {
    "do": "memory"
   },
   {
    "do": "liqparity"
   }
  ],
  "started": "13:55:49Z",
  "finished": "14:10:59Z"
 },
 {
  "id": "Q3-outage-timing",
  "status": "done",
  "steps": [
   {
    "do": "pull"
   },
   {
    "do": "restart"
   },
   {
    "do": "arm"
   },
   {
    "do": "outage",
    "down_min": 5,
    "settle_min": 10
   },
   {
    "do": "timing",
    "min": 15
   },
   {
    "do": "memory"
   },
   {
    "do": "liqparity"
   }
  ],
  "started": "15:09:17Z",
  "finished": "15:44:47Z"
 },
 {
  "id": "Q4-outage-detail",
  "status": "done",
  "steps": [
   {
    "do": "pull"
   },
   {
    "do": "restart"
   },
   {
    "do": "arm"
   },
   {
    "do": "outage
```

- `test_queue.superseded_20261026T010808Z.json` - 635 bytes, sha256 83a1b2500f6a6cef
```json
{
 "superseded_at": "2026-10-26T01:08:08Z",
 "reason": "watchdog invariant: a monitor may ALERT, never restart or arm (controller ruling 2026-10-26)",
 "ordered_by": "controller (GitHub issue #81, 6405864105)",
 "moved_from": "C:/Users/wigmore/trading_stack/hl-build3-testnet-cert-evidence/run5/test_queue.json",
 "items": [
  {
   "id": "AUTO-restart-110928",
   "steps": [
    {
     "do": "restart"
    },
    {
     "do": "arm"
    }
   ]
  },
  {
   "id": "AUTO-rearm-111528",
   "steps": [
    {
     "do": "arm"
    }
   ]
  }
 ]
}
```

## Notes for the reviewer

1. The added block uses CRLF while the surrounding file uses LF, so the file is now mixed. It
   runs (the monitor has been alive since), but a byte-normalising pass is the tidy fix.
2. This is a monitor, not the engine: it cannot place an order. The defect was that it could
   start one and arm it.
3. The engine SHA under review is unaffected - this file is not in the repo.
