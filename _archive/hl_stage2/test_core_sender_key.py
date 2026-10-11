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
import os
import sys
import tempfile
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


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="senderkey_"))
    os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LEADER_NETWORK": "mainnet", "HL_FOLLOWER_NETWORK": "testnet",
                       "HL_LIVE_ENV_FILE": str(tmp / "none.env"), "HL_LIVE_SCOPE_SWEEP_THREAD": "0",
                       "HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS": "0"})
    for k in ("HL_LIVE_HL_PRIVATE_KEY", "HL_LIVE_HL_ACCOUNT_ADDRESS"):
        os.environ.pop(k, None)
    import requests
    import HL_Live_Copy_Service_Core as c
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
        check("K5_ENGINE_REFUSES_TO_START", refused.startswith("SENDER_KEY_NOT_VALID_ON_FOLLOWER_NETWORK")
              and FAKE_KEY[2:] not in refused, refused)
    finally:
        c.HLAccount = saved_acct
        for k in ("HL_LIVE_HL_PRIVATE_KEY", "HL_LIVE_HL_ACCOUNT_ADDRESS"):
            os.environ.pop(k, None)

    failed = [n for n, ok in RESULTS if not ok]
    print(f"TOTAL={len(RESULTS)} FAILED={len(failed)}")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
