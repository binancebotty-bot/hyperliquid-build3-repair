"""The isolated follower volume reader; Core can reload only this module live."""
import math


def read_24h_volumes(post_many, dexes):
    payloads = [{"type": "metaAndAssetCtxs", **({"dex": dex} if dex else {})} for dex in dexes]
    results = post_many(payloads)
    if len(results) != len(payloads):
        raise ValueError("metaAndAssetCtxs scope count mismatch")
    vol, listed = {}, set()
    for dex, result in zip(dexes, results):
        if not isinstance(result, dict) or not result.get("ok"):
            raise ValueError("metaAndAssetCtxs unavailable for %s" % (dex or "default"))
        data = result.get("data")
        if not isinstance(data, (list, tuple)) or len(data) < 2:
            raise ValueError("metaAndAssetCtxs returned %r" % (type(data).__name__,))
        universe = data[0].get("universe") or []
        ctxs = data[1] or []
        for asset, ctx in zip(universe, ctxs):
            name = str((asset or {}).get("name") or "")
            if not name:
                continue
            coin = ("%s:%s" % (dex, name) if dex and ":" not in name else name).upper()
            listed.add(coin)
            raw_vol = (ctx or {}).get("dayNtlVlm")
            if raw_vol is None or str(raw_vol).strip() == "":
                continue
            try:
                value = float(raw_vol)
                vol[coin] = value if math.isfinite(value) else None
            except (TypeError, ValueError):
                vol[coin] = None
    if not listed:
        raise ValueError("empty follower universe")
    return vol, listed
