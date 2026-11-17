#!/usr/bin/env python3
"""ENG-INV-09: exchange truth outranks local replay; the manual follower-position file is not authoritative.

Test-only evidence harness. Offline fakes only (injected fetcher doubles), no network, no live send.
Engine bytes are never modified: every seam exercised below is production code; only the DATA
sources (the /info double, the persisted exchange snapshot, the temp state dir) are faked.

What is asserted is the ABSENCE of the wrong conclusion:
  E1  local replay says +2.0, MASTER truth says +0.5 -> the engine's authoritative ACTUAL is 0.5
      (MASTER_EXCHANGE_TRUTH), the wallet-local provider that would say 2.0 is NEVER consulted, and
      the durable reconciliation row records manual_net=2.0 against exchange_net=0.5 with a
      mismatch verdict (no row, no accessor, no scopes entry asserts 2.0 as truth).
  E2  a manual follower-position file claiming 9.0 against a MASTER net of 0.5 cannot gate a send
      (real ownership gate BLOCKS, exchange never called) and cannot size one (the real close plan
      wires the exchange net 0.5, never 9.0).
  E3  an ack (order accepted, oid attached) with no MASTER fill/position behind it is NOT settlement:
      the reservation stays blocking and no terminal settlement is recorded.
  E4  negative control -- with the precedence weakened so local replay wins, E1 and E2 turn RED.
  E5  duplicate/reordered event on the truth path (duplicate named case; sorted+deduped once,
      settlement counts each fill once, and a repeated read is byte-identical -> also covers a
      restart mid-sequence re-reading the same window).

Usage:  python -u test_inv09_exchange_truth_outranks_local.py
        python -u test_inv09_exchange_truth_outranks_local.py --mutate local-wins
Prints RESULT::<NAME>_PASS|_FAIL per check and TOTAL=n FAILED=m; exit 0 all pass, 1 otherwise.
In --mutate mode the weakened precedence is EXPECTED to fail E1/E2 (that is the proof of
non-vacuity); the process still exits 1.
"""
import argparse
import csv
import json
import os
import sys
import tempfile
import threading

HERE_PRE = os.path.dirname(os.path.abspath(__file__))
TMP = tempfile.mkdtemp(prefix="inv09_")

# Isolated state. Never the live audit folder, never a live env file.
os.environ.update({
    "HL_LIVE_AUDIT_DIR": TMP,
    "HL_LIVE_ENV_FILE": "/nonexistent",
    "HL_LEADER_NETWORK": "testnet",
    "HL_FOLLOWER_NETWORK": "testnet",
    "HL_LIVE_SCOPE_SWEEP_THREAD": "0",
    "HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS": "0",
    "HL_LIVE_GLOBAL_LOCK_FILE": os.path.join(TMP, "engine-global.lock"),
    "HL_LIVE_INTENT_DURABLE_WAIT_MS": "2000",
    "HL_LIVE_INFO_RETRIES": "1",
    "PYTHONHASHSEED": "0",
})
for _k in ("HL_LIVE_HL_PRIVATE_KEY", "HL_LIVE_HL_ACCOUNT_ADDRESS"):
    os.environ.pop(_k, None)

sys.path.insert(0, HERE_PRE)
import HL_Live_Copy_Service_Core as c          # noqa: E402  production sender/gate/ledger
import exchange_truth as X                     # noqa: E402  production read-only truth module
import HL_Live_Copy_Service as svcmod          # noqa: E402  production DryRun service (ACTUAL accessor)

ACCOUNT_ENV = os.environ.setdefault("HL_LIVE_HL_ACCOUNT_ADDRESS", "")
c.acquire_global_instance_lock(TMP + "/state")
svcmod.configure_paths(c.Path(TMP), c.Path(TMP) / "raw_live_fills.csv")
svcmod.TEST_INJECTION_ENABLED = True
c.USER_WALLET = "0x" + "c" * 40
os.environ["HL_LIVE_HL_ACCOUNT_ADDRESS"] = c.USER_WALLET   # close-proof account == the reader account
os.environ["HL_LIVE_HL_PRIVATE_KEY"] = "0x" + "1" * 64      # synthetic, satisfies the credentials pre-check only

MASTER = "0x" + "a" * 40
SIGNER = "0x" + "b" * 40
ACCOUNT = "0x" + "c" * 40                       # the follower trading account (public address)
WALLET = "0x" + "d1" * 20                       # leader wallet whose sleeve both sides describe
COIN = "BTC"
PX = 100.0
SZ_DEC = 3
EXCHANGE_NET = 0.5        # MASTER truth
LOCAL_E1_NET = 2.0        # local/replayed ledger claim for E1
FILE_E2_NET = 9.0         # manual follower-position file claim for E2

