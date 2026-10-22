"""XYZ close scoping and no-depth recovery are bounded and net-safe (offline synthetic data only)."""
import os, sys, tempfile, threading
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
tmp = Path(tempfile.mkdtemp(prefix="xyz_close_"))
os.environ["HL_LIVE_AUDIT_DIR"] = str(tmp)
os.environ["HL_LIVE_ENV_FILE"] = str(tmp / "missing.env")
os.environ["HL_LIVE_MOCK_SEND"] = "0"
import HL_Live_Copy_Service_Core as c

RESULTS = []
def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok)))
    print("RESULT::%s_%s%s" % (name, "PASS" if ok else "FAIL", (" | " + str(detail)) if detail else ""))

c.USER_WALLET = "0x" + "1" * 40
c.follower_dex_scope = lambda: ["", "xyz"]
scopes, nets = [], {"": 5.0, "xyz": 1.0}
def exposure(_wallet, dexs, **_kwargs):
    scopes.append(list(dexs))
    return {"ok": True, "by_coin": {
        "XYZ:SKHX": {"net": sum(nets[d] for d in dexs)},
        "BTC": {"net": 2.0 if "" in dexs else 0.0},
    }}
c._XNET.master_exposure = exposure

class Ledger:
    def __init__(self, net): self.net = net
    def coin_net(self, _coin): return self.net
    def sleeve(self, _wallet, _coin): return {"signed_size": self.net}
    def wallet_coin_position(self, _wallet, _coin): return self.net

def close_plan(side, size, net):
    sender = SimpleNamespace(ledger=Ledger(net), cfg=SimpleNamespace())
    sender._reduce_only_for_intent = lambda _intent: True
    sender._fresh_exchange_net = lambda coin: c.SenderGateway._fresh_exchange_net(sender, coin)
    sender._floor_wire_size = lambda value, decimals: round(value, decimals)
    intent = SimpleNamespace(fill=SimpleNamespace(coin="xyz:SKHX"), copy_side=side, copy_size=size)
    return c.SenderGateway._close_wire_plan(sender, intent, size, 3, lambda _size: True)

plan = close_plan("SELL", 3.0, 1.0)
check("XYZ_READS_ONLY_ITS_OWN_DEX", scopes[-1:] == [["xyz"]], scopes[-1:])
check("XYZ_OVERSIZE_CLOSE_NOT_REDUCE_ONLY", plan == (False, 3.0, ""), plan)
plan = close_plan("SELL", 0.5, 1.0)
check("XYZ_OPPOSING_WITHIN_NET_IS_REDUCE_ONLY", plan == (True, 0.5, ""), plan)
nets["xyz"] = -1.0
plan = close_plan("SELL", 0.5, -1.0)
check("XYZ_SAME_DIRECTION_IS_NOT_REDUCE_ONLY", plan[0] is False, plan)
default_net = c.SenderGateway._fresh_exchange_net(SimpleNamespace(), "BTC")
check("DEFAULT_MARKET_STAYS_ON_DEFAULT_DEX", scopes[-1:] == [[""]] and default_net == 2.0,
      {"scope": scopes[-1:], "net": default_net})

class Audit:
    def __init__(self): self.rows = []
    def append_reconciliation(self, *args, **kwargs): self.rows.append((args, kwargs))

def active_for_coin(rows, coin):
    key = c.canonical_coin_key(coin)
    for sleeve_id, row in rows.items():
        if c.canonical_coin_key(row.get("coin")) == key:
            return sleeve_id, dict(row)
    return None

