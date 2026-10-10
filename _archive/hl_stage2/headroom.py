"""Exchange headroom monitor (spec: issue #3 "Headroom monitor + escalation events").

Counts what THIS process spends of the per-IP Hyperliquid limits, grades it OK / WARN / CRITICAL, and writes a
structured event file that Telegram (Hermes monitor) and a future AI operator can read. It adds no network calls.
The engine only WRITES suggested actions; nothing here executes them.
"""
from __future__ import annotations

import json
import os
import threading
import time
from collections import deque
from pathlib import Path
from typing import Any, Callable, Deque, Dict, List, Optional, Tuple

INFO_LIMIT_PER_MIN = int(os.getenv("HL_LIVE_INFO_WEIGHT_LIMIT", "1200"))
WS_USER_QUOTA_DEFAULT = int(os.getenv("HL_LIVE_WS_USER_QUOTA", "15"))
WARN_PCT, CRIT_PCT = 70.0, 90.0
HYSTERESIS_SEC = 60.0
LEVELS = ("OK", "WARN", "CRITICAL")
# /info request weights (Hyperliquid docs): cheap reads 2, userRole 60, everything else 20 (+1 per 20 rows for fills)
_W2 = {"allMids", "clearinghouseState", "l2Book", "orderStatus", "spotClearinghouseState", "exchangeStatus", "perpDexs"}
_ACTIONS = {
    "info_weight": ["THROTTLE_POLL", "SHED_LEADER"],
    "ws_users": ["RELEASE_SLOT", "SHED_LEADER"],
    "refusal": ["THROTTLE_POLL", "PAUSE_NEW_ENTRIES"],
}


def info_weight(payload: Any, rows: int = 0) -> int:
    t = str((payload or {}).get("type") if isinstance(payload, dict) else "")
    if t in _W2:
        return 2
    if t == "userRole":
        return 60
    if t in ("userFills", "userFillsByTime", "historicalOrders", "userFunding"):
        return 20 + rows // 20
    return 20


def level_for(pct: float) -> str:
    return "CRITICAL" if pct >= CRIT_PCT else ("WARN" if pct >= WARN_PCT else "OK")


