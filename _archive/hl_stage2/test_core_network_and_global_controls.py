#!/usr/bin/env python3
"""Core engine: network selection and UI Global Controls.

Network: leader feed and follower account are chosen independently; leader fill polling and the
leader WS use the leader network, every follower read (meta, mids, copy fills, clearinghouseState,
exposure) and every order use the follower network. Unknown names, legacy URLs on the other network
and state folders stamped for another pair refuse to start; one engine per state folder.

Global Controls: all eight take effect in Core with the UI's meaning (0/missing = off, empty
allowlist = all). Total and per-asset caps use follower exchange truth over every DEX scope and fail
closed when it is unreadable; closes are never blocked by entry controls.

Run: python test_core_network_and_global_controls.py   # RESULT:: markers, exit 0/1. No network, no orders.
"""
from __future__ import annotations

import json
import re
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
RESULTS = []
FOLLOWER = "0x" + "c" * 40
LEADER = "0x" + "d" * 40
T_INFO, M_INFO = "https://api.hyperliquid-testnet.xyz/info", "https://api.hyperliquid.xyz/info"


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


def run_py(code: str, env: dict, args=()) -> subprocess.CompletedProcess:
    full = {k: v for k, v in os.environ.items() if not k.startswith("HL_")}
    full.update(env)
    full["HL_LIVE_ENV_FILE"] = str(Path(tempfile.mkdtemp()) / "none.env")
    return subprocess.run([sys.executable, "-c", code, *args], cwd=str(HERE), env=full, capture_output=True, text=True, timeout=180)


def last_json(r: subprocess.CompletedProcess):
    return json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 and r.stdout.strip() else r.stderr[-400:]


