#!/usr/bin/env python3
"""The XNET post_many envelope must be unwrapped before parsing metaAndAssetCtxs."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import HL_Live_Copy_Service_Core as C  # noqa: E402

real_post_many = C._XNET.post_many
real_scope = C.follower_dex_scope
old_cache = dict(C._VOL_CACHE)
seen = []
try:
    C._VOL_CACHE.update({"ts": 0.0, "vol": {}, "listed": set(), "ok": False})
    C.follower_dex_scope = lambda: ["", "xyz"]

    def fake_post_many(_fetcher, payloads, *_args, **_kwargs):
        results = []
        for payload in payloads:
            seen.append(payload)
            if payload.get("dex") == "xyz":
                data = [{"universe": [{"name": "EWZ"}]}, [{"dayNtlVlm": "25"}]]
            else:
                data = [{"universe": [{"name": "BTC"}]}, [{"dayNtlVlm": "1200.5"}]]
            results.append({"ok": True, "data": data})
        return results

    C._XNET.post_many = fake_post_many
    ok, volumes, listed = C.follower_volumes_24h(refresh=True)
finally:
    C._XNET.post_many = real_post_many
    C.follower_dex_scope = real_scope
    C._VOL_CACHE.update(old_cache)

passed = (ok and volumes == {"BTC": 1200.5, "XYZ:EWZ": 25.0}
          and listed == {"BTC", "XYZ:EWZ"}
          and [payload.get("dex", "") for payload in seen] == ["", "xyz"])
print("RESULT::FOLLOWER_VOLUME_UNWRAPS_XNET_DATA_%s" % ("PASS" if passed else "FAIL"))
if not passed:
    print("DETAIL::volume keys=%r listed=%r dexes=%r" % (sorted(volumes), sorted(listed),
                                                           [payload.get("dex", "") for payload in seen]))
    sys.exit(1)
