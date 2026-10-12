#!/usr/bin/env python3
"""The prewarmed SDK clients are keyed exactly as the send path keys them, so the first send on a builder-dex (HIP-3) coin finds its
client already built. Q18b (12 Oct): sdk_client_ms was 1,006 ms on a send because warm_exchange_client stored ("xyz",) while the
send asked for ["", "xyz"].

Run: HL_LIVE_ENV_FILE=/nonexistent python test_core_warm_dex_clients.py
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
os.environ.update({"HL_LIVE_AUDIT_DIR": tempfile.mkdtemp(prefix="warmdex_"), "HL_LIVE_ENV_FILE": "/nonexistent", "HL_LIVE_WS_ENABLED": "0"})
import HL_Live_Copy_Service_Core as c  # noqa: E402

RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


built = []


class FakeAccount:
    @staticmethod
    def from_key(k):
        return object()


class FakeExchange:
    def __init__(self, account, **kw):
        built.append(kw.get("perp_dexs"))


c.HLAccount, c.HLExchange = FakeAccount, FakeExchange
os.environ["HL_LIVE_HL_PRIVATE_KEY"] = "0x" + "11" * 32
g = object.__new__(c.SenderGateway)
g._exchange_cache, g._account_cache = {}, {}
g._meta_cache = {
    "ETH": {"symbol_source": "core_meta", "perp_dexs": None},
    "XYZ:SNDK": {"symbol_source": "builder_meta", "perp_dex": "xyz", "perp_dexs": ["", "xyz"]},
    "ABC:FOO": {"symbol_source": "builder_meta", "perp_dex": "abc"},  # no perp_dexs stored: the send path derives ["", "abc"]
}
g.warm_exchange_client()
after_warm = len(built)
base = c.HL_EXCHANGE_URL[:-len("/exchange")] if c.HL_EXCHANGE_URL.endswith("/exchange") else c.HL_EXCHANGE_URL
addr = os.getenv("HL_LIVE_HL_ACCOUNT_ADDRESS", "").strip() or None
key = os.environ["HL_LIVE_HL_PRIVATE_KEY"]
for dexs in (None, ["", "xyz"], ["", "abc"]):
    g._get_exchange_client(FakeAccount, FakeExchange, key, base, addr, dexs)
check("W1_SEND_PATH_KEYS_ALL_PREBUILT", len(built) == after_warm, "built %d -> %d" % (after_warm, len(built)))
check("W2_ONE_CLIENT_PER_KEY", after_warm == 3, str(built))
check("W3_NO_EMPTY_ONLY_CLIENT", [""] not in built and () not in built, str(built))
failed = [n for n, ok in RESULTS if not ok]
print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
sys.exit(1 if failed else 0)