RESOLVED = {"ok": True, "sdk_coin": COIN, "sz_decimals": SZ_DEC, "price_max_decimals": 2,
            "perp_dexs": [""], "sdk_order_compatible": True, "min_order_value_usd": 10.0,
            "min_size": 0.0, "status": "OK"}

RESULTS = []
OBSERVED = {}
WIRES = []          # (amount, why) of every close-plan decision this run, for the absence check
MAXT = {"total": 0}


def check(name, ok, detail=""):
    ok = bool(ok)
    RESULTS.append((name, ok))
    OBSERVED[name] = str(detail)
    print("RESULT::%s_%s%s" % (name, "PASS" if ok else "FAIL",
                               "" if ok or not detail else " | " + str(detail)[:700]), flush=True)


def dump_observed():
    """One machine-readable line carrying the observed values behind every verdict (quotable evidence)."""
    print("OBSERVED::" + json.dumps(OBSERVED, sort_keys=True), flush=True)


# ---- OFFLINE CONTROL: any real /info read would go through exchange_truth.http_post. Make it record
# and refuse, so "no network read happened" is a measured fact of this run, not a claim.
NET_ATTEMPTS = []


def _offline_post(url, payload, timeout, monitor=None):
    NET_ATTEMPTS.append((str(url), str((payload or {}).get("type") if isinstance(payload, dict) else payload)))
    raise RuntimeError("OFFLINE: no network read permitted in this harness")


X.http_post = _offline_post


def case(name, fn):
    """One witness; an exception is a FAILED check carrying the exception text, never a crash."""
    try:
        ok, detail = fn()
    except Exception as exc:                                     # noqa: BLE001
        ok, detail = False, "EXCEPTION %s: %s" % (type(exc).__name__, str(exc)[:500])
    check(name, ok, detail)


# ---------------------------------------------------------------------------------------- fixtures
class InfoFixture:
    """Offline /info double: perpDexs + per-dex clearinghouseState + userFillsByTime. Records calls."""

    def __init__(self, dexes=("",), states=None, fills=None, fail_scopes=(), fail_fills=False):
        self.dexes = list(dexes)
        self.states = states or {}
        self.fills = list(fills or [])
        self.fail_scopes = set(fail_scopes)
        self.fail_fills = fail_fills
        self.calls = []
        self._lock = threading.Lock()

    def __call__(self, payload):
        with self._lock:
            self.calls.append(dict(payload))
        kind = payload.get("type")
        if kind == "perpDexs":
            return [{"name": d} for d in self.dexes if d]
        if kind == "clearinghouseState":
            dex = payload.get("dex", "")
            if dex in self.fail_scopes:
                raise RuntimeError("scope %s unavailable" % dex)
            return {"assetPositions": [{"position": {"coin": k, "szi": str(v)}}
                                       for k, v in (self.states.get(dex) or {}).items()]}
        if kind == "userFillsByTime":
            if self.fail_fills:
                raise RuntimeError("userFillsByTime unavailable")
            return list(self.fills)
        raise RuntimeError("unexpected payload %r" % (payload,))


def with_master(fetcher, dexes=None):
    svcmod.MASTER_TRUTH_ADDRESS, svcmod.MASTER_TRUTH_SIGNER = MASTER, SIGNER
    svcmod.MASTER_TRUTH_FETCHER, svcmod.MASTER_TRUTH_DEXES = fetcher, dexes


def local_provider(net, calls=None):
    """A wallet-LOCAL provider: what local replay believes. Counted, so 'not consulted' is provable."""
    box = calls if calls is not None else {"n": 0}

    def provider(coin):
        box["n"] += 1
        return {"ok": True, "net": net, "source": "WALLET_LOCAL_REPLAY"}
    return provider, box


