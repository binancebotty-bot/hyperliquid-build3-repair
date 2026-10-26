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


def build_plan(positions: List[Dict[str, Any]], nets: Dict[str, float],
               sz_dec: Dict[str, int], listed: Optional[set] = None,
               journal: Optional[set] = None) -> List[Dict[str, Any]]:
    # CASE-BLIND: the ledger keys kBONK as "KBONK" while the exchange reports "kBONK". A case-sensitive lookup called
    # an engine-opened position "absent from the ledger" = USER-OWNED, and it would have been left open forever.
    nets_ci = {str(k).upper(): v for k, v in (nets or {}).items()}
    plan = []
    for p in positions:
        coin, net = p["coin"], float(p["net"])
        refuse, why = is_user_owned(coin, nets_ci.get(str(coin).upper()),
                                    in_journal=bool(journal) and str(coin).upper() in journal)
        if refuse:
            plan.append({"coin": coin, "net": net, "action": "SKIP", "reason": why})
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


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="flatten TESTNET positions one coin at a time (dry run by default)")
    ap.add_argument("--state", required=True, help="audit/state dir of the run being retired")
    ap.add_argument("--live", action="store_true", help="actually cancel and send; without this nothing is sent")
    ap.add_argument("--cancel-resting", action="store_true", help="cancel the engine's resting orders first")
    ap.add_argument("--only", default="", help="restrict to one coin")
    args = ap.parse_args(argv)
    state = Path(args.state)

    wallet = os.getenv("HL_USER_WALLET") or os.getenv("HL_LIVE_HL_ACCOUNT_ADDRESS") or ""
    if not wallet:
        print("REFUSED: no follower wallet in the environment")
        return 2
    live = bool(args.live)
    print("MODE " + ("LIVE" if live else "DRY_RUN (nothing will be sent)"))

    pids = engine_pids(state)
    if pids:
        print("REFUSED: an engine is running (pids %s). Stop the pair first." % pids)
        return 3

    nets = ledger_nets(state)
    positions = open_positions(wallet)
    if args.only:
        positions = [p for p in positions if p["coin"].upper() == args.only.upper()]
    print("positions=%d ledger_coins_with_net=%d" % (len(positions), len(nets)))

    rows: List[Dict[str, Any]] = []

    # ---- 3a. resting orders FIRST: a resting order must never fill into a flattened book
    if args.cancel_resting:
        for o in resting_orders(wallet):
            coin, oid = coin_key(o.get("coin")), str(o.get("oid") or "")
            print("%s resting cancel %s %s oid=%s" % ("WOULD" if not live else "DOING", coin, o.get("side"), oid))
            rows.append({"coin": coin, "before": float(o.get("sz") or 0), "after": 0.0,
                         "action": "CANCEL_RESTING", "reason": "" if live else "DRY_RUN"})
            if live and oid:
                try:
                    from HL_Live_Copy_Service_Core import SenderGateway, ConfigManager, AuditLogWriter
                    gw = SenderGateway(ConfigManager(), AuditLogWriter())
                    exch, _sdk = gw._exchange_client_for_coin(coin)
                    gw._cancel_order(exch, _sdk, oid)
                except Exception as exc:
                    rows[-1]["reason"] = "CANCEL_FAILED %r" % (exc,)
        if live:
            still = resting_orders(wallet)
            print("resting after cancel: %d" % len(still))

    # ---- the flatten plan (built before any order, so the whole book is decided at once)
    plan = build_plan(positions, nets, {}, None, journal=journal_coins(state))
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
        # ---- the real path: build the engine's own intent, then send through _place_order
        try:
            from HL_Live_Copy_Service_Core import (SenderGateway, ConfigManager, AuditLogWriter, IntentBuilder,
                                                   LeaderFill, utc_now_ms)
            gw = SenderGateway(ConfigManager(), AuditLogWriter())
            fill = LeaderFill("flatten-%s-%d" % (step["coin"], int(time.time())), wallet, step["coin"],
                              "SELL" if not step["is_buy"] else "BUY", mid, step["size"], utc_now_ms(), "FLATTEN", 0,
                              {"oid": "flat", "dir": "Close Long" if not step["is_buy"] else "Close Short"})
            intent = IntentBuilder(ConfigManager(), None).build(fill)
            exch, sdk_coin = gw._exchange_client_for_coin(step["coin"])
            done = False
            for attempt in (1, 2):
                px = limit_price(mid, step["is_buy"], attempt)
                if not valid_price(px):
                    break
                resp = gw._place_order(exch, sdk_coin, step["is_buy"], step["size"], px, "Ioc", True,
                                       {}, "flatten_started_ms", None, False, None, intent, "flatten_testnet")
                ok, status, _oid, _err = gw._parse_hl_response(resp)
                if ok:
                    done = True
                    r["reason"] = "attempt=%d px=%.6g" % (attempt, px)
                    break
                r["reason"] = "attempt=%d status=%s" % (attempt, status)
                payload = mids_now()
                mid = fresh_mid(payload, step["coin"], time.time()) or mid
            if not done:
                r.update(action="FLATTEN_NO_LIQUIDITY")
        except Exception as exc:
            r.update(action="FLATTEN_FAILED", reason=repr(exc))
        rows.append(r)

    # ---- after: re-read the exchange, so the report is the exchange's answer, not ours
    after = {p["coin"]: p["net"] for p in open_positions(wallet)}
    for r in rows:
        r["after"] = after.get(r["coin"], 0.0) if r["action"].startswith(("FLATTEN", "WOULD")) else r.get("after")
    print(report(rows))
    out = state / ("FLATTEN_%s_%s.json" % ("LIVE" if live else "DRYRUN", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())))
    try:
        out.write_text(json.dumps({"live": live, "rows": rows}, indent=2), encoding="utf-8")
        print("report written to %s" % out)
    except Exception as exc:
        print("report write failed: %r" % (exc,))
    return 0


if __name__ == "__main__":
    sys.exit(main())