class HeadroomMonitor:
    def __init__(self, alerts_dir: Optional[Path] = None, clock: Callable[[], float] = time.time) -> None:
        self._lock = threading.Lock()
        self._clock = clock
        self._info: Dict[str, Deque[Tuple[float, int]]] = {}   # host -> (time, weight) within the last 60 s
        self._level: Dict[str, str] = {}                        # resource -> current level
        self._below_since: Dict[str, float] = {}                # resource -> time it first read lower than its level
        self._last: Dict[str, Dict[str, Any]] = {}
        self.refusals: List[Dict[str, Any]] = []
        self.alerts_dir = Path(alerts_dir) if alerts_dir else None
        self.ws_provider: Optional[Callable[[], Dict[str, Any]]] = None
        self.run_id = str(int(clock()))

    # ---- counting -------------------------------------------------------------------------------------------
    def note_info(self, host: str, payload: Any, rows: int = 0) -> None:
        now = self._clock()
        with self._lock:
            d = self._info.setdefault(host, deque())
            d.append((now, info_weight(payload, rows)))
            while d and now - d[0][0] > 60.0:
                d.popleft()

    def info_used(self, host: str) -> int:
        now = self._clock()
        with self._lock:
            d = self._info.get(host) or deque()
            while d and now - d[0][0] > 60.0:
                d.popleft()
            return sum(w for _t, w in d)

    def note_refusal(self, resource: str, detail: str) -> None:
        """A hard refusal (429, rate-limit reject, WS user limit): CRITICAL at once, no threshold."""
        with self._lock:
            self.refusals.append({"ts_ms": int(self._clock() * 1000), "resource": resource, "detail": str(detail)[:300]})
            del self.refusals[:-20]
        self._transition("refusal:" + resource, "CRITICAL", 100.0, 1, 1, str(detail)[:300], force=True)

    # ---- grading --------------------------------------------------------------------------------------------
    def _transition(self, key: str, new: str, pct: float, used: float, limit: float, detail: str, force: bool = False) -> None:
        now = self._clock()
        cur = self._level.get(key, "OK")
        if new == cur and not force:
            self._below_since.pop(key, None)
            return
        if LEVELS.index(new) < LEVELS.index(cur) and not force:   # dropping: only after HYSTERESIS_SEC below
            since = self._below_since.setdefault(key, now)
            if now - since < HYSTERESIS_SEC:
                return
        self._below_since.pop(key, None)
        self._level[key] = new
        base = key.split(":")[0]
        ev = {"ts_ms": int(now * 1000), "resource": key, "level": new, "used": used, "limit": limit,
              "pct": round(pct, 1), "detail": detail, "suggested_actions": _ACTIONS.get(base, []) if new != "OK" else [],
              "engine_run_id": self.run_id}
        self._write_event(ev)

    def evaluate(self) -> Dict[str, Any]:
        """Grade every resource now; call it periodically (the poll check) and after any refusal."""
        out: Dict[str, Any] = {}
        with self._lock:
            hosts = list(self._info.keys())
        for host in hosts:
            used = self.info_used(host)
            pct = 100.0 * used / max(1, INFO_LIMIT_PER_MIN)
            key = "info_weight:" + host
            self._transition(key, level_for(pct), pct, used, INFO_LIMIT_PER_MIN, f"{used}/{INFO_LIMIT_PER_MIN} weight in the last 60 s")
            out[key] = {"used": used, "limit": INFO_LIMIT_PER_MIN, "pct": round(pct, 1), "level": self._level.get(key, "OK")}
        if self.ws_provider is not None:
            try:
                w = self.ws_provider() or {}
                acked, wanted = int(w.get("acked", 0)), int(w.get("wanted", 0))
                quota = max(WS_USER_QUOTA_DEFAULT, acked)
                pct = 100.0 * max(acked, wanted if w.get("refused") else acked) / max(1, quota)
                self._transition("ws_users", level_for(pct), pct, acked, quota,
                                 f"{acked} of {quota} feed users acked; {wanted} wanted; {w.get('last_refusal') or 'no refusal'}")
                out["ws_users"] = {"used": acked, "limit": quota, "pct": round(pct, 1), "level": self._level.get("ws_users", "OK"),
                                   "wanted": wanted, "last_refusal": w.get("last_refusal", "")}
            except Exception:
                pass
        out["refusals"] = list(self.refusals[-5:])
        out["worst"] = max((v["level"] for v in out.values() if isinstance(v, dict) and "level" in v), key=LEVELS.index, default="OK")
        if any(k.startswith("refusal:") and v == "CRITICAL" for k, v in self._level.items()):
            out["worst"] = "CRITICAL"
        self._last = out
        self._write_state(out)
        return out

    # ---- output ---------------------------------------------------------------------------------------------
    def _write_event(self, ev: Dict[str, Any]) -> None:
        if self.alerts_dir is None:
            return
        try:
            self.alerts_dir.mkdir(parents=True, exist_ok=True)
            with (self.alerts_dir / "headroom_events.jsonl").open("a", encoding="utf-8") as f:
                f.write(json.dumps(ev, separators=(",", ":")) + "\n")
        except Exception:
            pass

    def _write_state(self, state: Dict[str, Any]) -> None:
        if self.alerts_dir is None:
            return
        try:
            self.alerts_dir.mkdir(parents=True, exist_ok=True)
            p = self.alerts_dir / "headroom_state.json"
            tmp = p.with_suffix(".tmp")
            tmp.write_text(json.dumps({"ts_ms": int(self._clock() * 1000), "levels": dict(self._level), **state}), encoding="utf-8")
            os.replace(tmp, p)
        except Exception:
            pass


class CountingRequests:
    """Stands in for the `requests` module: delegates everything, and counts /info POSTs by host weight."""

    def __init__(self, real: Any, monitor: HeadroomMonitor, info_urls: List[str]) -> None:
        object.__setattr__(self, "_real", real)
        object.__setattr__(self, "_monitor", monitor)
        object.__setattr__(self, "_urls", set(info_urls))

    def __getattr__(self, name: str) -> Any:
        return getattr(self._real, name)

    def post(self, url: str, *a: Any, **k: Any) -> Any:
        resp = self._real.post(url, *a, **k)   # looked up at call time: patches on the real module still apply
        if url in self._urls:
            try:
                host = str(url).split("//", 1)[-1].split("/", 1)[0]
                rows = 0
                try:
                    j = resp.json()
                    rows = len(j) if isinstance(j, list) else 0
                except Exception:
                    pass
                self._monitor.note_info(host, k.get("json"), rows)
                if getattr(resp, "status_code", 200) == 429:
                    self._monitor.note_refusal("info:" + host, "HTTP 429 from /info")
            except Exception:
                pass
        return resp
