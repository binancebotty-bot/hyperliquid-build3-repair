# CERTIFICATION ENVIRONMENT — authoritative surfaces for Build-3 cert work

**Read this BEFORE writing any card that needs a live surface. Never guess a port.**

This file exists because four UI cards burned a full cycle probing 8000/8014/8767/8765/5000 —
all wrong — and blocked. A worker (or the coordinator) should NOT have to hold project context
in their head to run a cert job. The answer belongs in the repo, in one place, versioned.

## The live surfaces

| surface | URL | status | notes |
|---|---|---|---|
| **UI (certification target)** | `http://127.0.0.1:8031/live-copy` | ✅ **LIVE — HTTP 200** (verified 2026-10-16, listener PID 8668, 2 ESTABLISHED clients) | **This is the surface the UI cert rows run against.** This is the one Claude uses. |

## DO NOT USE

| port | why |
|---|---|
| **:8000** | Never came up. `HL_Copy_App_SSOT.py`'s docstring suggests `uvicorn ... --port 8000`, but the live surface is **8031**. `curl :8000` → WinError 10061 (refused). Do not start a second server there — it is not the cert target. |
| **:8014** | A **separate process, unrelated to the live copy engine** (Wallet Finder UI, listener PID 39660). It serves 0 bytes on `/` and 404 on `/api/status`. Do NOT start it, do NOT kill it, do NOT certify against it. |
| :8767, :8765, :5000 | Timed out. Not cert surfaces. |

## Verification recipe (run this, don't assume)

```bash
# is the target up?
curl -s -m 6 -o /dev/null -w 'http=%{http_code}\n' http://127.0.0.1:8031/live-copy   # expect 200

# who serves it?
netstat -ano | grep -E '127.0.0.1:8031\s.*LISTENING'   # take the trailing PID
```

## Rules that follow from this

1. **A card that needs a live surface must name the exact URL** from this table. "The real UI" is not a spec.
2. **A route that 404s is not "the surface is down".** `/api/status` does not exist on 8031 — record a per-row 404 honestly; do not block the whole card on it.
3. **Never start or stop a surface you were not asked to run.** If the target is genuinely absent, block with the exact probe and let the coordinator establish it.
4. **When a surface moves, update THIS file first**, then the cards. One source of truth.

## Change log

| date | change | evidence |
|---|---|---|
| 2026-10-16 | UI cert surface established as **:8031/live-copy** | operator: "that was the one claude was using"; probe `http=200`, PID 8668, 2 ESTABLISHED |
| 2026-10-16 | :8014 recorded as unrelated (operator) | operator: "the 8014 user interface is a process that is not to do with the live copy engine" |