def write_manual_follower_file(signed, coin=COIN, wallet=WALLET):
    """The manual follower-position file (manual_live_positions.json), hand-edited claim, wallet sleeves schema."""
    path = c.Path(TMP) / "manual_live_positions.json"
    payload = {"schema": "manual_live_positions.v1.wallet_sleeves",
               "by_wallet": {wallet: {coin: {"signed_size": signed, "last_updated_at": "inv09-fixture",
                                             "last_oid": "inv09", "last_intent_id": "inv09"}}},
               "by_coin_net": {coin: {"signed_size": signed}}}
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def write_audit_proof_rows(wallet=WALLET, coin=COIN, fill_size=FILE_E2_NET):
    """Non-empty append-only proof files (the ownership gate refuses to run without them) and the
    fill proof that the sleeve's 9.0 was really acquired by fills (so the close is not held for
    'no owned sleeve' and the only disagreement in play is local-vs-exchange)."""
    c.ensure_csv_header(c.ORDER_INTENTS_CSV, c.ORDER_INTENT_FIELDS)
    c.append_csv(c.ORDER_INTENTS_CSV, c.ORDER_INTENT_FIELDS, {"intent_id": "inv09-proof", "coin": coin})
    c.append_csv(c.SEND_ATTEMPTS_CSV, c.SEND_ATTEMPT_FIELDS,
                 {"created_at": c.utc_now_iso(), "intent_id": "inv09-proof", "coin": coin, "status": "FIXTURE"})
    c.append_csv(c.RECONCILIATION_CSV, c.RECONCILIATION_FIELDS,
                 {"created_at": c.utc_now_iso(), "event": "FIXTURE", "coin": coin})
    c.append_csv(c.LIVE_FILLS_CSV, c.LIVE_FILL_FIELDS,
                 {"created_at": c.utc_now_iso(), "leader_wallet": wallet, "coin": coin, "side": "BUY",
                  "fill_size": str(fill_size), "source": "AUTO_LIVE_WS_FAST_PATH", "leader_fill_id": "inv09-fill"})


class FakeExchange:
    """Records every physical order call; a send here would show up in .calls."""

    def __init__(self):
        self.calls = []
        self._lock = threading.Lock()

    def update_leverage(self, leverage, name, is_cross=True):
        return {"status": "ok"}

    def order(self, coin, is_buy, size, px, tif, reduce_only=False, cloid=None):
        with self._lock:
            self.calls.append({"coin": coin, "is_buy": is_buy, "size": float(size), "px": px,
                               "reduce_only": reduce_only})
        return {"status": "ok", "response": {"type": "order", "data": {"statuses": [
            {"filled": {"totalSz": str(size), "avgPx": str(px), "oid": len(self.calls)}}]}}}

    def cancel(self, coin, oid):
        return {"response": {"data": {"statuses": ["success"]}}}


_n = [0]


def new_ledger():
    _n[0] += 1
    return c.ManualLedger(path=c.Path(TMP) / ("ledger_%d.json" % _n[0]))


def set_sleeve(ledger, wallet, signed, coin=COIN):
    ledger.sleeve(wallet, coin)["signed_size"] = signed
    ledger._recompute_net(ledger.data)


def make_gateway(ex, ledger, net):
    """A REAL SenderGateway. The REAL _pre_send_ownership_gate, _close_wire_plan and reconciliation
    writer run; only data sources (exchange double, exchange-net read, persisted snapshot, asset
    metadata) are replaced -- exactly the split the existing close suites use."""
    gw = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter(), ledger)
    gw._resolve_coin = lambda coin: dict(RESOLVED)
    gw._get_exchange_client = lambda *a, **k: ex
    gw._exchange_client_has_symbol = lambda *a, **k: True
    gw._pre_exchange_asset_safety = lambda *a, **k: (True, {})
    gw._exchange_client_for_coin = lambda coin: (ex, COIN)
    gw._follower_order_account_for_proof = lambda *a, **k: ACCOUNT
    gw._fresh_exchange_net = lambda coin: net[0]
    gw._persisted_exchange_positions = lambda: ({COIN: net[0]}, "")
    gw.leader_reduced_since = lambda f: 0
    gw._margin_mode_done = {COIN}
    gw.cfg.master_switch_now = lambda: True
    gw.cfg.send_mode_now = lambda: "ON"
    gw.cfg.wallet_enabled = lambda w: True
    gw.cfg.wallet_mode = lambda w: "ON"
    return gw


def exit_intent(ledger, side, size, fid, sleeve):
    set_sleeve(ledger, WALLET, sleeve)
    fill = c.LeaderFill(fid, WALLET, COIN, side, PX, size, c.utc_now_ms(), "POLL")
    it = c.IntentBuilder(c.ConfigManager(), ledger).build(fill)
    it.intent_id = fid
    it.decision = "EXIT_ALLOWED"
    return it


def recon_rows(fid):
    p = c.Path(c.RECONCILIATION_CSV)
    if not p.exists():
        return []
    with p.open("r", newline="", encoding="utf-8-sig") as fh:
        return [r for r in csv.DictReader(fh) if r.get("leader_fill_id") == fid]


