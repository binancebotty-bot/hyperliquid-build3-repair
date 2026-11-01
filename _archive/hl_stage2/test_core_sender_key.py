#!/usr/bin/env python3
"""The signing key must be valid on the FOLLOWER network (testnet run 3, 2026-10-09: the engine loaded the mainnet
agent key and the testnet exchange answered "User or API Wallet ... does not exist"; the engine filed that clear
rejection as ORDER_UNKNOWN / SEND_OUTCOME_REVIEW_REQUIRED).

K1 that reply is a definite rejection with its own category and terminal state, shown as a Critical diff.
K2 a top-level {"status": "err"} reply is ORDER_REJECTED, never ORDER_UNKNOWN.
K3 the first such rejection stops ALL sending (entries and exits) with one red row; later trades are recorded, not sent.
K4 the live screen shows a red ENGINE ALERT in plain words; the cycle gate says why entries stopped.
K5 at start the key's public address is looked up on the follower network (userRole): only the account itself or an
   agent it approved passes; the engine refuses to start otherwise. Key values are never printed or stored.

Run: python test_core_sender_key.py   # RESULT:: markers, exit 0/1. No network, no orders, no real key.
"""
from __future__ import annotations

import io
import json
import os
os.environ["HL_LIVE_GATES_ALERT_ONLY"] = "0"  # this test pins the legacy blocking gates; alert-only has its own test file
os.environ["HL_LIVE_DEFER_MAX_SEC"] = "300"  # legacy bounded hold
import sys
import tempfile
import time
from contextlib import redirect_stderr
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
RESULTS = []
FOLLOWER = "0x" + "c" * 40
LEADER = "0x" + "d" * 40
SIGNER = "0x" + "f" * 40
FAKE_KEY = "0x" + "1" * 64   # placeholder; never a real key, never signs
REJECT = {"status": "err", "response": f"User or API Wallet {SIGNER} does not exist."}


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


