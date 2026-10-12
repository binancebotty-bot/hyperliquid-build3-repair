"""Catch-up after a long gap: stale fills of one leader/coin are copied as their NET change; every id is accounted for.
Run (from _archive/hl_stage2): HL_LIVE_ENV_FILE=/nonexistent python -u test_core_catchup_collapse.py"""
import os, random, sys, tempfile
from pathlib import Path
tmp = Path(tempfile.mkdtemp(prefix="cc_"))
os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LIVE_ENV_FILE": "/nonexistent"})
sys.path.insert(0, str(Path(__file__).resolve().parent))
import HL_Live_Copy_Service_Core as c

R = []
def check(n, ok, d=""):
    R.append((n, bool(ok))); print(("PASS" if ok else "FAIL"), n, d); print("RESULT::%s_%s" % (n, "PASS" if ok else "FAIL"))

NOW = 2_000_000_000_000
W = "0x" + "a" * 40
_n = [0]
def fill(coin, side, size, start, age_min, px=100.0, wallet=W, source="POLL", with_start=True):
    _n[0] += 1
    raw = {"dir": "x"}
    if with_start:
        raw["startPosition"] = str(start)
    return c.LeaderFill(leader_fill_id=f"f{_n[0]:05d}", leader_wallet=wallet, coin=coin, side=side, price=px, size=size,
                        timestamp_ms=NOW - int(age_min * 60000), source=source, raw=raw)
def ids(out, zero):
    got = []
    for f in out:
        got.append(f.leader_fill_id); got += list((f.raw or {}).get("merged_fill_ids") or [])
    return got + [f.leader_fill_id for f, _w in zero]

# 1 grow: open 5 then add 3 -> one BUY 8 carrying both ids
a, b = fill("BTC", "BUY", 5, 0, 300, 100), fill("BTC", "BUY", 3, 5, 299, 110)
out, zero = c.collapse_stale_runs([a, b], NOW)
check("GROW_RUN_IS_ONE_NET_FILL", len(out) == 1 and not zero and out[0].side == "BUY" and abs(out[0].size - 8) < 1e-9 and out[0].leader_fill_id == a.leader_fill_id
      and out[0].raw["merged_fill_ids"] == [b.leader_fill_id] and out[0].raw["dir"] == "Open Long" and abs(out[0].price - (5 * 100 + 3 * 110) / 8) < 1e-9, str(out))
