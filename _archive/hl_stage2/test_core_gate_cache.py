import json, os, sys, tempfile, time
from pathlib import Path
import HL_Live_Copy_Service_Core as C

d = Path(tempfile.mkdtemp())
f = d / "snap.json"
C.EXCHANGE_ACCOUNT_SNAPSHOT_FILE = f
G = C.SenderGateway
def write(sz):
    f.write_text(json.dumps({"positions_by_coin": {"BTC": {"signed_size": sz}}}))
os.environ["HL_LIVE_GATE_SNAPSHOT_CACHE_SEC"] = "2"
G._PERSISTED_POS_CACHE.clear()
write(1.0)
p, e = G._persisted_exchange_positions(); assert p == {"BTC": 1.0} and not e, (p, e)
calls = []
orig = G._persisted_exchange_positions_uncached
G._persisted_exchange_positions_uncached = staticmethod(lambda: (calls.append(1), orig())[1])
p, _ = G._persisted_exchange_positions(); assert not calls, "unchanged file must be cache hit"
p["BTC"] = 99  # caller mutation must not poison cache
p, _ = G._persisted_exchange_positions(); assert p == {"BTC": 1.0}
write(2.5)  # size/mtime change invalidates
p, _ = G._persisted_exchange_positions(); assert p == {"BTC": 2.5} and calls
os.environ["HL_LIVE_GATE_SNAPSHOT_CACHE_SEC"] = "0"; calls.clear()
G._persisted_exchange_positions(); G._persisted_exchange_positions(); assert len(calls) == 2
f.unlink(); G._PERSISTED_POS_CACHE.clear()
p, e = G._persisted_exchange_positions(); assert e, "missing file reports unavailable"
print("test_core_gate_cache OK")