def wait_for_json_file(path: Path, timeout: float = 2.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with path.open("r", encoding="utf-8") as f:
                json.load(f)
            return True
        except (OSError, ValueError):
            time.sleep(0.01)
    return False


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="senderkey_"))
    os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LEADER_NETWORK": "mainnet", "HL_FOLLOWER_NETWORK": "testnet",
                       "HL_LIVE_ENV_FILE": str(tmp / "none.env"), "HL_LIVE_SCOPE_SWEEP_THREAD": "0",
                       "HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS": "0"})
    for k in ("HL_LIVE_HL_PRIVATE_KEY", "HL_LIVE_HL_ACCOUNT_ADDRESS"):
        os.environ.pop(k, None)
    import requests
    import HL_Live_Copy_Service_Core as c
    # C7-WO-1-R95 lease: the sender refuses unless the engine already owns the machine-
    # wide lease. Acquire it as the real engine does at start, in an ISOLATED temp lock
    # path so the live machine lock is never opened.
    import tempfile as _tf, pathlib as _pl
    _lockdir = _pl.Path(_tf.mkdtemp(prefix='r95lock_'))
    os.environ['HL_LIVE_GLOBAL_LOCK_FILE'] = str(_lockdir / 'engine-global.lock')
    c.acquire_global_instance_lock(_lockdir / 'state')
    import HL_Copy_App_SSOT as ui

    def offline(*a, **k):
        raise RuntimeError("offline test: no network")
    requests.post = offline
    c.requests.post = offline
    c.USER_WALLET = FOLLOWER
    c.MIDS_FETCHER = lambda p: [] if p.get("type") == "perpDexs" else {"BTC": "100"}
    c.LEADER_MIDS_FETCHER = lambda p: [] if p.get("type") == "perpDexs" else {"BTC": "100"}

    # ---- K1 / K2 ---------------------------------------------------------------------------------------
    cat = c.classify_reject_category(REJECT["response"], REJECT)
    check("K1_SIGNER_UNKNOWN_HAS_ITS_OWN_CATEGORY", cat == "SENDER_KEY_NOT_VALID", cat)
    for lc in ("ENTRY", "ADD", "REDUCE", "EXIT"):
        t = c.classify_terminal_state("ORDER_REJECTED", cat, lc, True)
        check(f"K1_{lc}_TERMINAL_NOT_REVIEW_UNKNOWN", t == "SENDER_KEY_NOT_VALID_ON_FOLLOWER_NETWORK", t)
    act = c.classify_operator_action("ORDER_REJECTED", cat, "ENTRY", True)
    check("K1_CRITICAL_ON_SCREEN", "MANUAL_REVIEW" in act, act)
    check("K1_OTHER_REJECTS_UNCHANGED", c.classify_reject_category("Order could not immediately match against any resting orders")
          == "IOC_NO_IMMEDIATE_MATCH" and c.classify_reject_category("Insufficient margin to place order.") == "INSUFFICIENT_MARGIN")
    parsed = c.SenderGateway._parse_hl_response(REJECT)
    check("K2_TOP_LEVEL_ERR_IS_A_REJECT_NOT_UNKNOWN", parsed[:2] == (False, "ORDER_REJECTED") and "does not exist" in parsed[3], str(parsed))
    check("K2_UNPARSEABLE_STILL_UNKNOWN", c.SenderGateway._parse_hl_response({"status": "ok"})[1] == "ORDER_UNKNOWN")

    # ---- K3: first rejection stops all sending -------------------------------------------------------------
    class FakeExchange:
        def __init__(self):
            self.calls = []

        def update_leverage(self, leverage, name, is_cross=True):  # ENTRY/ADD fail closed without it
            return {"status": "ok"}
        def order(self, coin, is_buy, size, px, tif, reduce_only=False):
            self.calls.append({"px": px, "tif": tif["limit"]["tif"], "reduce_only": reduce_only})
            return REJECT

    resolved = {"ok": True, "sdk_coin": "BTC", "sz_decimals": 3, "price_max_decimals": 2, "perp_dexs": [""],
                "sdk_order_compatible": True, "min_order_value_usd": 1.0, "min_size": 0.0, "status": "OK"}
    c.atomic_write_json(c.LIVE_CONFIG_FILE, {"auto_send_enabled": True, "global_controls": {}, "wallets": {
        LEADER: {"enabled": True, "mode": "LIVE", "copy_mode": "fixed", "fixed_notional": 1000}}})
    fake = FakeExchange()
    led = c.ManualLedger(path=tmp / "k3.json")
    gw = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter(), led)
    gw._resolve_coin = lambda coin: dict(resolved)
    gw._get_exchange_client = lambda *a, **k: fake
    gw._exchange_client_has_symbol = lambda *a, **k: True
    gw._validate_final_wire_order = lambda *a, **k: (True, {})
    gw._pre_exchange_asset_safety = lambda *a, **k: (True, {})
    gw._pre_send_ownership_gate = lambda intent: (True, {})
    seq = [0]

    def fill(side="BUY"):
        seq[0] += 1
        return c.LeaderFill(f"k{seq[0]}", LEADER, "BTC", side, 100.0, 1.0, c.utc_now_ms(), "TEST")

    os.environ["HL_LIVE_HL_PRIVATE_KEY"] = FAKE_KEY
    saved = c.HLAccount, c.HLExchange
    c.HLAccount, c.HLExchange = object, object
    try:
        entry = c.IntentBuilder(c.ConfigManager(), led).build(fill())
        ok, status, res = gw._send_real(entry)
        check("K3_REJECT_RECORDED_AS_REJECT", not ok and status == "ORDER_REJECTED" and len(fake.calls) == 1, f"{status} {fake.calls}")
        check("K3_NO_IOC_RETRY_OR_LIMIT_AFTER_KEY_REJECT", len(fake.calls) == 1, str(fake.calls))
        check("K3_SENDING_STOPPED", bool(gw.sender_key_invalid) and "does not exist" in gw.sender_key_invalid)
        gw._append_real_attempt(entry, status, res)
        sends = c.read_csv_rows(c.SEND_ATTEMPTS_CSV)
        check("K3_SEND_ROW_TERMINAL_NOT_REVIEW_REQUIRED", sends[-1]["terminal_state"] == "SENDER_KEY_NOT_VALID_ON_FOLLOWER_NETWORK"
              and sends[-1]["status"] == "ORDER_REJECTED", str({k: sends[-1][k] for k in ("status", "terminal_state")}))
        red = [r for r in c.read_csv_rows(c.RECONCILIATION_CSV) if r["status"] == "SENDER_KEY_NOT_VALID_ON_FOLLOWER_NETWORK"]
        check("K3_ONE_RED_STOP_ROW_PLUS_THE_SEND_ROW", len(red) == 2 and all("MANUAL_REVIEW" in r["action"] for r in red), str(len(red)))
        led.sleeve(LEADER, "BTC")["signed_size"] = 1.0
        exit_intent = c.IntentBuilder(c.ConfigManager(), led).build(fill("SELL"))
        sent, st = gw.send_if_allowed(exit_intent)
        check("K3_EXITS_ALSO_STOPPED_NO_EXCHANGE_CALL", not sent and st == "SEND_BLOCKED_SENDER_KEY_NOT_VALID" and len(fake.calls) == 1, st)
        entry2 = c.IntentBuilder(c.ConfigManager(), c.ManualLedger(path=tmp / "k3b.json")).build(fill())
        entry2.decision = "ENTRY_ALLOWED"   # risk checks aside (offline here): the stop itself must refuse it
        sent, st = gw.send_if_allowed(entry2)
        check("K3_ENTRIES_STOPPED_NO_EXCHANGE_CALL", not sent and st == "SEND_BLOCKED_SENDER_KEY_NOT_VALID" and len(fake.calls) == 1, st)
    finally:
        c.HLAccount, c.HLExchange = saved
        os.environ.pop("HL_LIVE_HL_PRIVATE_KEY", None)

    # ---- K4: engine state, cycle gate, screen ---------------------------------------------------------------
    core = c.LiveCopyCore(source_csv=tmp / "none.csv")
    core.sender.sender_key_invalid = gw.sender_key_invalid
    f = fill()
    intent = core.intent_builder.build(f)
    core._append_send_terminal(f, intent, "SEND_BLOCKED_SENDER_KEY_NOT_VALID")
    rows = [r for r in c.read_csv_rows(c.RECONCILIATION_CSV) if r.get("leader_fill_id") == f.leader_fill_id]
    check("K4_MISSED_TRADE_RECORDED_AS_RED_DIFF", rows and rows[-1]["status"] == "SENDER_KEY_NOT_VALID_ON_FOLLOWER_NETWORK"
          and "MANUAL_REVIEW" in rows[-1]["action"], str(rows[-1:])[:200])
    core.run_cycle(use_source_csv=False)
    check("K4_CYCLE_GATE_SAYS_WHY", core._entry_sends_blocked_reason == "SENDER_KEY_NOT_VALID", core._entry_sends_blocked_reason)
    state_published = wait_for_json_file(c.SERVICE_STATE_FILE)
    check("K4_STATE_PUBLISHED_EVENTUALLY", state_published, str(c.SERVICE_STATE_FILE))
    state = c.load_json(c.SERVICE_STATE_FILE, {})
    check("K4_STATE_CARRIES_IT_FOR_THE_SCREEN", "does not exist" in str(state.get("sender_key_invalid"))
          and state.get("entry_sends_blocked_reason") == "SENDER_KEY_NOT_VALID", str({k: state.get(k) for k in ("sender_key_invalid", "entry_sends_blocked_reason")}))
    ui.LIVE_COPY_SERVICE_STATE_FILE = c.SERVICE_STATE_FILE
    alert = ui._engine_alert()
    check("K4_SCREEN_ALERT_IN_PLAIN_WORDS", alert.startswith("SENDING STOPPED: the testnet exchange rejected the engine's signing key")
          and "restart" in alert, alert)
    page = ui.render_live_copy_control_panel()
    check("K4_SCREEN_RENDERS_RED_ENGINE_ALERT_CARD", "statusCard('ENGINE ALERT'" in page and "lcAudit.engine_alert" in page)

    # ---- K5: start-up check --------------------------------------------------------------------------------
    class FakeAcct:
        @staticmethod
        def from_key(key):
            if key != FAKE_KEY:
                raise ValueError("bad key")
            return type("A", (), {"address": SIGNER})()

    role = {"reply": {"role": "missing"}}

    def role_fetch(payload):
        if role["reply"] is None:
            raise RuntimeError("info down")
        assert payload == {"type": "userRole", "user": SIGNER}, payload
        return role["reply"]
    c.SIGNER_ROLE_FETCHER = role_fetch
    saved_acct = c.HLAccount
    c.HLAccount = FakeAcct
    try:
        check("K5_NO_KEY_NOTHING_TO_CHECK", c.sender_key_check()["ok"] is True)
        os.environ["HL_LIVE_HL_PRIVATE_KEY"] = FAKE_KEY
        os.environ["HL_LIVE_HL_ACCOUNT_ADDRESS"] = FOLLOWER
        r = c.sender_key_check()
        check("K5_UNKNOWN_SIGNER_REFUSED", r["ok"] is False and "testnet" in r["detail"], str(r))
        check("K5_KEY_NEVER_IN_THE_MESSAGE", FAKE_KEY not in r["detail"] and FAKE_KEY[2:] not in r["detail"], r["detail"])
        role["reply"] = {"role": "agent", "data": {"user": FOLLOWER}}
        check("K5_AGENT_APPROVED_BY_ACCOUNT_PASSES", c.sender_key_check()["ok"] is True)
        role["reply"] = {"role": "agent", "data": {"user": "0x" + "9" * 40}}
        check("K5_AGENT_OF_ANOTHER_ACCOUNT_REFUSED", c.sender_key_check()["ok"] is False)
        role["reply"] = {"role": "user"}
        check("K5_SIGNER_IS_A_DIFFERENT_USER_REFUSED", c.sender_key_check()["ok"] is False)
        os.environ["HL_LIVE_HL_ACCOUNT_ADDRESS"] = SIGNER
        check("K5_SIGNER_IS_THE_ACCOUNT_PASSES", c.sender_key_check()["ok"] is True)
        os.environ["HL_LIVE_HL_ACCOUNT_ADDRESS"] = FOLLOWER
        role["reply"] = None
        check("K5_UNREADABLE_IS_UNKNOWN_NOT_PASS", c.sender_key_check()["ok"] is None)
        os.environ["HL_LIVE_HL_PRIVATE_KEY"] = "not-a-key"
        r = c.sender_key_check()
        check("K5_MALFORMED_KEY_REFUSED_WITHOUT_ECHO", r["ok"] is False and "not-a-key" not in r["detail"], str(r))
        os.environ["HL_LIVE_HL_PRIVATE_KEY"] = FAKE_KEY
        role["reply"] = {"role": "missing"}
        argv = sys.argv
        saved_locks = c.acquire_global_instance_lock, c.acquire_instance_lock
        c.acquire_global_instance_lock = c.acquire_instance_lock = lambda *a, **k: None
        sys.argv = ["HL_Live_Copy_Service_Core.py", "--once"]
        err = io.StringIO()
        try:
            with redirect_stderr(err):
                c.main()
            refused = ""
        except SystemExit as exc:
            refused = str(exc)
        finally:
            sys.argv = argv
            c.acquire_global_instance_lock, c.acquire_instance_lock = saved_locks
        check("K5_ENGINE_REFUSES_TO_START", refused.startswith("SENDER_KEY_NOT_VALID_ON_FOLLOWER_NETWORK")
              and FAKE_KEY[2:] not in refused, refused)
    finally:
        c.HLAccount = saved_acct
        for k in ("HL_LIVE_HL_PRIVATE_KEY", "HL_LIVE_HL_ACCOUNT_ADDRESS"):
            os.environ.pop(k, None)

    # ---- K6: publish the new process before startup reconciliation can wait --------------------------------
    startup_state_path = tmp / "startup_state.json"
    startup_state_path.write_text(json.dumps({"process_id": -1}), encoding="utf-8")

    class StartupConfig:
        def active_wallets(self):
            return []

    real_config_manager = c.ConfigManager
    startup_cfg = real_config_manager()
    orphan_result = {"ok": True, "detail": "offline test"}
    orphan_error = None
    startup_writer_error = None

    class StartupStateWriter:
        def __init__(self):
            self.writer = c.ServiceStateWriter()
            self.failed = False

        def write_startup(self, *args):
            if startup_writer_error and not self.failed:
                self.failed = True
                raise startup_writer_error
            self.writer.write_startup(*args)

    class StartupSender:
        def startup_orphan_order_check(self):
            state = c.load_json(startup_state_path, {})
            check("K6_STATUS_FRESH_BEFORE_STARTUP_RECONCILIATION", state.get("process_id") == os.getpid(), str(state))
            check("K6_STARTUP_STATUS_STAYS_BLOCKED", state.get("cycle") == "startup"
                  and state.get("entry_sends_blocked_reason") == "STARTUP_ORPHAN_CHECK_PENDING", str(state))
            if orphan_error:
                raise orphan_error
            return orphan_result

    class StartupCore:
        def __init__(self, source_csv=None):
            self.state_writer = StartupStateWriter()
            self.dedupe = c.DedupeStore({}, state_dir=tmp)
            self.cfg = startup_cfg
            self.sender = StartupSender()
            self.ws = object()
            self.wallets = []
            self.hot_send_workers = 0

        def run_cycle(self, **kwargs):
            summary = c.CycleSummary()
            self.state_writer.write_startup(summary, self.dedupe, self.cfg)
            return summary

        def stop(self):
            pass

    patch_names = ("SERVICE_STATE_FILE", "ConfigManager", "LiveCopyCore", "sender_key_check",
                   "acquire_global_instance_lock", "acquire_instance_lock", "install_core_attribution_hooks")
    saved_patch = {name: getattr(c, name) for name in patch_names}
    saved_claim, saved_refusal = c._XNET.claim_network_stamp, c._XNET.stamp_state_refusal
    saved_argv = sys.argv
    try:
        c.SERVICE_STATE_FILE = startup_state_path
        c.ConfigManager = StartupConfig
        c.LiveCopyCore = StartupCore
        c.sender_key_check = lambda: {"ok": True, "detail": "offline test"}
        c.acquire_global_instance_lock = lambda *a, **k: None
        c.acquire_instance_lock = lambda *a, **k: None
        c.install_core_attribution_hooks = lambda: None
        c._XNET.claim_network_stamp = lambda *a, **k: None
        c._XNET.stamp_state_refusal = lambda *a, **k: ""
        sys.argv = ["HL_Live_Copy_Service_Core.py", "--once"]
        with redirect_stderr(io.StringIO()):
            c.main()
        successful_state = c.load_json(startup_state_path, {})
        check("K6_SUCCESSFUL_CHECK_ADVANCES_STATUS", successful_state.get("cycle") == "run_cycle"
              and successful_state.get("entry_sends_blocked_reason") != "STARTUP_ORPHAN_CHECK_PENDING", str(successful_state))
        startup_writer_error = RuntimeError("offline writer failure")
        startup_state_path.write_text(json.dumps({"process_id": -1}), encoding="utf-8")
        try:
            with redirect_stderr(io.StringIO()):
                c.main()
            refused = ""
        except SystemExit as exc:
            refused = str(exc)
        except Exception as exc:
            refused = f"UNCAUGHT:{type(exc).__name__}:{exc}"
        failed_state = c.load_json(startup_state_path, {})
        check("K6_WRITER_FAILURE_IS_FATAL_STATUS", refused.startswith("STARTUP_ORPHAN_CHECK_WRITER_FAILED")
              and failed_state.get("ok") is False
              and failed_state.get("entry_sends_blocked_reason") == "STARTUP_ORPHAN_CHECK_WRITER_FAILED"
              and failed_state.get("fatal_errors") == 1 and failed_state.get("process_id") == os.getpid()
              and "offline writer failure" in failed_state.get("send_block_reason", "")
              and failed_state.get("entry_sends_blocked_reason") != "STARTUP_ORPHAN_CHECK_PENDING", str(failed_state))
        startup_writer_error = None
        orphan_result.update(ok=False, detail="offline refusal")
        sys.argv = ["HL_Live_Copy_Service_Core.py", "--once"]
        try:
            with redirect_stderr(io.StringIO()):
                c.main()
            refused = ""
        except SystemExit as exc:
            refused = str(exc)
        failed_state = c.load_json(startup_state_path, {})
        check("K6_FAILED_RECONCILIATION_IS_PUBLISHED", refused.startswith("STARTUP_ORPHAN_CHECK_FAILED")
              and failed_state.get("ok") is False
              and failed_state.get("entry_sends_blocked_reason") == "STARTUP_ORPHAN_CHECK_FAILED"
              and failed_state.get("fatal_errors") == 1, str(failed_state))
        orphan_result.update(ok=True)
        orphan_error = RuntimeError("offline exception")
        try:
            with redirect_stderr(io.StringIO()):
                c.main()
            refused = ""
        except SystemExit as exc:
            refused = str(exc)
        except RuntimeError as exc:
            refused = f"UNCAUGHT:{type(exc).__name__}"
        failed_state = c.load_json(startup_state_path, {})
        check("K6_EXCEPTION_RECONCILIATION_IS_PUBLISHED", refused.startswith("STARTUP_ORPHAN_CHECK_FAILED")
              and failed_state.get("ok") is False
              and failed_state.get("entry_sends_blocked_reason") == "STARTUP_ORPHAN_CHECK_FAILED"
              and failed_state.get("fatal_errors") == 1, str(failed_state))
    finally:
        sys.argv = saved_argv
        c._XNET.claim_network_stamp, c._XNET.stamp_state_refusal = saved_claim, saved_refusal
        for name, value in saved_patch.items():
            setattr(c, name, value)

    failed = [n for n, ok in RESULTS if not ok]
    print(f"TOTAL={len(RESULTS)} FAILED={len(failed)}")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
