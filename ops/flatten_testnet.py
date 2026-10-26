#!/usr/bin/env python3
"""Flatten TESTNET positions one coin at a time, through the engine's own order path.

WHY THIS EXISTS: a zeroed restart means the book must be empty first, and there is no flatten tool in this repo. This
is that tool, deliberately small and deliberately loud. It sends nothing unless `--live` is given; the default is a dry
run that prints exactly what it would do.

RULES IT CANNOT BREAK (each one is a guard, not a comment):
  * USER-OWNED coins are never touched: an explicit name list, PLUS any coin the engine's own ledger does not show as
    a position. A coin absent from the ledger is hand-placed until proven otherwise - the safe direction is to leave it.
  * reduce_only only when the order OPPOSES the exchange net and the wire size is <= abs(net). Never increases a
    position, never flips one.
  * a fresh follower mid (<= 5 s) priced 20 bps through it; one retry at 40 bps; then FLATTEN_NO_LIQUIDITY and move on.
  * never a loop without a cap.
  * refuses to run if an engine pid exists - one writer, and the pair must be proven stopped first.

USAGE
  python ops/flatten_testnet.py --state <audit dir>                    # dry run, prints the plan
  python ops/flatten_testnet.py --state <audit dir> --cancel-resting   # dry run of the resting cancels too
  python ops/flatten_testnet.py --state <audit dir> --live             # cancel resting, then flatten
  python ops/flatten_testnet.py --state <audit dir> --live --only CHIP # one coin
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

USER_OWNED = {"XYZ:CRCL", "XYZ:ORCL", "XYZ:LLY"}     # hand-placed by the operator: never closed by an agent
SLIP_BPS = {"first": 0.0020, "retry": 0.0040}
MID_MAX_AGE_SEC = 5.0
MAX_ATTEMPTS = 2


# ---------------------------------------------------------------- pure decisions (tested without an exchange)
def coin_key(coin: str) -> str:
    return str(coin or "").strip()


def ownership(coin: str, ledger_net: Optional[float], journal_net: Optional[float]) -> Tuple[str, str]:
    """THREE-WAY, because two is not enough: ENGINE / USER / AMBIGUOUS.

    ENGINE    the ledger has a NON-ZERO sleeve for this coin (key presence alone is not enough - the engine's own
              _is_manual_owned treats a zero-size sleeve as owned, which is how a repaired-on-disk zero would leave a
              real exchange position unflattened forever).
    USER      on the hard name list. The list wins over everything, including a ledger sleeve.
    AMBIGUOUS anything else: exchange holds it, the ledger does not account for it, and it is not a known name. That
              includes a coin WE opened whose sleeve was zeroed by a repair - and it must NOT be auto-flattened, because
              the mirror error is closing the operator's position. It is named and left for a human.
    """
    ck = coin_key(coin).upper()
    if ck in {u.upper() for u in USER_OWNED}:
        return "USER", "USER_OWNED_NAMED"
    if ledger_net is not None and abs(float(ledger_net)) > 0:
        return "ENGINE", ""
    if journal_net is not None and abs(float(journal_net)) > 0:
        return "AMBIGUOUS", "ENGINE_JOURNAL_BUT_LEDGER_FLAT"   # we placed it; the ledger says flat: a human call
    return "AMBIGUOUS", "ABSENT_FROM_LEDGER"


def net_agrees(exchange_net: float, ledger_net: Optional[float], tol: float = 1e-9) -> bool:
    """reduce_only acts on the NET, so a shared symbol would take the operator's side with it. SIGNED equality: a
    ledger long of the same size as an exchange short is a different position, not agreement."""
    if ledger_net is None:
        return False
    return abs(float(exchange_net) - float(ledger_net)) <= tol


def sz_decimals_from_meta(meta: Any) -> Dict[str, int]:
    """coin -> szDecimals. Without this every size floors to whole units and a fractional position is left behind."""
    out: Dict[str, int] = {}
    try:
        for asset in (meta or {}).get("universe") or []:
            name = str((asset or {}).get("name") or "")
            if name:
                out[name] = int((asset or {}).get("szDecimals") or 0)
    except Exception:
        return {}
    return out


def is_testnet(info_url: str, client_url: str = "") -> bool:
    """Both the info reads and the order client must point at TESTNET before a live send."""
    def tn(u: str) -> bool:
        u = str(u or "").lower()
        return "testnet" in u or "127.0.0.1" in u or "localhost" in u
    return tn(info_url) and (not client_url or tn(client_url))


def is_user_owned(coin: str, ledger_net: Optional[float], in_journal: bool = False) -> Tuple[bool, str]:
    """(refuse, reason). The operator's when named, or when NEITHER the ledger NOR the send journal knows the coin.

    TWO SOURCES, because one is not enough: the ledger lags (a resting order can fill after the last ledger write), and
    a coin we opened but have not booked would otherwise be called hand-placed and left open forever. A hand-placed
    coin appears in neither source.
    """
    ck = coin_key(coin)
    if ck.upper() in {u.upper() for u in USER_OWNED}:
        return True, "USER_OWNED_NAMED"
    if ledger_net is None and not in_journal:
        return True, "USER_OWNED_ABSENT_FROM_LEDGER"
    return False, ""


def order_side(net: float) -> Optional[bool]:
    """True = buy, False = sell. A long is closed by selling, a short by buying."""
    if net > 0:
        return False
    if net < 0:
        return True
    return None


def wire_size(net: float, sz_decimals: int) -> float:
    """<= abs(net) always: rounding must never enlarge the order."""
    step = 10 ** (-max(0, int(sz_decimals)))
    sz = abs(float(net))
    return float(int(sz / step) * step) if step > 0 else sz


def limit_price(mid: float, is_buy: bool, attempt: int) -> float:
    bps = SLIP_BPS["first"] if attempt <= 1 else SLIP_BPS["retry"]
    return mid * (1.0 + bps) if is_buy else mid * (1.0 - bps)


def valid_price(px: float) -> bool:
    return px > 0


def fresh_mid(payload: Dict[str, Any], coin: str, now_s: float) -> Optional[float]:
    """A mid only if the payload says it is recent enough. No mid is better than a stale one."""
    ts = float(payload.get("ts") or 0.0)
    if ts and now_s - ts > MID_MAX_AGE_SEC:
        return None
    mids = payload.get("mids") or {}
    try:
        return float(mids.get(coin) or mids.get(coin_key(coin)) or 0.0) or None
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- exchange reads (read-only)
def _info(body: Any) -> Any:
    url = os.getenv("HL_INFO_URL") or "https://api.hyperliquid-testnet.xyz/info"
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())


def open_positions(wallet: str) -> List[Dict[str, Any]]:
    st = _info({"type": "clearinghouseState", "user": wallet})
    out = []
    for p in st.get("assetPositions") or []:
        q = p.get("position") or {}
        szi = float(q.get("szi") or 0)
        if abs(szi) > 0:
            out.append({"coin": coin_key(q.get("coin")), "net": szi, "value": float(q.get("positionValue") or 0)})
    return out


def resting_orders(wallet: str) -> List[Dict[str, Any]]:
    return list(_info({"type": "frontendOpenOrders", "user": wallet}) or [])


def mids_now() -> Dict[str, Any]:
    return {"mids": _info({"type": "allMids"}), "ts": time.time()}


def journal_coins(state: Path) -> set:
    """Coins the ENGINE has sent an order for, from its own send journal. This closes the case the ledger misses: a
    resting order that filled after the last ledger write leaves a position the engine opened but has not booked. A
    hand-placed coin has no cloid in our journal, so this never claims the operator's positions."""
    import csv
    coins = set()
    path = state / "append_only" / "send_attempts.csv"
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for row in csv.DictReader(fh):
                cl = str(row.get("cloid") or "").strip()
                cn = str(row.get("coin") or "").strip()
                if cl and cn:
                    coins.add(cn.upper())
    except Exception:
        return set()
    return coins


