#!/usr/bin/env python3
"""The XNET post_many envelope must be unwrapped before parsing metaAndAssetCtxs."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import HL_Live_Copy_Service_Core as C  # noqa: E402

real_post_many = C._XNET.post_many
old_cache = dict(C._VOL_CACHE)
try:
    C._VOL_CACHE.update({"ts": 0.0, "vol": {}, "listed": set(), "ok": False})
    C._XNET.post_many = lambda *args, **kwargs: [{
        "ok": True,
        "data": [
            {"universe": [{"name": "BTC"}, {"name": "XYZ:EWZ"}]},
            [{"dayNtlVlm": "1200.5"}, {"dayNtlVlm": "25"}],
        ],
    }]
    ok, volumes, listed = C.follower_volumes_24h(refresh=True)
finally:
    C._XNET.post_many = real_post_many
    C._VOL_CACHE.update(old_cache)

passed = (ok and volumes == {"BTC": 1200.5, "XYZ:EWZ": 25.0}
          and listed == {"BTC", "XYZ:EWZ"})
print("RESULT::FOLLOWER_VOLUME_UNWRAPS_XNET_DATA_%s" % ("PASS" if passed else "FAIL"))
if not passed:
    sys.exit(1)