def network_tests() -> None:
    import exchange_truth as X

    nets = X.resolve_networks({})
    check("N1_DEFAULT_LEADER_MAINNET_FOLLOWER_TESTNET",
          nets["leader"]["info"] == M_INFO and nets["follower"]["info"] == T_INFO
          and nets["follower"]["exchange"] == "https://api.hyperliquid-testnet.xyz/exchange"
          and nets["leader"]["ws"] == "wss://api.hyperliquid.xyz/ws", str(nets))

    def refused(env):
        try:
            X.resolve_networks(env)
            return False
        except X.NetworkConfigError:
            return True
    check("N2_UNKNOWN_NETWORK_REFUSED", refused({"HL_FOLLOWER_NETWORK": "devnet"}) and refused({"HL_LEADER_NETWORK": "x"}))
    check("N3_LEGACY_URLS_ON_OTHER_NETWORK_REFUSED",
          refused({"HL_LIVE_ORDER_ENDPOINT": "https://api.hyperliquid.xyz/exchange"})
          and refused({"HL_LIVE_WS_URL": "wss://api.hyperliquid-testnet.xyz/ws"})
          and refused({"HL_INFO_URL": M_INFO})                       # Core's shared URL cannot serve both
          and not refused({"HL_INFO_URL": M_INFO, "HL_FOLLOWER_NETWORK": "mainnet"}))
    d = Path(tempfile.mkdtemp(prefix="netstamp_"))
    X.claim_network_stamp(d, nets)
    X.claim_network_stamp(d, nets)
    try:
        X.claim_network_stamp(d, X.resolve_networks({"HL_FOLLOWER_NETWORK": "mainnet"}))
        stamped_refused = False
    except X.NetworkConfigError:
        stamped_refused = True
    check("N4_STATE_FOLDER_BOUND_TO_ONE_NETWORK_PAIR", stamped_refused)

    probe = ("import HL_Live_Copy_Service_Core as c, json;"
             "print(json.dumps([c.HL_EXCHANGE_URL, c.HL_WS_URL, c.HL_INFO_URL, c.HL_LEADER_INFO_URL, c.AUDIT_DIR.name]))")
    got = last_json(run_py(probe, {"HL_LEADER_NETWORK": "mainnet", "HL_FOLLOWER_NETWORK": "testnet"}))
    check("N5_CORE_CROSS_NETWORK_ENDPOINTS_AND_STATE_FOLDER",
          got == ["https://api.hyperliquid-testnet.xyz/exchange", "wss://api.hyperliquid.xyz/ws", T_INFO, M_INFO,
                  "hl_live_copy_audit_testnet"], str(got))
    got = last_json(run_py(probe, {"HL_FOLLOWER_NETWORK": "mainnet"}))
    check("N5_CORE_MAINNET_KEEPS_HISTORICAL_STATE_FOLDER",
          got == ["https://api.hyperliquid.xyz/exchange", "wss://api.hyperliquid.xyz/ws", M_INFO, M_INFO,
                  "hl_live_copy_audit"], str(got))
    r = run_py(probe, {"HL_LIVE_ORDER_ENDPOINT": "https://api.hyperliquid.xyz/exchange"})
    check("N5_CORE_MISMATCHED_ENDPOINT_REFUSES_TO_START", r.returncode != 0 and "NETWORK_ENDPOINT_MISMATCH" in r.stderr, r.stderr[-200:])

    route = r'''
import json, HL_Live_Copy_Service_Core as c
calls = []
class R:
    def __init__(self, body): self.body = body
    def json(self): return self.body
def post(url, json=None, timeout=None):
    calls.append([url, json.get("type")])
    t = json.get("type")
    return R({"BTC": "1"} if t == "allMids" else {"assetPositions": []} if t == "clearinghouseState" else [])
c.requests.post = post
c.USER_WALLET = "''' + FOLLOWER + r'''"
c.LeaderFillIngestor().poll_hyperliquid_fills("''' + LEADER + r'''", 0, 1)
c.CopyAccountIngestor().poll_copy_account_fills("''' + FOLLOWER + r'''", 0, 1)
gw = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter()); gw._fetch_all_mids()
c.ExchangeReconciler(c.ManualLedger(), c.AuditLogWriter()).fetch_snapshot()
print(json.dumps(calls))
'''
    calls = last_json(run_py(route, {"HL_LEADER_NETWORK": "mainnet", "HL_FOLLOWER_NETWORK": "testnet",
                                     "HL_LIVE_AUDIT_DIR": str(Path(tempfile.mkdtemp()))}))
    check("N6_LEADER_FILLS_FROM_LEADER_NETWORK", isinstance(calls, list) and calls[0] == [M_INFO, "userFillsByTime"], str(calls))
    check("N6_FOLLOWER_FILLS_MIDS_AND_SNAPSHOT_FROM_FOLLOWER_NETWORK",
          isinstance(calls, list) and calls[1:] == [[T_INFO, "userFillsByTime"], [T_INFO, "allMids"], [T_INFO, "clearinghouseState"]],
          str(calls))

    lock = "import sys, time, HL_Live_Copy_Service_Core as c; c.acquire_instance_lock(c.AUDIT_DIR); print('LOCKED', flush=True); time.sleep(float(sys.argv[1]))"
    shared = str(Path(tempfile.mkdtemp(prefix="inst_")))
    env = {k: v for k, v in os.environ.items() if not k.startswith("HL_")}
    env.update({"HL_LIVE_AUDIT_DIR": shared, "HL_LIVE_ENV_FILE": "/nonexistent.env"})
    first = subprocess.Popen([sys.executable, "-c", lock, "30"], cwd=str(HERE), env=env, stdout=subprocess.PIPE, text=True)
    first.stdout.readline()
    second = run_py(lock, {"HL_LIVE_AUDIT_DIR": shared}, ["0"])
    other = run_py(lock, {"HL_LIVE_AUDIT_DIR": str(Path(tempfile.mkdtemp(prefix="inst_")))}, ["0"])
    first.kill()
    first.wait()
    after = run_py(lock, {"HL_LIVE_AUDIT_DIR": shared}, ["0"])
    check("N7_SECOND_ENGINE_ON_SAME_STATE_REFUSED", second.returncode != 0 and "INSTANCE_ALREADY_RUNNING" in second.stderr, second.stderr[-200:])
    check("N7_PARALLEL_ENGINES_ON_SEPARATE_STATE_RUN", other.returncode == 0 and "LOCKED" in other.stdout, other.stderr[-200:])
    check("N7_LOCK_RELEASED_WHEN_PROCESS_DIES", after.returncode == 0 and "LOCKED" in after.stdout, after.stderr[-200:])

    ui_probe = ("import HL_Copy_App_SSOT as u, json; print(json.dumps([u.LIVE_COPY_AUDIT_DIR.name, u.FOLLOWER_INFO_URL,"
                " u.APP_PORT, u.LIVE_CONFIG_FILE == u.LIVE_COPY_CONFIG_FILE]))")
    ui_dir = Path(tempfile.mkdtemp(prefix="ui_")) / "state_testnet"
    got = last_json(run_py(ui_probe, {"HL_FOLLOWER_NETWORK": "testnet", "HL_APP_PORT": "8011", "HL_LIVE_AUDIT_DIR": str(ui_dir)}))
    check("N8_UI_USES_FOLLOWER_NETWORK_STATE_AND_PORT", got == ["state_testnet", T_INFO, 8011, True], str(got))
    r = run_py(ui_probe, {"HL_FOLLOWER_NETWORK": "mainnet", "HL_LIVE_AUDIT_DIR": str(ui_dir)})
    check("N8_UI_REFUSES_STATE_FOLDER_OF_OTHER_NETWORK", r.returncode != 0 and "NETWORK_STAMP_MISMATCH" in r.stderr, r.stderr[-200:])