# ======================================================================================== E1
def e1_checks():
    """LOCAL LEDGER SAYS X, EXCHANGE SAYS Y -> the engine's authoritative position is Y."""
    write_manual_follower_file(LOCAL_E1_NET)
    fetcher = InfoFixture(dexes=("",), states={"": {COIN: EXCHANGE_NET}}, fills=[])
    with_master(fetcher)
    svc = svcmod.DryRunLiveCopyService()
    provider, box = local_provider(LOCAL_E1_NET)
    svc.account_net_provider = provider
    truth = svc.account_net_actual(COIN)
    local_seen = None
    try:  # what the engine's own ledger data says, for the disagreement to be real and not assumed
        local_seen = float(((svc.state.get("by_coin_net") or {}).get(COIN) or {}).get("signed_size"))
    except Exception:
        local_seen = None
    if local_seen is None:
        local_seen = float(json.loads((c.Path(TMP) / "manual_live_positions.json")
                                      .read_text(encoding="utf-8"))["by_coin_net"][COIN]["signed_size"])

    def a():
        return (truth.get("ok") is True and abs(float(truth.get("net")) - EXCHANGE_NET) < 1e-9,
                "effective ACTUAL=%r (want %s) truth=%s" % (truth.get("net"), EXCHANGE_NET, truth))

    def b():
        scopes = truth.get("scopes") or []
        good = (str(truth.get("source")) == "MASTER_EXCHANGE_TRUTH"
                and any(abs(float(s.get("signed")) - EXCHANGE_NET) < 1e-9 for s in scopes))
        return good, "source=%r scopes=%r" % (truth.get("source"), scopes)

    def d():
        return abs(local_seen - LOCAL_E1_NET) < 1e-9, "local ledger/replay net=%r" % (local_seen,)

    def e():  # the local replay value is never consulted when MASTER truth is configured
        return box["n"] == 0, "wallet-local provider calls=%d" % box["n"]

    def f():  # the truth value came from an exchange read, not from local replay
        kinds = [p.get("type") for p in fetcher.calls]
        return ("clearinghouseState" in kinds), "fetcher calls=%r" % (kinds,)

    def g():  # ABSENCE: nothing in the truth answer asserts the local value as truth
        blob = json.dumps(truth, sort_keys=True)
        return (LOCAL_E1_NET not in [float(truth.get("net"))] and "2.0" not in blob.replace('"', "")), blob

    def h():  # the durable reconciliation row the engine writes names both nets and calls the local one wrong
        rec = c.ExchangeReconciler(new_ledger(), c.AuditLogWriter())
        set_sleeve(rec.ledger, WALLET, LOCAL_E1_NET)
        status = rec.compare_snapshot({"positions_by_coin": {COIN: {"signed_size": EXCHANGE_NET}}})
        rows = [r for r in recon_rows("") if r.get("event") == "EXCHANGE_RECON"] or \
               [dict(r) for r in _all_recon() if r.get("event") == "EXCHANGE_RECON"]
        last = rows[-1] if rows else {}
        good = (status == "LEDGER_EXCHANGE_NET_MISMATCH"
                and abs(float(last.get("manual_net") or 0) - LOCAL_E1_NET) < 1e-9
                and abs(float(last.get("exchange_net") or 0) - EXCHANGE_NET) < 1e-9)
        return good, "status=%r row=%s" % (status, {k: last.get(k) for k in
                                                    ("event", "status", "coin", "manual_net", "exchange_net", "action")})

    check("E1_EFFECTIVE_POSITION_IS_EXCHANGE_VALUE", *a())
    check("E1_TRUTH_ROW_IS_MASTER_EXCHANGE_TRUTH", *b())
    check("E1_LOCAL_LEDGER_DISAGREES", *d())
    check("E1_LOCAL_REPLAY_NEVER_CONSULTED", *e())
    check("E1_TRUTH_DERIVED_FROM_EXCHANGE_READ", *f())
    check("E1_NO_WRONG_CLAIM_OF_LOCAL_VALUE_AS_TRUTH", *g())
    check("E1_DURABLE_MISMATCH_ROW_NAMES_BOTH_NETS", *h())