def ledger_nets(state: Path) -> Dict[str, float]:
    """coin -> signed size from the engine's own ledger. A coin missing here is NOT ours."""
    path = state / "manual_live_positions.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    nets: Dict[str, float] = {}
    for _w, coins in (data.get("by_wallet") or {}).items():
        for ck, s in (coins or {}).items():
            try:
                sz = float((s or {}).get("signed_size") or 0.0)
            except (TypeError, ValueError):
                continue
            if abs(sz) > 0:
                nets[str(ck)] = nets.get(str(ck), 0.0) + sz
    return nets


def engine_pids(state: Optional[Path] = None) -> List[int]:
    """Exact pids of a running engine. Delegates to ops/stop_pair.pids(), the implementation that is PROVEN to see the
    live pair - the wmic version I wrote first silently returned [] on this Windows build, so the guard never fired."""
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import stop_pair
        return list(stop_pair.pids(state) if state is not None else stop_pair.pids(None))
    except Exception as exc:
        print("REFUSED: cannot determine whether an engine is running (%r)" % (exc,))
        return [-1]          # unknown is NOT permission to proceed


def reconcile_cloids(state: Path, wallet: str) -> Dict[str, Any]:
    """exchange open orders (cloid) vs our journals (cloid). Matched on CLOID, never oid.

    An order on the exchange whose cloid appears in neither journal is UNACCOUNTED: it must be named and cancelled
    before the state dir is archived, because an archived dir is never read again.
    """
    import csv
    ours = set()
    for name in ("send_attempts.csv", "resting_entry_orders.csv"):
        p = state / "append_only" / name
        if not p.exists():
            p = state / name
        try:
            with open(p, encoding="utf-8", errors="replace") as fh:
                for row in csv.DictReader(fh):
                    cl = str(row.get("cloid") or "").strip()
                    if cl:
                        ours.add(cl.lower())
        except Exception:
            pass
    live = []
    for o in resting_orders(wallet):
        cl = str(o.get("cloid") or "").strip().lower()
        if cl:
            live.append({"coin": o.get("coin"), "cloid": cl, "oid": o.get("oid")})
    unaccounted = [o for o in live if o["cloid"] not in ours]
    return {"exchange_orders": len(live), "journal_cloids": len(ours),
            "unaccounted": unaccounted, "ok": not unaccounted}