def global_controls_tests() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="coregc_"))
    os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LEADER_NETWORK": "mainnet", "HL_FOLLOWER_NETWORK": "testnet",
                       "HL_LIVE_ENV_FILE": str(tmp / "none.env")})
    import HL_Live_Copy_Service_Core as c
    import HL_Copy_App_SSOT as ui
    from fastapi.testclient import TestClient
    ui.LIVE_COPY_CONFIG_FILE = c.LIVE_CONFIG_FILE
    client = TestClient(ui.app)
    c.USER_WALLET = FOLLOWER
    book = {"positions": [], "down": False, "reads": 0}

    def fetcher(payload):
        if payload.get("type") == "perpDexs":
            return [{"name": "xyz"}]
        book["reads"] += 1
        if book["down"]:
            raise RuntimeError("scope unavailable")
        return {"assetPositions": [{"position": p} for p in book["positions"] if p.get("dex", "") == payload.get("dex", "")]}
    c.EXPOSURE_FETCHER = fetcher

    def config(**gc):
        c.atomic_write_json(c.LIVE_CONFIG_FILE, {"auto_send_enabled": False, "global_controls": gc, "wallets": {
            LEADER: {"enabled": True, "mode": "ON", "copy_mode": "fixed", "fixed_notional": 1000}}})

    seq = [0]

    def fill(side="BUY", coin="BTC", price=100.0, size=1.0):
        seq[0] += 1
        return c.LeaderFill(f"f{seq[0]}", LEADER, coin, side, price, size, c.utc_now_ms(), "TEST")

    def decide(gc, positions=(), side="BUY", coin="BTC", ledger=None, builder=None):
        config(**gc)
        book["positions"] = list(positions)
        b = builder or c.IntentBuilder(c.ConfigManager(), ledger or c.ManualLedger(path=tmp / f"pos{seq[0]}.json"))
        i = b.build(fill(side, coin))
        return i.decision, i.reason

    eth = {"coin": "ETH", "szi": "5", "positionValue": "2000"}
    hip3 = {"coin": "xyz:GOLD", "szi": "1", "positionValue": "700", "dex": "xyz"}
    # fixed_notional 1000 at price 100 -> entry of 10 BTC = $1000
    check("G0_ALL_OFF_ENTRY_ALLOWED", decide({})[0] == "ENTRY_ALLOWED", str(decide({})))
    check("G0_NO_EXPOSURE_READS_WHEN_CAPS_OFF", book["reads"] == 0, str(book["reads"]))
    d = decide({"max_total_live_exposure_usd": 3500}, [eth, hip3])
    check("G1_TOTAL_CAP_COUNTS_EVERY_DEX_FROM_EXCHANGE", d == ("SEND_BLOCKED_RISK", "max total exposure exceeded"), str(d))
    check("G1_TOTAL_WITHIN_CAP_ALLOWED", decide({"max_total_live_exposure_usd": 5000}, [eth, hip3])[0] == "ENTRY_ALLOWED")
    d = decide({"max_asset_directional_exposure_usd": 1500}, [{"coin": "BTC", "szi": "6", "positionValue": "600"}])
    check("G2_ASSET_DIRECTIONAL_CAP_BLOCKS", d == ("SEND_BLOCKED_RISK", "max asset directional exposure exceeded"), str(d))
    d = decide({"max_asset_directional_exposure_usd": 1500}, [{"coin": "BTC", "szi": "-6", "positionValue": "600"}])
    check("G2_ASSET_DIRECTIONAL_COUNTS_NET_DIRECTION", d[0] == "ENTRY_ALLOWED", str(d))
    d = decide({"max_wallet_exposure_usd": 500})
    check("G3_WALLET_CAP_BLOCKS", d == ("SEND_BLOCKED_RISK", "max wallet exposure exceeded"), str(d))
    check("G4_BLOCKLIST_BLOCKS_ENTRY", decide({"symbol_blocklist": ["BTC"]}) == ("SYMBOL_UNAVAILABLE", "SYMBOL_BLOCKED"))
    check("G5_ALLOWLIST_BLOCKS_OTHERS", decide({"symbol_allowlist": ["ETH"]}) == ("SYMBOL_UNAVAILABLE", "SYMBOL_NOT_ALLOWED"))
    check("G5_ALLOWLISTED_PASSES", decide({"symbol_allowlist": ["ETH", "BTC"]})[0] == "ENTRY_ALLOWED")
    check("G6_MAX_ORDER_NOTIONAL_BLOCKS", decide({"max_order_notional_usd": 500}) == ("SEND_BLOCKED_RISK", "max order notional exceeded"))

    book["down"] = True
    d = decide({"max_total_live_exposure_usd": 5000})
    check("G7_UNREADABLE_EXCHANGE_TRUTH_FAILS_CLOSED", d[0] == "SEND_BLOCKED_RISK" and "unavailable" in d[1], str(d))
    book["down"] = False

    config(max_total_live_exposure_usd=3500)
    book["positions"] = [eth]
    b = c.IntentBuilder(c.ConfigManager(), c.ManualLedger(path=tmp / "burst.json"))
    first, second = b.build(fill()), b.build(fill())
    check("G8_BURST_INSIDE_CACHE_WINDOW_CANNOT_PASS_CAP",
          first.decision == "ENTRY_ALLOWED" and second.decision == "SEND_BLOCKED_RISK", f"{first.decision} {second.decision}")

    # a close is never blocked by entry controls, even with every control tripped
    ledger = c.ManualLedger(path=tmp / "exit.json")
    ledger.sleeve(LEADER, "BTC")["signed_size"] = 10.0
    d = decide({"symbol_blocklist": ["BTC"], "symbol_allowlist": ["ETH"], "max_total_live_exposure_usd": 1,
                "max_asset_directional_exposure_usd": 1, "max_wallet_exposure_usd": 1, "max_order_notional_usd": 1},
               side="SELL", ledger=ledger)
    check("G9_CLOSE_NEVER_BLOCKED_BY_ENTRY_CONTROLS", d[0] == "EXIT_ALLOWED", str(d))

    config()
    check("G10_MISSING_SLIPPAGE_IS_OFF_NOT_HIDDEN_25BPS", c.ConfigManager().marketable_bps() == 0.0)
    check("G10_MISSING_CLOSE_DIFF_IS_OFF_NOT_HIDDEN_025PCT", c.ConfigManager().max_close_adverse_diff_pct() == 0.0)
    r = client.post("/api/global-controls", json={"marketable_slippage_pct": 0.05, "max_close_adverse_diff_pct": 0.3,
                                                  "max_asset_directional_exposure_usd": 900})
    cm = c.ConfigManager()
    check("G11_UI_SAVE_REACHES_CORE", r.status_code == 200 and cm.marketable_bps() == 5.0
          and cm.max_close_adverse_diff_pct() == 0.3 and cm.max_asset_directional_exposure() == 900.0,
          f"{r.status_code} {cm.marketable_bps()} {cm.max_close_adverse_diff_pct()} {cm.max_asset_directional_exposure()}")
    g = ui._execution_guards_info()
    check("G11_UI_SHOWS_EFFECTIVE_VALUES_AND_NETWORKS", g.get("marketable_bps") == 5.0 and g.get("close_adverse_diff_pct") == 0.3
          and g.get("networks") == {"leader": "mainnet", "follower": "testnet"}, str(g))

    # wire level: limit price, cross-network re-pricing, close-diff guard (fake exchange, no network)
    class FakeExchange:
        def __init__(self):
            self.calls = []

        def order(self, coin, is_buy, size, px, tif, reduce_only=False):
            self.calls.append({"coin": coin, "size": size, "px": px, "reduce_only": reduce_only})
            return {"status": "ok", "response": {"type": "order", "data": {"statuses": [
                {"filled": {"totalSz": str(size), "avgPx": str(px), "oid": 1}}]}}}

    resolved = {"ok": True, "sdk_coin": "BTC", "sz_decimals": 3, "price_max_decimals": 2, "perp_dexs": [""],
                "sdk_order_compatible": True, "min_order_value_usd": 1.0, "min_size": 0.0, "status": "OK"}

    def send(gc, side="BUY", mid=93.0, sleeve=0.0):
        config(**gc)
        led = c.ManualLedger(path=tmp / f"send{seq[0]}.json")
        if sleeve:
            led.sleeve(LEADER, "BTC")["signed_size"] = sleeve
        intent = c.IntentBuilder(c.ConfigManager(), led).build(fill(side))
        fake = FakeExchange()
        gw = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter())
        gw._resolve_coin = lambda coin: dict(resolved)
        gw._get_exchange_client = lambda *a, **k: fake
        gw._exchange_client_has_symbol = lambda *a, **k: True
        gw._validate_final_wire_order = lambda *a, **k: (True, {})
        gw._pre_exchange_asset_safety = lambda *a, **k: (True, {})
        gw._fetch_all_mids = lambda: {"BTC": mid} if mid else {}
        gw._mids_cache = {"BTC": mid} if mid else {}
        os.environ["HL_LIVE_HL_PRIVATE_KEY"] = "0x" + "1" * 64   # placeholder; the fake exchange never signs
        saved = c.HLAccount, c.HLExchange
        c.HLAccount, c.HLExchange = object, object
        try:
            ok, status, res = gw._send_real(intent)
        finally:
            c.HLAccount, c.HLExchange = saved
            os.environ.pop("HL_LIVE_HL_PRIVATE_KEY", None)
        return status, fake.calls, intent

    status, calls, intent = send({"marketable_bps": 10})
    check("G12_CROSS_NETWORK_LIMIT_FROM_FOLLOWER_MID_UNITS_KEPT",
          len(calls) == 1 and abs(calls[0]["px"] - 93.09) < 1e-9 and abs(calls[0]["size"] - intent.copy_size) < 1e-9,
          f"{status} {calls} size={intent.copy_size}")
    status, calls, _ = send({}, mid=0.0)
    check("G12_CROSS_NETWORK_NO_FOLLOWER_PRICE_NO_ORDER", status == "SEND_NOT_ATTEMPTED_FOLLOWER_PRICE_UNAVAILABLE" and not calls, status)
    status, calls, _ = send({"marketable_bps": 50, "max_close_adverse_diff_pct": 0.2}, side="SELL", mid=100.0, sleeve=10.0)
    check("G13_CLOSE_DIFF_GUARD_BLOCKS_CLOSE_TOO_FAR_THROUGH_MID",
          status == "SEND_NOT_ATTEMPTED_CLOSE_ADVERSE_DIFF" and not calls, f"{status} {calls}")
    status, calls, _ = send({"marketable_bps": 10, "max_close_adverse_diff_pct": 0.2}, side="SELL", mid=100.0, sleeve=10.0)
    check("G13_CLOSE_WITHIN_DIFF_SENT_REDUCE_ONLY", len(calls) == 1 and calls[0]["reduce_only"] is True, f"{status} {calls}")
    status, calls, _ = send({"marketable_bps": 50}, side="SELL", mid=100.0, sleeve=10.0)
    check("G13_ZERO_CLOSE_DIFF_IS_OFF", len(calls) == 1, f"{status} {calls}")

    src = (HERE / "HL_Live_Copy_Service_Core.py").read_text(encoding="utf-8-sig")
    sites = len(re.findall(r"exchange\.order\((?!\))", src))
    check("G14_NO_NEW_ORDER_SITE", sites <= 4, str(sites))


def main() -> None:
    network_tests()
    global_controls_tests()
    failed = [n for n, ok in RESULTS if not ok]
    print(f"TOTAL={len(RESULTS)} FAILED={len(failed)}")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
