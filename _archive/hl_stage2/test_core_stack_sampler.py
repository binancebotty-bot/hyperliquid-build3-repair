import json, os, tempfile, threading, time
from pathlib import Path
import HL_Live_Copy_Service_Core as C

d = Path(tempfile.mkdtemp())
C.CORE_RUNTIME_STATE_FILE = d / "state.json"
os.environ["HL_LIVE_STACK_SAMPLE_SEC"] = "1"

class Fake:
    _hot_stop_event = threading.Event()
    _stack_sampler = C.LiveCopyCore._stack_sampler

f = Fake()
lock = threading.Lock(); lock.acquire()
w = threading.Thread(target=lambda: lock.acquire(), name="HLCoreWS-hot-send-3", daemon=True); w.start()
s = threading.Thread(target=f._stack_sampler, daemon=True); s.start()
time.sleep(2.6)
f._hot_stop_event.set()
rows = [json.loads(l) for l in (d / "stack_samples.jsonl").read_text().splitlines()]
assert rows, "sampler wrote nothing"
t = rows[-1]["threads"]
assert "HLCoreWS-hot-send" in t, t  # worker number stripped so workers group together
assert sum(t["HLCoreWS-hot-send"].values()) == 1
assert all("HLCore-stack-sampler" not in k for k in t)
print("test_core_stack_sampler OK")
