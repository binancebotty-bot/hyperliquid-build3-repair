"""G3 acceptance evidence: EXCHANGE_TRUTH_RECOVERY_SETTLEMENT (ruling B3-A2C-G2-PASS-G3-1).

Offline fixtures only (injected `fetcher` doubles). No live sending. Proves items A-N.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["HL_LIVE_AUDIT_DIR"] = tempfile.mkdtemp(prefix="g3_")  # never the live state folder
import exchange_truth as X  # noqa: E402
import HL_Live_Copy_Service as svcmod  # noqa: E402
svcmod.TEST_INJECTION_ENABLED = True  # test-only seam: injected providers/durability bypass

MASTER = "0x" + "a" * 40
SIGNER = "0x" + "b" * 40
_p = _f = 0


def check(name, ok, detail=""):
    global _p, _f
    if ok:
        _p += 1
        print(f"  PASS: {name}")
    else:
        _f += 1
        print(f"  FAIL: {name}  ::  {detail}")


class Fixture:
    """Offline /info double: perpDexs + per-dex clearinghouseState + userFillsByTime."""

    def __init__(self, dexes=("",), states=None, fills=None, fail_scopes=(), fail_dex_enum=False, fail_fills=False):
        self.dexes, self.states, self.fills = list(dexes), states or {}, list(fills or [])
        self.fail_scopes, self.fail_dex_enum, self.fail_fills = set(fail_scopes), fail_dex_enum, fail_fills
        self.calls = []

    def __call__(self, payload):
        self.calls.append(dict(payload))
        kind = payload.get("type")
        if kind == "perpDexs":
            if self.fail_dex_enum:
                raise RuntimeError("dex enumeration unavailable")
            return [{"name": d} for d in self.dexes if d]
        if kind == "clearinghouseState":
            dex = payload.get("dex", "")
            if dex in self.fail_scopes:
                raise RuntimeError(f"scope {dex} unavailable")
            return {"assetPositions": [{"position": {"coin": c, "szi": str(s)}} for c, s in self.states.get(dex, {}).items()]}
        if kind == "userFillsByTime":
            if self.fail_fills:
                raise RuntimeError("userFillsByTime unavailable")
            return list(self.fills)
        raise RuntimeError(f"unexpected payload {payload}")


def fresh(tmp, provider=None):
    (tmp / "live_config.json").write_text(json.dumps({"wallets": {
        "0xw1": {"mode": "LIVE", "enabled": True, "copy_mode": "proportional",
                 "norm_base": 100.0, "leader_equity_base": 1000.0}}}), encoding="utf-8")
    svcmod.configure_paths(tmp, tmp / "raw_live_fills.csv")
    svc = svcmod.DryRunLiveCopyService()
    svc.state["leader_event_positions"] = {}
    svc.processed_ids = set()
    if provider is not None:
        svc.account_net_provider = provider
    return svc


def with_master(fetcher, address=MASTER, signer=SIGNER, dexes=None):
    svcmod.MASTER_TRUTH_ADDRESS, svcmod.MASTER_TRUTH_SIGNER = address, signer
    svcmod.MASTER_TRUTH_FETCHER, svcmod.MASTER_TRUTH_DEXES = fetcher, dexes


def reset_master():
    svcmod.MASTER_TRUTH_ADDRESS, svcmod.MASTER_TRUTH_SIGNER = "", ""
    svcmod.MASTER_TRUTH_FETCHER, svcmod.MASTER_TRUTH_DEXES = None, None
    svcmod.UNATTRIBUTED_INVENTORY.clear()


def main():
    tmp = Path(tempfile.mkdtemp(prefix="g3_"))
    cfg = svcmod.LiveWalletConfig(wallet="0xw1", mode="LIVE", copy_mode="proportional",
                                  norm_base=100.0, leader_equity_base=1000.0, enabled=True)

    print("\n=== A) MASTER truth drives ACTUAL; signer state cannot ===")
    f = Fixture(dexes=("",), states={"": {"BTC": 1.0}})
    with_master(f)
    poisoned = {"called": 0}

    def poison(coin):
        poisoned["called"] += 1
        return {"ok": True, "net": 999.0, "source": "WALLET_LOCAL"}
    svc = fresh(tmp, provider=poison)
    truth = svc.account_net_actual("BTC")
    check("MASTER exchange truth supplies ACTUAL (1.0)", truth.get("ok") and abs(float(truth["net"]) - 1.0) < 1e-9, str(truth))
    check("wallet-local provider never consulted when MASTER truth is configured", poisoned["called"] == 0, str(poisoned))
    check("truth source is labelled MASTER_EXCHANGE_TRUTH", str(truth.get("source")) == "MASTER_EXCHANGE_TRUTH", str(truth))
    signer_f = Fixture(dexes=("",), states={"": {"BTC": -7.0}})
    with_master(signer_f, address=MASTER, signer=MASTER)   # signer == master -> invalid identities
    bad = svc.account_net_actual("BTC")
    check("signer == MASTER identity is rejected (fail closed)", not bad.get("ok") and bad.get("status") == X.IDENTITY_INVALID, str(bad))
    with_master(f)

    print("\n=== B) multi-DEX / HIP-3 aggregation; missing scope fails closed ===")
    multi = Fixture(dexes=("", "builder-hip3"), states={"": {"BTC": 1.0}, "builder-hip3": {"BTC": 0.5}})
    with_master(multi)
    agg = svcmod.DryRunLiveCopyService().account_net_actual("BTC")
    check("HIP-3/builder DEX scope aggregates into account-net", agg.get("ok") and abs(float(agg["net"]) - 1.5) < 1e-9, str(agg))
    check("both scopes are reported", len(agg.get("scopes") or []) == 2, str(agg.get("scopes")))
    broken = Fixture(dexes=("", "builder-hip3"), states={"": {"BTC": 1.0}, "builder-hip3": {"BTC": 0.5}}, fail_scopes=("builder-hip3",))
    with_master(broken)
    failclosed = svcmod.DryRunLiveCopyService().account_net_actual("BTC")
    check("unavailable required scope FAILS CLOSED (never assumes zero)",
          not failclosed.get("ok") and failclosed.get("status") == X.SCOPE_UNAVAILABLE, str(failclosed))
    noenum = Fixture(fail_dex_enum=True)
    with_master(noenum)
    ne = svcmod.DryRunLiveCopyService().account_net_actual("BTC")
    check("incomplete DEX enumeration FAILS CLOSED", not ne.get("ok") and ne.get("status") == X.DEX_ENUM_UNAVAILABLE, str(ne))

    print("\n=== C) snapshot/restart mints ZERO order authority ===")
    reset_master()
    snap = fresh(tmp, provider=lambda coin: {"ok": True, "net": 3.0, "source": "SNAPSHOT"})
    snap.state["snapshot_positions"] = {"0xw1::BTC": 3.0, "0xleader::BTC": 9.0}
    lineage_before = dict(snap.state.get("leader_event_positions") or {})
    desired = svcmod.event_authorised_desired_net("BTC", snap.leader_signed_by_wallet("BTC", snap.load_config()), snap.load_config())
    check("non-zero snapshot yields ZERO desired exposure", desired.get("ok") and abs(float(desired.get("desired_net") or 0.0)) < 1e-12, str(desired))
    check("snapshot does not mutate event lineage", dict(snap.state.get("leader_event_positions") or {}) == lineage_before, str(snap.state.get("leader_event_positions")))

    print("\n=== D) lineage checkpoint reload validity (G2 rules preserved) ===")
    ck = fresh(tmp)
    ck.state["leader_event_positions"] = {"0xw1::BTC": 1.0}
    ck.state["leader_event_checkpoint"] = {"coin": "BTC", "seq": 0, "last_fill_id": ""}
    check("checkpoint with no filled seq fails closed", ck._lineage_checkpoint_valid() is False, str(ck.state.get("leader_event_checkpoint")))
    ck.state["leader_event_checkpoint"] = {"coin": "BTC", "seq": 3, "last_fill_id": "evt-1"}
    ck.processed_ids = {"evt-1"}
    check("valid checkpoint reloads (seq>0 and last id processed)", ck._lineage_checkpoint_valid() is True, str(ck.state.get("leader_event_checkpoint")))
    ck.processed_ids = set()
    check("stale checkpoint (id not processed) fails closed", ck._lineage_checkpoint_valid() is False, str(ck.state.get("leader_event_checkpoint")))
    ck.lineage_valid = ck._lineage_checkpoint_valid()
    check("invalid lineage gates account-net truth (fail closed)", ck.account_net_actual("BTC").get("status") == svcmod.LINEAGE_CHECKPOINT_INVALID, str(ck.account_net_actual("BTC")))

    print("\n=== E/F/G/H/I) settlement: ack != settlement; full/partial/unknown/reject ===")
    s2 = fresh(tmp)
    s2.mark_in_flight("BTC", {"intent_id": "I1", "started_ms": 1000, "size": 2.0, "side": "BUY", "oid": "77"})
    check("E) reservation present before any ack", bool(s2.in_flight.get("BTC")), str(s2.in_flight))
    with_master(Fixture(dexes=("",), states={"": {"BTC": 2.0}}, fills=[{"coin": "BTC", "side": "B", "oid": "77", "sz": "2.0"}]))
    full = s2.settle_from_master_evidence("I1", "BTC", "BUY", 2.0, oid="77", start_ms=1000)
    check("F) independent MASTER userFills + position settle the full fill and clear in-flight",
          full.get("settled") is True and s2.in_flight.get("BTC") is None and abs(float(full.get("position_after")) - 2.0) < 1e-9, str(full))
    s2.mark_in_flight("ETH", {"intent_id": "OTHER", "started_ms": 1000})
    s2.mark_in_flight("BTC", {"intent_id": "I2", "started_ms": 1000, "size": 2.0, "side": "BUY", "oid": "78"})
    with_master(Fixture(dexes=("",), states={"": {"BTC": 2.0}}, fills=[{"coin": "BTC", "side": "B", "oid": "78", "sz": "0.5"}]))
    part = s2.settle_from_master_evidence("I2", "BTC", "BUY", 2.0, oid="78", start_ms=1000)
    check("G) partial fill keeps the unresolved remainder BLOCKING",
          part.get("settled") is False and abs(float(part.get("remaining")) - 1.5) < 1e-9 and bool(s2.in_flight.get("BTC"))
          and s2.in_flight["BTC"].get("settle_status") == X.SETTLE_PARTIAL, str(part))
    check("F) another coin's reservation is untouched", bool(s2.in_flight.get("ETH")), str(list(s2.in_flight)))
    err = s2.settle_from_master_evidence("I2", "BTC", "BUY", 2.0, oid="78", start_ms=1000)
    check("H) unknown/ambiguous evidence keeps blocking", err.get("ok") is True and err.get("settled") is False, str(err))
    with_master(Fixture(dexes=("",), states={"": {"BTC": 1.5}}, fills=[], fail_fills=True))
    amb = s2.settle_from_master_evidence("I2", "BTC", "BUY", 2.0, oid="78", start_ms=1000)
    check("H) unreadable MASTER fill truth fails closed and keeps in-flight",
          amb.get("ok") is False and bool(s2.in_flight.get("BTC")), str(amb))
    with_master(Fixture(dexes=("",), states={"": {"BTC": 1.5}}, fills=[]))
    rej = s2.settle_from_master_evidence("I2", "BTC", "BUY", 2.0, oid="78", start_ms=1000,
                                         reject_evidence=X.terminal_reject_evidence("ORDER_REJECTED", oid_accepted=False, no_fill_proved=True))
    check("I) terminal exchange rejection + all-DEX no-fill proof clears with NO phantom fill",
          rej.get("settled") is True and rej.get("status") == X.SETTLE_REJECTED and rej.get("position_after") is None
          and s2.in_flight.get("BTC") is None, str(rej))
    s2.mark_in_flight("BTC", {"intent_id": "I4", "started_ms": 1000, "size": 2.0, "side": "BUY", "oid": "79"})
    weak = s2.settle_from_master_evidence("I4", "BTC", "BUY", 2.0, oid="79", start_ms=1000,
                                          reject_evidence={"terminal_reject": True, "no_fill_proved": False, "oid_accepted": True})
    check("I) a caller boolean / unproven no-fill can NEVER clear a reservation",
          weak.get("settled") is False and bool(s2.in_flight.get("BTC")), str(weak))
    s2.mark_in_flight("BTC", {"intent_id": "I3", "started_ms": 1000})
    notowner = s2.settle_from_master_evidence("WHO-ELSE", "BTC", "BUY", 1.0,
                                              reject_evidence=X.terminal_reject_evidence("ORDER_REJECTED", False, True))
    check("I) only the owning intent can clear a reservation", notowner.get("ok") is False and bool(s2.in_flight.get("BTC")), str(notowner))

    print("\n=== J/K) divergence surfaces; unrelated inventory preserved ===")
    with_master(Fixture(dexes=("",), states={"": {"BTC": 9.0}}))
    div = s2.account_net_actual("BTC")
    recon = X.reconcile_sleeve(desired_net=1.0, master_net=float(div["net"]), unattributed_net=7.0)
    check("J) divergence produces an explicit reconciliation blocker",
          recon.get("blocker") == "RECONCILIATION_DIVERGENCE" and abs(recon.get("divergence") - 1.0) < 1e-9, str(recon))
    ok_case = X.reconcile_sleeve(desired_net=2.0, master_net=2.5, unattributed_net=0.5)
    check("K) copied sleeve converges while unrelated inventory is preserved",
          ok_case.get("blocker") is None and abs(ok_case.get("sleeve_net") - 2.0) < 1e-9, str(ok_case))
    svcmod.UNATTRIBUTED_INVENTORY["BTC"] = 7.0
    net_k = s2.account_net_actual("BTC")
    check("K) unattributed inventory is excluded from sleeve ACTUAL", abs(float(net_k.get("net")) - 2.0) < 1e-9, str(net_k))
    svcmod.UNATTRIBUTED_INVENTORY.clear()

    print("\n=== M) G3 seam does not disturb G2 planner behaviour ===")
    reset_master()
    s3 = fresh(tmp, provider=lambda coin: {"ok": True, "net": 0.0, "source": "TEST"})
    s3.process_fill(svcmod.LeaderFill(fill_id="g3e1", wallet="0xw1", coin="BTC", side="BUY", price=100.0, size=10.0,
                                      signed_size_delta=10.0, timestamp_ms=1000, timestamp_iso="t", source="test",
                                      recording_method="t", raw={}), cfg)
    check("planner still converges on the injected ACTUAL", abs(float(s3.get_position("0xw1", "BTC")["signed_size"])) > 0, str(s3.get_position("0xw1", "BTC")))

    print("\n=== L) single physical order site ===")
    src = (Path(__file__).parent / "HL_Live_Copy_Service.py").read_text(encoding="utf-8", errors="replace")
    check("exactly one exchange.order() call site", src.count("exchange.order(") == 1, str(src.count("exchange.order(")))

    print("\n=== A2) production has NO account-net fallback; runtime identity separation ===")
    reset_master()
    svcmod.TEST_INJECTION_ENABLED = False
    svc_no_master = fresh(tmp, provider=lambda coin: {"ok": True, "net": 42.0, "source": "WALLET_LOCAL"})
    locked = svc_no_master.account_net_actual("BTC")
    check("A2) production with no MASTER identity FAILS CLOSED (no provider fallback)",
          not locked.get("ok") and locked.get("status") in {X.IDENTITY_INVALID, svcmod.ACCOUNT_NET_TRUTH_UNAVAILABLE}, str(locked))
    import os as _os
    ident = X.runtime_master_identity({"HL_LIVE_HL_ACCOUNT_ADDRESS": MASTER, "HL_LIVE_HL_SIGNER_ADDRESS": SIGNER})
    check("A2) runtime identity accepts distinct MASTER + signer", ident.get("ok") is True, str(ident))
    same = X.runtime_master_identity({"HL_LIVE_HL_ACCOUNT_ADDRESS": MASTER, "HL_LIVE_HL_SIGNER_ADDRESS": MASTER})
    check("A2) runtime identity rejects signer == MASTER", same.get("ok") is False, str(same))
    missing = X.runtime_master_identity({})
    check("A2) runtime identity rejects missing identity", missing.get("ok") is False, str(missing))
    svcmod.TEST_INJECTION_ENABLED = True

    print("\n=== B2/C2/D2) durable pre-send reservation + restart recovery ===")
    with_master(Fixture(dexes=("",), states={"": {"BTC": 0.0}}, fills=[]))
    fresh(tmp)   # ensure a clean state file
    ok_p = svcmod.persist_unresolved_send("BTC", {"intent_id": "R1", "coin": "BTC", "side": "BUY", "size": 2.0,
                                                  "reduce_only": False, "started_ms": 1000, "pre_send_master_net": 0.0, "oid": ""})
    on_disk = svcmod.load_unresolved_sends()
    check("B2) reservation is DURABLE on disk before any sender boundary", ok_p and "BTC" in on_disk, str(on_disk))
    restarted = svcmod.DryRunLiveCopyService()
    check("B2) restart reloads the unresolved reservation as blocking (no second authorisation)",
          bool(restarted.in_flight.get("BTC")) and restarted.in_flight["BTC"].get("intent_id") == "R1", str(restarted.in_flight))
    svcmod.attach_send_result("BTC", {"oid": "4242", "exchange_status": "ORDER_FILLED"})
    still = svcmod.load_unresolved_sends().get("BTC") or {}
    check("D2) an ack/oid is attached but NEVER clears the reservation",
          still.get("oid") == "4242" and still.get("intent_id") == "R1", str(still))
    with_master(Fixture(dexes=("",), states={"": {"BTC": 2.0}}, fills=[{"coin": "BTC", "side": "B", "oid": "4242", "sz": "2.0", "time": 1005}]))
    res_res = svcmod.reconcile_unresolved_send("BTC")
    check("C2) crash-before/after-oid resolves from per-DEX MASTER evidence WITHOUT any resend",
          res_res.get("settled") is True and "BTC" not in svcmod.load_unresolved_sends(), str(res_res))

    print("\n=== E2) HIP-3 / multi-DEX settlement scoping + deterministic dedupe ===")
    calls = []

    def dex_fetcher(payload):
        calls.append(payload)
        if payload.get("type") == "perpDexs":
            return [{"name": "builder-hip3"}]
        if payload.get("type") == "clearinghouseState":
            return {"assetPositions": [{"position": {"coin": "BTC", "szi": "1.0"}}]}
        if payload.get("type") == "userFillsByTime":
            return [{"coin": "BTC", "side": "B", "oid": "9", "sz": "1.0", "time": 2000}]   # same fill in both scopes
        raise RuntimeError(payload)
    with_master(dex_fetcher, dexes=None)
    allf = X.master_userfills_all_dexes(MASTER, 1500, ["", "builder-hip3"], fetcher=dex_fetcher)
    # default perp DEX has no name => unqualified query; HIP-3 scope carries its explicit dex field
    sent_dex = [c.get("dex") for c in calls if c.get("type") == "userFillsByTime"]
    check("E2) userFillsByTime is queried once per scope (unqualified default + explicit HIP-3 dex)",
          allf.get("ok") and sent_dex == [None, "builder-hip3"], str(sent_dex))
    check("E2) each scope's fills are attributed to the scope they were read from",
          [s.get("dex") for s in allf.get("scopes", [])] == ["(default)", "builder-hip3"],
          str(allf.get("scopes")))
    check("E2) duplicate fills across scopes are deduplicated deterministically",
          allf.get("deduped") == 1 and len(allf.get("fills")) == 1, str(allf.get("deduped")))
    bad_fills = Fixture(dexes=("", "builder-hip3"), states={"": {"BTC": 1.0}}, fills=[], fail_fills=True)
    with_master(bad_fills, dexes=None)
    svcmod.persist_unresolved_send("BTC", {"intent_id": "E2", "coin": "BTC", "side": "BUY", "size": 1.0, "started_ms": 1000})
    unk = svcmod.reconcile_unresolved_send("BTC")
    check("E2) an unreadable required scope keeps the reservation BLOCKING",
          unk.get("ok") is False and "BTC" in svcmod.load_unresolved_sends(), str(unk))
    svcmod.clear_unresolved_send("BTC", "TEST_CLEANUP")

    print("\n=== H2/I2/J2) ownership baseline persists; divergence blocks before send ===")
    with_master(Fixture(dexes=("",), states={"": {"BTC": 9.0}}, fills=[]))
    base_svc = fresh(tmp)
    frozen = base_svc.freeze_unattributed_baseline("BTC", 9.0)
    check("H2) NO-SEND boundary freezes UNATTRIBUTED_BASELINE in the existing state file",
          frozen.get("ok") and base_svc.state["unattributed_baseline"]["BTC"] == 9.0, str(frozen))
    revived = svcmod.DryRunLiveCopyService()
    check("H2) restart preserves the frozen baseline (attribution, not authority)",
          revived.unattributed_baseline("BTC") == 9.0, str(revived.state.get("unattributed_baseline")))
    gate_ok = revived.reconcile_gate("BTC", 9.0)
    check("H2) matching MASTER truth passes the reconciliation gate", gate_ok.get("ok") is True, str(gate_ok))
    with_master(Fixture(dexes=("",), states={"": {"BTC": 12.0}}, fills=[]))
    gate_bad = revived.reconcile_gate("BTC", 12.0)
    check("I2) external/manual same-coin change produces RECONCILIATION_DIVERGENCE", gate_bad.get("ok") is False
          and gate_bad.get("status") == "RECONCILIATION_DIVERGENCE", str(gate_bad))
    gate_blocked = revived.convergence_notional_for_fill(
        cfg, svcmod.LeaderFill(fill_id="gate1", wallet="0xw1", coin="BTC", side="BUY", price=100.0, size=1.0,
                              signed_size_delta=1.0, timestamp_ms=1, timestamp_iso="t", source="test",
                              recording_method="t", raw={}))
    check("I2) divergence blocks the PRODUCTION order-authority path before any send",
          gate_blocked.get("ok") is False and gate_blocked.get("status") == "RECONCILIATION_DIVERGENCE", str(gate_blocked))
    check("J2) unrelated inventory is preserved (baseline excluded from sleeve ACTUAL)",
          abs(float(revived.account_net_actual("BTC").get("net")) - 3.0) < 1e-9,
          str(revived.account_net_actual("BTC")))

    print("\n=== L2) order-site invariant after the correction ===")
    src2 = (Path(__file__).parent / "HL_Live_Copy_Service.py").read_text(encoding="utf-8", errors="replace")
    check("L2) exactly one physical exchange.order() site still", src2.count("exchange.order(") == 1, str(src2.count("exchange.order(")))

    print("\n=== CL) durable in-flight checkpoint is never clobbered by persist() ===")
    tmpc = Path(tempfile.mkdtemp(prefix="g3_clob_"))
    svcmod.configure_paths(tmpc, tmpc / "raw_live_fills.csv")
    svc_c = svcmod.DryRunLiveCopyService()  # constructed BEFORE the send -> stale self.state
    svcmod.persist_unresolved_send("BTC", {"intent_id": "CL1", "coin": "BTC", "side": "BUY",
                                           "size": 1.5, "started_ms": 4242, "pre_send_master_net": 0.0})
    _before = svcmod.load_unresolved_sends().get("BTC") or {}
    svc_c.persist()                        # a routine persist must NOT erase the durable blocker
    _after = svcmod.load_unresolved_sends().get("BTC") or {}
    check("CL) durable in-flight reservation survives persist() (no clobber)",
          _before.get("intent_id") == "CL1" and _after.get("intent_id") == "CL1",
          "before=%s after=%s" % (_before, _after))
    print(f"\n  checks: {_p} passed, {_f} failed")
    if _f == 0:
        for tag in ("G3_MASTER_TRUTH_ACTUAL_PASS", "G3_SIGNER_NOT_TRUTH_PASS", "G3_MULTIDEX_HIP3_AGGREGATE_PASS",
                    "G3_SCOPE_UNAVAILABLE_FAIL_CLOSED_PASS", "G3_SNAPSHOT_ZERO_AUTHORITY_PASS",
                    "G3_LINEAGE_CHECKPOINT_RULES_PASS", "G3_ACK_NOT_SETTLEMENT_PASS",
                    "G3_FULL_SETTLEMENT_CLEARS_OWN_INTENT_PASS", "G3_PARTIAL_KEEPS_BLOCKING_PASS",
                    "G3_UNKNOWN_KEEPS_BLOCKING_PASS", "G3_TERMINAL_REJECT_NO_PHANTOM_PASS",
                    "G3_DIVERGENCE_BLOCKER_PASS", "G3_UNRELATED_INVENTORY_PRESERVED_PASS",
                    "G3_SINGLE_ORDER_SITE_PASS", "G3_DURABLE_IN_FLIGHT_NOT_CLOBBERED_PASS"):
            print(f"RESULT::{tag}")
    else:
        print("RESULT::G3_EXCHANGE_TRUTH_TESTS_FAIL")
    return 1 if _f else 0


if __name__ == "__main__":
    sys.exit(main())