intent = SimpleNamespace(
    intent_id="next-close", sleeve_id="leader-b::xyz:skhx", copy_size=0.5, copy_side="SELL",
    reduce_only_intended=True, position_id="p1",
    fill=SimpleNamespace(leader_wallet="0x" + "2" * 40, leader_fill_id="fill-2", coin="xyz:SKHX", price=100.0),
)
orders, audit = [], Audit()
gateway = SimpleNamespace(
    ledger=Ledger(1.0), _recovery_intent_ids=set(), _exit_recovery_exists=lambda _intent: False,
    _standing_closes={"leader-a::xyz:skhx": {
        "oid": "resting-no-depth", "coin": "xyz:SKHX", "side": "SELL", "size": 0.5,
        "intent_id": "prior-close", "reduce_only": True,
    }}, _resting_lock=threading.RLock(), audit=audit,
    cfg=SimpleNamespace(master_switch_now=lambda: True),
    _standing_close_for_coin=lambda coin: active_for_coin(gateway._standing_closes, coin),
    _resolve_coin=lambda _coin: {"ok": True, "sdk_coin": "SKHX"},
    _effective_symbol_min_notional=lambda _resolved: 1.0,
    _close_wire_plan=lambda _intent, size, *_args, **_kwargs: (True, size, ""),
    _place_order=lambda *_args, **_kwargs: orders.append("duplicate") or {},
    _parse_hl_response=lambda _response: (True, "ORDER_RESTING", "new-oid", ""),
    _record_placed_order=lambda *_args, **_kwargs: None,
)
c.SenderGateway._queue_exit_recovery_if_needed(gateway, object(), "SKHX", intent, 99.0, 0.5,
                                               {}, "IOC_NO_IMMEDIATE_MATCH")
check("XYZ_ZERO_DEPTH_STANDING_CLOSE_NOT_STACKED",
      not orders and gateway._standing_closes["leader-a::xyz:skhx"]["oid"] == "resting-no-depth", orders)

now = c.utc_now_ms()
fill = c.LeaderFill("f3", "0x" + "2" * 40, "xyz:SKHX", "SELL", 99.0, 0.5, now, "TEST")
close_intent = c.Intent(
    intent_id="close-3", fill=fill, copy_side="SELL", copy_size=0.5, copy_notional=49.5,
    wallet_mode="LIVE", copy_mode="fixed", decision="EXIT_ALLOWED", reason="EXIT",
    sleeve_id="leader-b::xyz:skhx", position_id="p3", position_direction_before="LONG",
    wallet_position_before=0.5, coin_net_before=0.5, reduce_only_intended=True,
    reduce_only_sent_planned=True, created_at_ms=now, notes="lifecycle=EXIT",
)
blocks, sends = [], []
resting = {"leader-a::xyz:skhx": {"coin": "xyz:SKHX", "oid": "resting-no-depth"}}
sender = SimpleNamespace(
    cfg=SimpleNamespace(master_switch_now=lambda: True, send_mode_now=lambda: "ON"), sender_key_invalid="",
    _market_halted_until_ms={}, _ioc_no_match_until_ms={}, _base_timing=lambda _intent: {},
    _pre_send_ownership_gate=lambda _intent: (True, {}), _reduce_only_for_intent=lambda _intent: True,
    _pending_exit_lock=threading.Lock(), _last_exit_attempt_ms={"xyz:skhx": c.utc_now_ms() - 61000},
    _pending_exit_guard={}, _pending_exit_blocked=lambda _intent: (False, ""), _mark_pending_exit=lambda _intent: None,
    _standing_closes=resting, _resting_lock=threading.RLock(),
    _standing_close_for_coin=lambda coin: active_for_coin(resting, coin),
    _append_local_block_reconciliation=lambda _intent, status, _result: blocks.append(status),
    _send_real=lambda _intent, _timing: sends.append(_intent) or (True, "ORDER_FILLED", {"exchange_called": True}),
    _append_real_attempt=lambda *_args: None, leader_reduced_since=lambda _fill: 0,
)
c.stale_snapshot_replay_reason = lambda _fill: ""
status = c.SenderGateway.send_if_allowed(sender, close_intent)
check("XYZ_OTHER_SLEEVE_RESTING_CLOSE_BLOCKS_NEW_SEND",
      status == (False, "PENDING_EXIT_GUARD_ACTIVE") and not sends and blocks == ["PENDING_EXIT_GUARD_ACTIVE"],
      {"status": status, "send_count": len(sends), "blocks": blocks})

cooldown_sender = SimpleNamespace(**vars(sender))
cooldown_sender._standing_closes = {}
cooldown_sender._last_exit_attempt_ms = {"xyz:skhx": c.utc_now_ms() - 1000}
send_count_before = len(sends)
cooldown_status = c.SenderGateway.send_if_allowed(cooldown_sender, close_intent)
check("XYZ_DUPLICATE_CLOSE_HONORS_60S_GUARD",
      cooldown_status == (False, "EXIT_ATTEMPT_COOLDOWN") and len(sends) == send_count_before, cooldown_status)

failed = [name for name, ok in RESULTS if not ok]
print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
raise SystemExit(1 if failed else 0)