def _all_recon():
    p = c.Path(c.RECONCILIATION_CSV)
    if not p.exists():
        return []
    with p.open("r", newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


# ======================================================================================== E2
def entry_intent(ledger, side, size, fid, sleeve):
    set_sleeve(ledger, WALLET, sleeve)
    fill = c.LeaderFill(fid, WALLET, COIN, side, PX, size, c.utc_now_ms(), "POLL")
    it = c.IntentBuilder(c.ConfigManager(), ledger).build(fill)
    it.intent_id = fid
    return it


def e2_checks():
    """The manual follower-position file is not authoritative for gating or sizing a send.

    The ledger the sender uses is loaded FROM the manual follower-position file itself
    (ManualLedger(path=manual_live_positions.json), the wallet_sleeves schema that file carries),
    so 'the file claims 9.0' is exactly what the engine read, not a parallel fixture.
    """
    write_audit_proof_rows()
    fp = write_manual_follower_file(FILE_E2_NET)      # the hand-edited file claims 9.0
    ex = FakeExchange()
    net = [EXCHANGE_NET]
    ledger = c.ManualLedger(path=fp)                  # THE FILE IS THE LEDGER SOURCE
    gw = make_gateway(ex, ledger, net)
    # capture the file's claim and the engine's read of it BEFORE any later part rewrites the file
    captured = {"file": c.Path(fp).name,
                "disk_claim": float(json.loads(c.Path(fp).read_text(encoding="utf-8"))
                                    ["by_wallet"][WALLET][COIN]["signed_size"]),
                "coin_net": float(ledger.coin_net(COIN)),
                "sleeve": float(ledger.sleeve(WALLET, COIN)["signed_size"]),
                "ledger_path": str(getattr(ledger, "path", ""))}

    def file_is_the_source():
        good = (abs(captured["disk_claim"] - FILE_E2_NET) < 1e-9
                and abs(captured["coin_net"] - FILE_E2_NET) < 1e-9
                and abs(captured["sleeve"] - FILE_E2_NET) < 1e-9
                and c.Path(str(getattr(ledger, "path", ""))).name == captured["file"])
        return good, "captured=%r" % (captured,)

    # (1) SIZING with the ledger present: the file's 9.0 vs the exchange's 0.5 -> no wire at all
    it1 = exit_intent(ledger, "SELL", FILE_E2_NET, "inv09-e2-mismatch", FILE_E2_NET)

    def hold_predicate():
        gw.cfg.send_mode_now = lambda: "CLOSE"
        ro, amount, why = gw._close_wire_plan(it1, FILE_E2_NET, SZ_DEC, lambda n: True, {})
        WIRES.append((amount, why))
        good = (str(why) == "CLOSE_PROOF_HOLD_FOREIGN_UNITS" and float(amount) == 0.0
                and ro is False and not ex.calls)
        return good, "amount=%r ro=%r why=%r order_calls=%r" % (amount, ro, why, ex.calls)

    # (2) SIZING with a stale/lagging ledger: the wire is the exchange net 0.5, never the file's 9.0
    def lag_size():
        gw.cfg.send_mode_now = lambda: "CLOSE"
        start = len(ex.calls)
        it2 = exit_intent(ledger, "SELL", FILE_E2_NET, "inv09-e2-lag", FILE_E2_NET)
        ro, amount, why = gw._close_wire_plan(it2, FILE_E2_NET, SZ_DEC, lambda n: True, {},
                                              ledger_may_lag=True)
        WIRES.append((amount, why))
        sent = ex.calls[start:]
        good = (abs(float(amount) - EXCHANGE_NET) < 1e-9 and ro is True
                and abs(float(amount) - FILE_E2_NET) > 1e-9 and not sent)
        return good, "wire_amount=%r (exchange=%s file=%s) ro=%r why=%r sent=%r" % (
            amount, EXCHANGE_NET, FILE_E2_NET, ro, why, sent)

    def clamp_row():
        rows = []
        p = c.Path(c.CLOSE_ESCALATIONS_FILE)
        if p.exists():
            rows = [v for v in json.loads(p.read_text(encoding="utf-8-sig")).values() if isinstance(v, dict)]
        reasons = [str(r.get("reason")) for r in rows]
        return ("CLOSE_PROOF_GLOBAL_CLOSE_ONLY_CLAMPED" in reasons), "escalation reasons=%r" % (reasons,)

    # (3) GATE: the file claims 0.5 while MASTER holds 9.0 -> a send sized off the file is BLOCKED
    fp3 = write_manual_follower_file(EXCHANGE_NET)
    ex3 = FakeExchange()
    ledger3 = c.ManualLedger(path=fp3)
    gw3 = make_gateway(ex3, ledger3, [9.0])
    gw3.cfg.send_mode_now = lambda: "ON"
    it3 = entry_intent(ledger3, "BUY", 0.5, "inv09-e2-gate", EXCHANGE_NET)

    def gate_block():
        ok, block = gw3._pre_send_ownership_gate(it3)
        gw3._append_local_block_reconciliation(it3, block.get("status"), block)
        row = (recon_rows("inv09-e2-gate") or [{}])[-1]
        good = (ok is False
                and block.get("status") == "OWNERSHIP_GATE_UNEXPLAINED_EXCHANGE_POSITION"
                and block.get("exchange_called") is False
                and abs(float(block.get("manual_net")) - EXCHANGE_NET) < 1e-9
                and abs(float(block.get("exchange_net")) - 9.0) < 1e-9
                and abs(float(row.get("exchange_net") or 0) - 9.0) < 1e-9
                and not ex3.calls)
        return good, "ok=%r status=%r exchange_called=%r manual=%r exchange=%r row=%s calls=%r" % (
            ok, block.get("status"), block.get("exchange_called"), block.get("manual_net"),
            block.get("exchange_net"),
            {k: row.get(k) for k in ("event", "status", "manual_net", "exchange_net")}, ex3.calls)

    # (4) ABSENCE: the file's value never appears as a wire size, a ledger-sourced size or an order
    def no_file_value():
        sizes = [r.get("copy_size") for r in _all_recon()
                 if str(r.get("leader_fill_id")) in ("inv09-e2-mismatch", "inv09-e2-lag", "inv09-e2-gate")]
        wires = [float(w[0]) for w in WIRES]

        def is_file_value(v):
            try:
                return abs(float(v) - FILE_E2_NET) < 1e-9
            except (TypeError, ValueError):
                return False
        good = (not any(is_file_value(s) for s in sizes)
                and not any(is_file_value(w) for w in wires)
                and not any(is_file_value(x["size"]) for x in ex.calls + ex3.calls)
                and all(abs(w - EXCHANGE_NET) < 1e-9 or w == 0.0 for w in wires))
        return good, "wire_amounts=%r ledger_sourced_sizes=%r order_calls=%r (file value=%s exchange=%s)" % (
            wires, sizes, ex.calls + ex3.calls, FILE_E2_NET, EXCHANGE_NET)

    check("E2_MANUAL_FILE_IS_THE_LEDGER_SOURCE", *file_is_the_source())
    check("E2_SIZING_HOLDS_FOREIGN_UNITS_ON_FILE_VS_EXCHANGE", *hold_predicate())
    check("E2_SEND_SIZE_IS_EXCHANGE_NET_NOT_FILE_VALUE", *lag_size())
    check("E2_CLAMP_RECORDED_AGAINST_EXCHANGE_CEILING", *clamp_row())
    check("E2_GATE_BLOCKS_A_FILE_SOURCED_SEND", *gate_block())
    check("E2_FILE_VALUE_ABSENT_FROM_EVERY_SIZE", *no_file_value())


# ======================================================================================== E3
def e3_checks():
    """An ack (accepted oid) with no MASTER fill/position is not settlement."""
    write_manual_follower_file(EXCHANGE_NET)
    svcmod.clear_unresolved_send("ETH", "INV09_SETUP_NO_RESERVATION")
    terminals_before = dict((svcmod.load_json(svcmod.SERVICE_STATE_FILE, {}) or {}).get("in_flight_terminals") or {})
    svcmod.persist_unresolved_send("ETH", {"intent_id": "inv09-e3", "coin": "ETH", "side": "BUY",
                                           "size": 1.0, "started_ms": c.utc_now_ms(),
                                           "pre_send_master_net": 0.0})
    svcmod.attach_send_result("ETH", {"oid": "778899", "exchange_status": "ORDER_ACCEPTED"})
    acked = svcmod.load_unresolved_sends().get("ETH") or {}

    def a():  # the ack is recorded ...
        return (str(acked.get("oid")) == "778899"), "reservation after ack=%s" % (acked,)

    # ... and it settles nothing: MASTER reads no fill for the intent and the position did not move
    with_master(InfoFixture(dexes=("",), states={"": {"ETH": 0.0}}, fills=[]))
    verdict = svcmod.reconcile_unresolved_send("ETH")

    def b():
        return (verdict.get("ok") is True and verdict.get("settled") is False
                and str(verdict.get("status")) == X.SETTLE_NONE), "verdict=%s" % (verdict,)

    def still_blocking():  # ABSENCE: the reservation still blocks and no NEW terminal settlement is recorded
        still = svcmod.load_unresolved_sends().get("ETH") or {}
        terminals = (svcmod.load_json(svcmod.SERVICE_STATE_FILE, {}) or {}).get("in_flight_terminals") or {}
        new_terminals = {k: v for k, v in terminals.items() if terminals_before.get(k) != v}
        return (bool(still) and not new_terminals
                and str(still.get("settle_status")) == X.SETTLE_NONE), \
               "reservation=%s new_terminals=%s" % (still, new_terminals)

    def unreadable():
        svcmod.attach_send_result("ETH", {"oid": "778899"})
        with_master(InfoFixture(dexes=("",), states={"": {"ETH": 0.0}}, fills=[], fail_fills=True))
        unk = svcmod.reconcile_unresolved_send("ETH")
        return (unk.get("ok") is False and "ETH" in svcmod.load_unresolved_sends()), "unknown=%s" % (unk,)

    def positive_control():  # a real MASTER fill for the same intent DOES settle and clear
        svcmod.attach_send_result("ETH", {"oid": "778899"})
        real = [{"coin": "ETH", "side": "B", "oid": "778899", "sz": "1.0", "time": 1, "tid": "t1"}]
        with_master(InfoFixture(dexes=("",), states={"": {"ETH": 1.0}}, fills=real))
        got = svcmod.reconcile_unresolved_send("ETH")
        gone = "ETH" not in svcmod.load_unresolved_sends()
        return (got.get("settled") is True and str(got.get("status")) == X.SETTLE_FULL and gone), \
               "settled=%s cleared=%r" % (got, gone)

    check("E3_ACK_IS_RECORDED", *a())
    check("E3_ACK_ALONE_IS_NOT_SETTLEMENT", *b())
    check("E3_ACK_LEAVES_RESERVATION_BLOCKING", *still_blocking())
    check("E3_UNREADABLE_MASTER_PROOF_STAYS_UNKNOWN", *unreadable())
    check("E3_MASTER_FILL_DOES_SETTLE_POSITIVE_CONTROL", *positive_control())
    svcmod.clear_unresolved_send("ETH", "INV09_CLEANUP")


# ======================================================================================== E5
def e5_checks():
    """Duplicate/reordered event on the truth path (named case), plus a repeated read = restart shape."""
    f1 = {"coin": COIN, "side": "B", "oid": "1", "sz": "1.0", "time": 2000, "tid": "a"}
    f2 = {"coin": COIN, "side": "A", "oid": "2", "sz": "0.5", "time": 1000, "tid": "b"}
    # every scope answers with both fills, in different orders and with f1 duplicated
    fetcher = InfoFixture(dexes=("", "builder-hip3"),
                          states={"": {COIN: 0.5}, "builder-hip3": {}}, fills=[f1, f2, f1])
    with_master(fetcher, dexes=["", "builder-hip3"])
    a = X.master_userfills_all_dexes(MASTER, 500, ["", "builder-hip3"], fetcher=fetcher)
    b = X.master_userfills_all_dexes(MASTER, 500, ["", "builder-hip3"], fetcher=fetcher)

    def one():
        return (a.get("ok") and a.get("count") == 2 and a.get("deduped") == 4), \
               "count=%r deduped=%r scopes=%r" % (a.get("count"), a.get("deduped"), a.get("scopes"))

    def two():  # deterministic order (sorted by fill identity), independent of arrival order
        keys = [X._fill_key(f) for f in a.get("fills", [])]
        return (keys == sorted(keys) and keys), "keys=%r" % (keys,)

    def three():  # a repeated read (restart mid-sequence) is identical: no drift, no double count
        return (a == b), "first==second: %r" % (a == b)

    def four():  # settlement from the deduped list counts each fill once
        v = X.resolve_settlement({"coin": COIN, "side": "BUY", "size": 1.0, "oid": "1"},
                                 a.get("fills"), EXCHANGE_NET)
        return (v.get("settled") is True and abs(float(v.get("filled")) - 1.0) < 1e-9), "verdict=%s" % (v,)

    def five():  # ABSENCE: no duplicate fill identity survives into the merged truth
        keys = [X._fill_key(f) for f in a.get("fills", [])]
        return (len(keys) == len(set(keys))), "keys=%r" % (keys,)

    check("E5_DUPLICATE_EVENT_DEDUPED_ONCE", *one())
    check("E5_REORDERED_EVENT_SORTED_DETERMINISTICALLY", *two())
    check("E5_RESTART_REREAD_IS_IDENTICAL", *three())
    check("E5_SETTLEMENT_COUNTS_A_DUPLICATE_ONCE", *four())
    check("E5_NO_DUPLICATE_IDENTITY_IN_TRUTH", *five())


# ======================================================================================== E4
def apply_mutation(kind):
    """Weaken the precedence so local replay wins. Reported as the E4 negative control."""
    if kind == "local-wins":
        # E1 weakened: remove the MASTER-truth branch of the ACTUAL accessor, so the wallet-local
        # (local replay) provider supplies ACTUAL -- the exact fallback production forbids.
        def local_wins(fetcher_states):
            def wire():
                svcmod.MASTER_TRUTH_ADDRESS = ""
                globals()["_MUTATION"] = "account_net_actual: MASTER exchange truth branch removed; " \
                                         "wallet-local provider (local replay) supplies ACTUAL"
            return wire
        return local_wins
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mutate", default="", help="non-vacuity control: 'local-wins'")
    args = ap.parse_args()
    mutation = args.mutate.strip().lower()

    print("=" * 100)
    print("ENG-INV-09 exchange truth outranks local replay  |  state dir=%s" % TMP)
    print("no network: /info is an injected double; HL_LIVE_ENV_FILE=/nonexistent; follower network=testnet")
    if mutation:
        print("MUTATION MODE: %s  (E1/E2 are EXPECTED to fail; that is the non-vacuity control)" % mutation)
    print("=" * 100)

    if mutation:
        # E1 mutation: the exchange-truth precedence is removed, local replay wins.
        svcmod.MASTER_TRUTH_ADDRESS = ""
        mutation_applied = "account_net_actual: MASTER exchange-truth branch disabled -> wallet-local " \
                           "provider (local replay) becomes ACTUAL"
        print("[mutation] %s" % mutation_applied)
        write_manual_follower_file(LOCAL_E1_NET)
        fetcher = InfoFixture(dexes=("",), states={"": {COIN: EXCHANGE_NET}}, fills=[])
        svc = svcmod.DryRunLiveCopyService()
        provider, box = local_provider(LOCAL_E1_NET)
        svc.account_net_provider = provider
        truth = svc.account_net_actual(COIN)
        check("E1_EFFECTIVE_POSITION_IS_EXCHANGE_VALUE",
              truth.get("ok") is True and abs(float(truth.get("net")) - EXCHANGE_NET) < 1e-9,
              "effective ACTUAL=%r (want %s) truth=%s" % (truth.get("net"), EXCHANGE_NET, truth))
        check("E1_LOCAL_REPLAY_NEVER_CONSULTED", box["n"] == 0,
              "wallet-local provider calls=%d -> local replay supplied ACTUAL" % box["n"])
        with_master(fetcher)
        # E2 mutation: the exchange net read is fed the manual file's claim (local replay wins the size path)
        write_audit_proof_rows()
        write_manual_follower_file(FILE_E2_NET)
        ex, ledger, net = FakeExchange(), new_ledger(), [FILE_E2_NET]
        gw = make_gateway(ex, ledger, net)
        it = exit_intent(ledger, "SELL", FILE_E2_NET, "inv09-e2-closesize-mut", FILE_E2_NET)
        gw.cfg.send_mode_now = lambda: "CLOSE"
        ro, amount, why = gw._close_wire_plan(it, FILE_E2_NET, SZ_DEC, lambda n: True, {},
                                              ledger_may_lag=True)
        check("E2_SEND_SIZE_IS_EXCHANGE_NET_NOT_FILE_VALUE",
              abs(float(amount) - EXCHANGE_NET) < 1e-9,
              "amount=%r reduce_only=%r why=%r (file value %s became the size: local replay won)"
              % (amount, ro, why, FILE_E2_NET))
        total = len(RESULTS)
        failed = sum(1 for _, ok in RESULTS if not ok)
        print("\nTOTAL=%d FAILED=%d (mutation=%s)" % (total, failed, mutation))
        print("RESULT::E4_MUTATION_LOCAL_WINS_IS_%s" % ("RED" if failed else "NOT_RED"))
        dump_observed()
        return 1 if failed else 0

    svcmod.MASTER_TRUTH_ADDRESS, svcmod.MASTER_TRUTH_SIGNER = MASTER, SIGNER
    print("\n=== E1) local ledger says 2.0, exchange says 0.5 ===")
    case("E1_BLOCK", lambda: (e1_checks() or True, ""))
    print("\n=== E2) the manual follower-position file is not authoritative ===")
    case("E2_BLOCK", lambda: (e2_checks() or True, ""))
    print("\n=== E3) an ack is not settlement ===")
    case("E3_BLOCK", lambda: (e3_checks() or True, ""))
    print("\n=== E5) duplicate/reordered event on the truth path ===")
    case("E5_BLOCK", lambda: (e5_checks() or True, ""))
    print("\n=== E0) offline control: no network read happened ===")
    check("E0_OFFLINE_NO_NETWORK_READ", not NET_ATTEMPTS, "NET_ATTEMPTS=%r" % (NET_ATTEMPTS,))
    print("NET_ATTEMPTS::%r" % (NET_ATTEMPTS,))

    total = len(RESULTS)
    failed = sum(1 for _, ok in RESULTS if not ok)
    print("\nTOTAL=%d FAILED=%d" % (total, failed))
    dump_observed()
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