# 2 open and fully closed from flat -> zero rows for every id
a, b, d = fill("ETH", "BUY", 10, 0, 500), fill("ETH", "SELL", 4, 10, 400), fill("ETH", "SELL", 6, 6, 300)
out, zero = c.collapse_stale_runs([a, b, d], NOW)
check("ROUND_TRIP_FROM_FLAT_IS_ZERO", not out and sorted(f.leader_fill_id for f, _w in zero) == sorted([a.leader_fill_id, b.leader_fill_id, d.leader_fill_id]))
# 3 open, partial close, add -> net BUY 8 (open)
a, b, d = fill("SOL", "BUY", 10, 0, 500), fill("SOL", "SELL", 4, 10, 400), fill("SOL", "BUY", 2, 6, 300)
out, zero = c.collapse_stale_runs([a, b, d], NOW)
check("OPEN_REDUCE_ADD_NETS", len(out) == 1 and out[0].side == "BUY" and abs(out[0].size - 8) < 1e-9 and out[0].raw["dir"] == "Open Long" and len(ids(out, zero)) == 3)
# 4 reduce to flat from an existing position -> one SELL close of the whole position
a, b = fill("BTC", "SELL", 3, 8, 300), fill("BTC", "SELL", 5, 5, 299)
out, zero = c.collapse_stale_runs([a, b], NOW)
check("CLOSE_TO_FLAT_IS_ONE_CLOSE", len(out) == 1 and out[0].side == "SELL" and abs(out[0].size - 8) < 1e-9 and out[0].raw["dir"] == "Close Long" and not zero)
# 5 a flip stays as it is
a = fill("BTC", "SELL", 5, 2, 300)
out, zero = c.collapse_stale_runs([a], NOW)
check("FLIP_UNTOUCHED", out == [a] and not zero)
a, b, d = fill("BTC", "BUY", 1, 0, 300), fill("BTC", "SELL", 4, 1, 299), fill("BTC", "BUY", 1, -3, 298)
out, zero = c.collapse_stale_runs([a, b, d], NOW)
check("FLIP_SPLITS_RUNS", len(out) == 3 and sorted(f.leader_fill_id for f in out) == sorted([a.leader_fill_id, b.leader_fill_id, d.leader_fill_id]), str([(f.side, f.size) for f in out]))
# 6 fresh, no startPosition, non-POLL, handled: all kept as they are
f1, f2, f3, f4 = fill("BTC", "BUY", 1, 0, 2), fill("BTC", "BUY", 1, 1, 300, with_start=False), fill("BTC", "BUY", 1, 2, 300, source="WS_CAPTURED"), fill("BTC", "BUY", 1, 3, 300)
out, zero = c.collapse_stale_runs([f1, f2, f3, f4], NOW, handled=lambda f: f.leader_fill_id == f4.leader_fill_id)
check("FRESH_NOSTART_WS_HANDLED_KEPT", sorted(x.leader_fill_id for x in out) == sorted([f1.leader_fill_id, f2.leader_fill_id, f3.leader_fill_id, f4.leader_fill_id]) and not zero)
# 7 broken chain (a fill missing between) -> two separate runs
a, b = fill("BTC", "BUY", 2, 0, 300), fill("BTC", "BUY", 3, 9, 299)
out, zero = c.collapse_stale_runs([a, b], NOW)
check("BROKEN_CHAIN_NOT_COLLAPSED", len(out) == 2)
# 8 big simulated gap: 3 wallets x 3 coins, 1,500 fills over 2.5 days with opens/adds/reduces/flips/round trips
rnd = random.Random(7)
fills, finals = [], {}
for wi in range(3):
    for coin in ("BTC", "ETH", "SOL"):
        pos, wallet = 0.0, "0x" + str(wi + 1) * 40
        start0 = pos
        for k in range(167):
            age = 3600 - k * (3500 / 167) + rnd.random()   # minutes ago: ~2.5 days down to ~1 h
            size = round(rnd.choice([0.5, 1, 2, 3]), 4)
            if pos == 0 and rnd.random() < 0.5:
                side = rnd.choice(["BUY", "SELL"])
            elif pos != 0 and rnd.random() < 0.25:
                side = "SELL" if pos > 0 else "BUY"; size = abs(pos)   # close to flat
            else:
                side = rnd.choice(["BUY", "SELL"])
            fills.append(fill(coin, side, size, pos, age, wallet=wallet))
            pos += size if side == "BUY" else -size
        finals[(wallet, coin)] = (start0, pos)
rnd.shuffle(fills)
out, zero = c.collapse_stale_runs(fills, NOW)
got = ids(out, zero)
check("BIG_GAP_EVERY_ID_EXACTLY_ONCE", sorted(got) == sorted(f.leader_fill_id for f in fills) and len(got) == len(set(got)) == len(fills), f"{len(fills)} fills -> {len(out)} to process + {len(zero)} zero")
net = {}
for f in out:
    net[(f.leader_wallet, f.coin)] = net.get((f.leader_wallet, f.coin), 0.0) + (f.size if f.side == "BUY" else -f.size)
check("BIG_GAP_NET_EQUALS_LEADER_FINAL_MINUS_START", all(abs(net.get(k, 0.0) - (e - s)) < 1e-6 for k, (s, e) in finals.items()), str({k: (round(net.get(k, 0), 3), round(e - s, 3)) for k, (s, e) in list(finals.items())[:3]}))
check("BIG_GAP_FAR_FEWER_FILLS", len(out) < len(fills) * 0.5, f"{len(out)} of {len(fills)}")
check("OFF_SWITCH", len(c.collapse_stale_runs(fills, NOW)[0]) < len(fills) and (os.environ.__setitem__("HL_LIVE_CATCHUP_COLLAPSE", "0") or True) and len(c.collapse_stale_runs(fills, NOW)[0]) == len(fills))
fails = [n for n, ok in R if not ok]
print("TOTAL=%d FAILED=%d" % (len(R), len(fails)))
sys.exit(1 if fails else 0)
