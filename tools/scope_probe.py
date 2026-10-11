#!/usr/bin/env python3
"""Read-only probe of the follower scope sweep: which perp DEX read fails, with what HTTP status, how long it takes.

    python tools/scope_probe.py <follower_info_url> <follower_account_address> [concurrency=8]

e.g. python tools/scope_probe.py https://api.hyperliquid-testnet.xyz/info 0xYourFollowerAddress
Sends only perpDexs and clearinghouseState reads (no key, no orders). Prints one summary block; attach it to issue #3.
"""
import collections
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import requests


def one(url, payload, timeout=8.0):
    t0 = time.monotonic()
    try:
        r = requests.post(url, json=payload, timeout=timeout)
        ms = int((time.monotonic() - t0) * 1000)
        if r.status_code != 200:
            return {"ok": False, "why": f"HTTP {r.status_code}", "ms": ms, "body": r.text[:80]}
        try:
            data = r.json()
        except Exception as exc:
            return {"ok": False, "why": f"bad json {type(exc).__name__}", "ms": ms, "body": r.text[:80]}
        return {"ok": True, "ms": ms, "data": data}
    except Exception as exc:
        return {"ok": False, "why": type(exc).__name__ + ": " + str(exc)[:80], "ms": int((time.monotonic() - t0) * 1000)}


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    url, addr = argv[1], argv[2]
    workers = int(argv[3]) if len(argv) > 3 else 8
    enum = one(url, {"type": "perpDexs"})
    print("perpDexs:", {k: v for k, v in enum.items() if k != "data"})
    if not enum["ok"]:
        return 1
    names = sorted({(i.get("name") if isinstance(i, dict) else i) or "" for i in enum["data"] if (i.get("name") if isinstance(i, dict) else i)} | {""})
    print("dex count:", len(names))
    for label, w in (("concurrent", workers), ("sequential-sample", 1)):
        sample = names if w > 1 else names[:20]
        t0 = time.monotonic()
        with ThreadPoolExecutor(max_workers=w) as pool:
            res = list(pool.map(lambda d: (d, one(url, {"type": "clearinghouseState", "user": addr, **({"dex": d} if d else {})})), sample))
        wall = time.monotonic() - t0
        bad = [(d, r) for d, r in res if not r["ok"]]
        ms = sorted(r["ms"] for _d, r in res)
        print(f"{label}: workers={w} reads={len(res)} failed={len(bad)} wall={wall:.1f}s p50={ms[len(ms)//2]}ms max={ms[-1]}ms")
        print("  failure reasons:", dict(collections.Counter(r["why"] for _d, r in bad)))
        for d, r in bad[:10]:
            print("  failed dex", repr(d), r)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
