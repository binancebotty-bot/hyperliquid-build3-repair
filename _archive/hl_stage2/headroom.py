"""Exchange headroom monitor (spec: issue #3 "Headroom monitor + escalation events").

Counts what THIS process spends of the per-IP Hyperliquid limits, grades it OK / WARN / CRITICAL, and writes a
structured event file that Telegram (Hermes monitor) and a future AI operator can read. It adds no network calls.
The engine only WRITES suggested actions; nothing here executes them.
"""
from __future__ import annotations

import json
import os
import socket
import struct
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
    "ws_foreign": ["ASK_BOSS_STOP_OR_CAP_OTHER_WS_CLIENT", "SHED_LEADER"],
}
FOREIGN_SCAN_SEC = float(os.getenv("HL_LIVE_FOREIGN_WS_SCAN_SEC", "30"))


def _established_tcp():
    """(pid, remote_ip, remote_port) for ESTABLISHED IPv4 TCP sockets. Stdlib only, no subprocess."""
    if os.name == "nt":
        import ctypes
        import ctypes.wintypes as w
        AF_INET, OWNER_PID, ESTAB = 2, 4, 5
        size = w.DWORD(0)
        get = ctypes.windll.iphlpapi.GetExtendedTcpTable
        get(None, ctypes.byref(size), False, AF_INET, OWNER_PID, 0)
        buf = ctypes.create_string_buffer(size.value)
        if get(buf, ctypes.byref(size), False, AF_INET, OWNER_PID, 0) != 0:
            raise OSError("GetExtendedTcpTable")
        rows = ctypes.cast(buf, ctypes.POINTER(w.DWORD))[0]
        base = ctypes.addressof(buf) + ctypes.sizeof(w.DWORD)
        step = ctypes.sizeof(w.DWORD) * 6
        for i in range(rows):
            st, _la, _lp, ra, rp, pid = (w.DWORD * 6).from_address(base + i * step)
            if st == ESTAB and pid:
                yield pid, socket.inet_ntoa(struct.pack("<L", ra)), socket.ntohs(rp & 0xFFFF)
        return
    # Linux: /proc/net/tcp carries the socket inode but no pid; resolve it through /proc/<pid>/fd.
    want = {}
    with open("/proc/net/tcp", encoding="ascii", errors="replace") as fh:
        for line in fh.readlines()[1:]:
            f = line.split()
            if len(f) < 10 or f[3] != "01":
                continue
            ip_h, port_h = f[2].split(":")
            want[int(f[9])] = (socket.inet_ntoa(struct.pack("<L", int(ip_h, 16))), int(port_h, 16))
    for d in Path("/proc").iterdir():
        if not d.name.isdigit():
            continue
        try:
            for fd in (d / "fd").iterdir():
                t = os.readlink(fd)
                if t.startswith("socket:[") and int(t[8:-1]) in want:
                    ip, port = want[int(t[8:-1])]
                    yield int(d.name), ip, port
        except OSError:
            continue


def _proc_name(pid: int) -> str:
    """Process image name, stdlib only: QueryFullProcessImageNameW on Windows, /proc/<pid>/comm on Linux."""
    if os.name == "nt":
        import ctypes
        import ctypes.wintypes as w
        h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return ""
        try:
            buf, n = ctypes.create_unicode_buffer(260), w.DWORD(260)
            if ctypes.windll.kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n)):
                return os.path.basename(buf.value)
            return ""
        finally:
            ctypes.windll.kernel32.CloseHandle(h)
    try:
        return Path("/proc/%d/comm" % pid).read_text(encoding="ascii").strip()
    except OSError:
        return ""