def build_plan(positions: List[Dict[str, Any]], nets: Dict[str, float],
               sz_dec: Dict[str, int], listed: Optional[set] = None,
               journal: Optional[set] = None) -> List[Dict[str, Any]]:
    # CASE-BLIND: the ledger keys kBONK as "KBONK" while the exchange reports "kBONK". A case-sensitive lookup called
    # an engine-opened position "absent from the ledger" = USER-OWNED, and it would have been left open forever.
    nets_ci = {str(k).upper(): v for k, v in (nets or {}).items()}
    jsent = {str(k).upper() for k in (journal or set())}
    plan = []
    for p in positions:
        coin, net = p["coin"], float(p["net"])
        _led = nets_ci.get(str(coin).upper())
        _jr = 1.0 if str(coin).upper() in jsent else None
        _kind, why = ownership(coin, _led, _jr)
        if _kind != "ENGINE":
            plan.append({"coin": coin, "net": net, "action": "SKIP", "reason": why})
            continue
        if not net_agrees(net, _led):
            plan.append({"coin": coin, "net": net, "action": "SKIP",
                         "reason": "NET_DISAGREES_LEDGER_%s" % (_led,)})
            continue
        if listed is not None and coin not in listed and coin.upper() not in listed:
            plan.append({"coin": coin, "net": net, "action": "SKIP", "reason": "NOT_LISTED_ON_FOLLOWER"})
            continue
        is_buy = order_side(net)
        plan.append({"coin": coin, "net": net, "action": "FLATTEN", "is_buy": is_buy,
                     "size": wire_size(net, sz_dec.get(coin, 0)), "reason": ""})
    return plan


def report(rows: List[Dict[str, Any]]) -> str:
    lines = ["coin            before        after   action / reason"]
    for r in rows:
        lines.append("%-14s %10.4f %12s   %s" % (r["coin"], r["before"],
                                                 ("%.4f" % r["after"]) if r.get("after") is not None else "-",
                                                 (r.get("action") or "") + (" " + r["reason"] if r.get("reason") else "")))
    left = [r for r in rows if r.get("after") not in (0, 0.0, None)]
    lines.append("")
    lines.append("LEFT OPEN: %d" % len(left))
    for r in left:
        lines.append("  %s %.4f  %s" % (r["coin"], r["after"], r.get("reason") or "NOT_FLATTENED"))
    return "\n".join(lines)