def scan_foreign_ws(ws_url: str, own_pid: Optional[int] = None) -> Dict[str, Any]:
    """Other local processes holding an established connection to the Hyperliquid WebSocket host (they share this IP's
    user/connection quota). Read-only: asks the OS for its connection table; touches no other process. {"ok": False}
    when the table cannot be read."""
    own_pid = own_pid or os.getpid()
    host = str(ws_url).split("//", 1)[-1].split("/", 1)[0].split(":")[0]
    try:
        ips = {ai[4][0] for ai in socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)}
    except Exception as exc:
        return {"ok": False, "error": "resolve:" + repr(exc)[:120], "foreign": 0, "pids": {}}
    pids: Dict[int, Dict[str, Any]] = {}
    try:
        for pid, remote_ip, remote_port in _established_tcp():
            if remote_port == 443 and remote_ip in ips and pid != own_pid:
                d = pids.setdefault(int(pid), {"connections": 0, "name": _proc_name(int(pid))})
                d["connections"] += 1
    except Exception as exc:
        return {"ok": False, "error": repr(exc)[:160], "foreign": 0, "pids": {}}
    return {"ok": True, "foreign": sum(v["connections"] for v in pids.values()),
            "pids": {str(k): v for k, v in pids.items()}}


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
        self.foreign_ws_scanner: Optional[Callable[[], Dict[str, Any]]] = None   # set by the engine; None = no scan
        self._foreign: Dict[str, Any] = {}
        self._foreign_at = 0.0
        self._foreign_busy = False
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
        if self.foreign_ws_scanner is not None:
            self._refresh_foreign()
            f = dict(self._foreign)
            if f.get("ok"):
                n = int(f.get("foreign", 0))
                try:
                    refused = bool((self.ws_provider() or {}).get("refused")) if self.ws_provider else False
                except Exception:
                    refused = False
                lvl = "CRITICAL" if (n and refused) else ("WARN" if n else "OK")
                who = ", ".join("pid %s %s (%d conn)" % (k, v.get("name") or "?", v.get("connections", 0))
                                for k, v in sorted((f.get("pids") or {}).items()))
                self._transition("ws_foreign", lvl, 100.0 if lvl == "CRITICAL" else (70.0 if n else 0.0), n, 0,
                                 "other local processes hold %d HTTPS/WebSocket connection(s) to the feed host (not all are feed users): %s%s" % (n, who or "none",
                                 "; our subscriptions were refused" if (n and refused) else ""))
                out["ws_foreign"] = {"used": n, "limit": 0, "pct": 0.0, "level": self._level.get("ws_foreign", "OK"), "pids": f.get("pids", {})}
            else:
                out["ws_foreign_scan"] = {"ok": False, "error": f.get("error", "not scanned yet")}
        out["refusals"] = list(self.refusals[-5:])
        out["worst"] = max((v["level"] for v in out.values() if isinstance(v, dict) and "level" in v), key=LEVELS.index, default="OK")
        if any(k.startswith("refusal:") and v == "CRITICAL" for k, v in self._level.items()):
            out["worst"] = "CRITICAL"
        self._last = out
        self._write_state(out)
        return out

    def _refresh_foreign(self) -> None:
        """Rescan at most every FOREIGN_SCAN_SEC, on a daemon thread, so a slow OS call never delays the poll cycle."""
        now = self._clock()
        if now - self._foreign_at < FOREIGN_SCAN_SEC or (self._foreign_busy and now - self._foreign_at < 120.0):
            return  # a scan stuck for 2 min (DNS) is abandoned and retried; the old thread is a daemon
        self._foreign_busy = True
        self._foreign_at = now
        scanner = self.foreign_ws_scanner

        def _run() -> None:
            try:
                self._foreign = scanner() or {}
            except Exception as exc:
                self._foreign = {"ok": False, "error": repr(exc)[:160]}
            finally:
                self._foreign_busy = False

        threading.Thread(target=_run, name="headroom-foreign-ws", daemon=True).start()

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
        real_post = self._real.post   # looked up at call time: patches on the real module still apply
        if (getattr(real_post, "__module__", "") == "requests.api" and not a and "json" in k
                and set(k) <= {"json", "timeout"}):
            try:
                import exchange_truth as _xt  # one shared keep-alive session: a bare post opens a new TCP+TLS connection per read
                resp = _xt.http_post(url, k.get("json"), k.get("timeout"))
            except ImportError:
                resp = real_post(url, *a, **k)
        else:
            resp = real_post(url, *a, **k)
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