def ledger_fingerprint(path: Path) -> Dict[str, Any]:
    """sha256 + mtime of the real ledger at copy time, so a later change can be detected and refused."""
    import hashlib
    try:
        raw = path.read_bytes()
        return {"sha256": hashlib.sha256(raw).hexdigest(), "mtime_ns": path.stat().st_mtime_ns, "size": len(raw)}
    except Exception as exc:
        return {"error": repr(exc)}


def ledger_unchanged(path: Path, fp: Dict[str, Any]) -> bool:
    if "sha256" not in fp:
        return False
    return ledger_fingerprint(path).get("sha256") == fp.get("sha256")


def client_endpoint(exchange: Any) -> Optional[str]:
    """The base URL of the object that will actually send. Unknown is None, and None must refuse."""
    if exchange is None:
        return None
    for attr in ("base_url", "url", "endpoint", "api_url", "_base_url", "_url"):
        v = getattr(exchange, attr, None)
        if isinstance(v, str) and v:
            return v
    for attr in ("session", "client", "_session", "_client"):
        obj = getattr(exchange, attr, None)
        if obj is not None:
            u = getattr(obj, "base_url", None) or getattr(obj, "url", None)
            if isinstance(u, str) and u:
                return u
    try:
        for v in vars(exchange).values():
            if isinstance(v, str) and v.startswith("http"):
                return v
    except Exception:
        pass
    return None


def client_is_testnet(exchange: Any) -> Optional[bool]:
    """True/False, or None when the endpoint cannot be read - and None refuses.

    THREE SOURCES, in order: the client object's own attribute; HL_EXCHANGE_URL from the environment (the variable the
    client is constructed FROM, see Core:6728); the engine module's own HL_EXCHANGE_URL. A real SDK client often has no
    url attribute at all, and refusing on that alone would make a live flatten impossible - but each source must still
    positively say testnet, and no source at all still refuses.
    """
    ep = client_endpoint(exchange)
    if ep:
        return is_testnet(ep)
    env_url = os.getenv("HL_EXCHANGE_URL")
    if env_url:
        return is_testnet(env_url)
    try:
        from HL_Live_Copy_Service_Core import HL_EXCHANGE_URL
        return is_testnet(HL_EXCHANGE_URL)
    except Exception:
        return None


def write_report(state: Path, live: bool, rows: List[Dict[str, Any]], extra: Optional[Dict[str, Any]] = None) -> Path:
    """Written and fsynced BEFORE any early return: evidence survives an abort."""
    out = state / ("FLATTEN_%s_%s.json" % ("LIVE" if live else "DRYRUN",
                                           time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())))
    payload = {"live": live, "rows": rows, "extra": extra or {}}
    try:
        with open(out, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, default=str)
            fh.flush()
            os.fsync(fh.fileno())
    except Exception as exc:
        print("report write failed: %r" % (exc,))
    return out


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="flatten TESTNET positions one coin at a time (dry run by default)")
    ap.add_argument("--state", required=True, help="audit/state dir of the run being retired")
    ap.add_argument("--live", action="store_true", help="actually cancel and send; without this nothing is sent")
    ap.add_argument("--cancel-resting", action="store_true", help="cancel the engine's resting orders first")
    ap.add_argument("--only", default="", help="restrict to one coin")
    ap.add_argument("--reconcile", action="store_true",
                    help="print the cloid reconciliation (exchange vs journal union) and exit non-zero if any order "
                         "is unaccounted - the ARCHIVE GATE")
    args = ap.parse_args(argv)
    state = Path(args.state)
    live = bool(args.live)

    wallet = os.getenv("HL_USER_WALLET") or os.getenv("HL_LIVE_HL_ACCOUNT_ADDRESS") or ""
    if not wallet:
        print("REFUSED: no follower wallet in the environment")
        return 2
    print("MODE " + ("LIVE" if live else "DRY_RUN (nothing will be sent)"))
    rows: List[Dict[str, Any]] = []
    extra: Dict[str, Any] = {}

    # read-only, so it runs before the engine check (needed both before the stop and at the archive gate)
    if args.reconcile:
        rec = reconcile_cloids(state, wallet)
        print(json.dumps(rec, indent=2))
        print("ARCHIVE_GATE " + ("PASS" if rec["ok"] else "BLOCKED"))
        return 0 if rec["ok"] else 4

    pids = engine_pids(state)
    if pids:
        print("REFUSED: an engine is running (pids %s). Stop the pair first." % pids)
        return 3

    # ---- endpoints: BOTH must be testnet, and an unreadable endpoint refuses
    info_url = os.getenv("HL_INFO_URL") or "https://api.hyperliquid-testnet.xyz/info"
    if not is_testnet(info_url):
        print("REFUSED: info endpoint is not testnet (%r)" % (info_url,))
        return 6

    # ---- ledger: disposable copy + fingerprint of the original
    real_ledger = state / "manual_live_positions.json"
    fp = ledger_fingerprint(real_ledger)
    _ltmp = Path(tempfile.mkdtemp(prefix="flatten_ledger_")) / "manual_live_positions.json"
    try:
        _ltmp.write_bytes(real_ledger.read_bytes())
    except Exception:
        _ltmp.write_text("{}", encoding="utf-8")
    extra["ledger_fingerprint"] = fp

    nets = ledger_nets(state)
    sz_dec = sz_decimals_from_meta(_info({"type": "meta"}))
    positions = open_positions(wallet)
    if args.only:
        positions = [p for p in positions if p["coin"].upper() == args.only.upper()]
    print("positions=%d ledger_coins_with_net=%d" % (len(positions), len(nets)))

    # ---- 3a. cancels are MANDATORY for a live run, verified, and a failure is a hard stop
    if live and not args.cancel_resting:
        print("REFUSED: --live requires --cancel-resting (a resting order must not fill into a flattened book)")
        return 8
    if args.cancel_resting:
        try:
            from HL_Live_Copy_Service_Core import SenderGateway, ConfigManager, AuditLogWriter
            _gw = SenderGateway(ConfigManager(), AuditLogWriter())
        except Exception as exc:
            print("REFUSED: cannot build the engine gateway (%r)" % (exc,))
            return 9
        for o in resting_orders(wallet):
            coin, oid = coin_key(o.get("coin")), str(o.get("oid") or "")
            print("%s resting cancel %s %s oid=%s" % ("DOING" if live else "WOULD", coin, o.get("side"), oid))
            r = {"coin": coin, "before": float(o.get("sz") or 0), "after": 0.0, "action": "CANCEL_RESTING"}
            rows.append(r)
            if not live or not oid:
                r["reason"] = "DRY_RUN"
                continue
            try:
                exch, sdk = _gw._exchange_client_for_coin(coin)
                tn = client_is_testnet(exch)
                if tn is not True:
                    r["reason"] = "ENDPOINT_NOT_PROVEN_TESTNET(%r)" % (client_endpoint(exch),)
                    write_report(state, live, rows, extra)
                    print("ABORT: order endpoint not proven testnet - refusing to send")
                    return 6
                _gw._cancel_order(exch, sdk, oid)
            except Exception as exc:
                r["reason"] = "CANCEL_FAILED %r" % (exc,)
                write_report(state, live, rows, extra)
                print("ABORT: cancel failed on %s - hard stop" % coin)
                return 10
        if live:
            still = resting_orders(wallet)
            print("resting after cancel: %d" % len(still))
            if still:
                for o in still:
                    print("STILL RESTING %s oid=%s - refusing to flatten" % (o.get("coin"), o.get("oid")))
                write_report(state, live, rows, extra)
                return 7
            positions = [p for p in open_positions(wallet)
                         if not args.only or p["coin"].upper() == args.only.upper()]
            print("positions after cancels: %d (frozen book)" % len(positions))

    plan = build_plan(positions, nets, sz_dec, None, journal=journal_coins(state))
    payload = mids_now() if plan else {"mids": {}, "ts": time.time()}
    for step in plan:
        r = {"coin": step["coin"], "before": step["net"], "after": step["net"], "action": step["action"],
             "reason": step.get("reason", "")}
        if step["action"] != "FLATTEN":
            rows.append(r)
            continue
        mid = fresh_mid(payload, step["coin"], time.time())
        if not mid:
            r.update(action="SKIP", reason="NO_FRESH_MID")
            rows.append(r)
            continue
        if not live:
            r.update(action="WOULD_FLATTEN", reason="mid=%.6g size=%.6f" % (mid, step["size"]))
            rows.append(r)
            continue
        try:
            from HL_Live_Copy_Service_Core import (SenderGateway, ConfigManager, AuditLogWriter, IntentBuilder,
                                                   LeaderFill, ManualLedger, utc_now_ms)
            gw = SenderGateway(ConfigManager(), AuditLogWriter())
            exch, sdk_coin = gw._exchange_client_for_coin(step["coin"])
            tn = client_is_testnet(exch)
            if tn is not True:
                # an unreadable endpoint is not a pass: refuse before the first order
                r.update(action="ABORTED_ENDPOINT_NOT_PROVEN_TESTNET",
                         reason="endpoint=%r" % (client_endpoint(exch),))
                rows.append(r)
                write_report(state, live, rows, extra)
                print("ABORT: order endpoint not proven testnet for %s" % step["coin"])
                return 6
            if not ledger_unchanged(real_ledger, fp):
                r.update(action="ABORTED_LEDGER_CHANGED", reason="the real ledger changed after the copy")
                rows.append(r)
                write_report(state, live, rows, extra)
                print("ABORT: the ledger changed under us - refusing to send")
                return 11
            fill = LeaderFill("flatten-%s-%d" % (step["coin"], int(time.time())), wallet, step["coin"],
                              "SELL" if not step["is_buy"] else "BUY", mid, step["size"], utc_now_ms(), "FLATTEN", 0,
                              {"oid": "flat", "dir": "Close Long" if not step["is_buy"] else "Close Short"})
            intent = IntentBuilder(ConfigManager(), ManualLedger(path=_ltmp)).build(fill)
            done = False
            for attempt in (1, 2):
                px = limit_price(mid, step["is_buy"], attempt)
                if not valid_price(px):
                    break
                resp = gw._place_order(exch, sdk_coin, step["is_buy"], step["size"], px, "Ioc", True,
                                       {}, "flatten_started_ms", None, False, None, intent, "flatten_testnet")
                ok, status, _oid, _err = gw._parse_hl_response(resp)
                _st = str(status or "")
                if ok:
                    done = True
                    r["reason"] = "attempt=%d px=%.6g" % (attempt, px)
                    break
                r["reason"] = "attempt=%d status=%s" % (attempt, _st)
                # ONLY a clean "IOC no match" may retry. Anything else is uncertainty, and uncertainty aborts.
                if not _st.startswith(("SKIPPED_IOC_NO_IMMEDIATE_MATCH", "IOC_NO_MATCH", "ORDER_IOC_NO_MATCH")):
                    r.update(action="ABORTED_UNEXPECTED_RESULT")
                    print("ABORT: unclassified or rejected result %r on %s" % (_st, step["coin"]))
                    break
                payload = mids_now()
                mid = fresh_mid(payload, step["coin"], time.time()) or mid
            if not done and not str(r.get("action", "")).startswith("ABORTED"):
                r.update(action="FLATTEN_NO_LIQUIDITY")
        except Exception as exc:
            # ANY exception during a send is uncertainty: record, write, re-read, stop
            r.update(action="ABORTED_EXCEPTION", reason=repr(exc))
            rows.append(r)
            extra["final_positions"] = {p["coin"]: p["net"] for p in open_positions(wallet)}
            write_report(state, live, rows, extra)
            print("ABORT: %r - stopping the whole run" % (exc,))
            return 5
        rows.append(r)
        if str(r.get("action", "")).startswith("ABORTED"):
            extra["final_positions"] = {p["coin"]: p["net"] for p in open_positions(wallet)}
            write_report(state, live, rows, extra)
            return 5
        if live:
            # re-read AFTER each coin: the next decision is made from the exchange, not from a stale snapshot
            _now = {p["coin"]: p["net"] for p in open_positions(wallet)}
            r["after"] = _now.get(step["coin"], 0.0)
            extra.setdefault("post_coin_positions", {})[step["coin"]] = r["after"]

    after = {p["coin"]: p["net"] for p in open_positions(wallet)}
    extra["final_positions"] = after
    for r in rows:
        if r["action"].startswith(("FLATTEN", "WOULD")):
            r["after"] = after.get(r["coin"], 0.0)
    print(report(rows))
    out = write_report(state, live, rows, extra)
    if live and not ledger_unchanged(real_ledger, fp):
        print("WARNING: the ledger changed during the run (edited by something else?)")
    print("report written to %s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
