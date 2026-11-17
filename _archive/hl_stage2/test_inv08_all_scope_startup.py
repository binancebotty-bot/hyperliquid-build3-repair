#!/usr/bin/env python3
"""ENG-INV-08 (tier 1, ENGINE): startup/recovery truth includes ALL perp DEX scopes (default + HIP-3/builder),
and a missing required scope fails closed.

Requirement (certification/certification_matrix.json, id ENG-INV-08):
  "Startup/recovery truth includes all relevant perp DEX scopes (default + HIP-3/builder); missing required
   scope fails closed."

TEST-ONLY. No production byte is changed by this file and nothing in it writes engine state outside a temp dir.
OFFLINE: every /info read goes through an injected fetcher (EXPOSURE_FETCHER); requests.post is replaced with a
raiser and the harness asserts it was never called, so no network read of any network can happen here.

Sections
  S1  ALL SCOPES ON STARTUP/RECOVERY: the startup/recovery truth read enumerates the default DEX plus every
      HIP-3/builder DEX the account is known to hold, reads every one of them, and the published truth row
      carries all of them (engine sweep result + scope_sweep_state.json + follower_dex_scope + the
      exchange_truth truth rows master_account_net / master_exposure).
  S2  MISSING REQUIRED SCOPE FAILS CLOSED: with ONE required scope unreadable, the engine refuses the truth with
      a NAMED refusal and publishes NO green position truth - the assertion is the ABSENCE of green, not the
      presence of an error string (sweep status, no 'held', scope_sweep_state held_count 0, _scope_sweep_ok
      reset to None, the entry gate, and the truth read refusing with no net/scopes published).
  S3  NEGATIVE CONTROL (non-vacuity): a deliberately weakened COPY of the scope-enumeration predicate (source-
      level mutant M1 of exchange_truth.list_perp_dexes, builder scopes dropped) and a fail-OPEN copy of the
      truth read (mutant M2 of master_account_net, a missing scope skipped) each turn S1 / S2 RED. Both mutants
      are shown to be WORKING-but-weaker (they return a green truth), so the RED is content-driven, not a crash.
  S4  NEGATIVE TEST "restart mid-sequence": a sweep aborted mid-sequence leaves scopes unproven; a NEW process
      over the same state dir declares NO green startup truth, re-reads only the unproven scopes, and goes green
      only once every scope has a reading.

Run (from _archive/hl_stage2):
  HL_LIVE_ENV_FILE=/nonexistent python -u test_inv08_all_scope_startup.py
RESULT:: markers, TOTAL=n FAILED=m, exit 0/1.
"""
from __future__ import annotations

import os
import sys

# The scope gate must BLOCK here, not degrade to an alert row (Boss rule 16 Oct keeps an operator-set alert-only
# mode; this harness pins the strict gate so "fails closed" is asserted as a refusal, and reads the alert-only
# path separately where it matters).
os.environ["HL_LIVE_GATES_ALERT_ONLY"] = "0"

import json
import tempfile
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

RESULTS = []
FOLLOWER = "0x" + "c" * 40
LEADER = "0x" + "d" * 40
OFFLINE_INFO = "http://offline.invalid/info"   # never dialled: every read is an injected fetcher
HIP3 = ["flx", "io", "xyz"]                     # builder / HIP-3 DEXes the account holds (sorted order is the sweep's)
ALL_SCOPES = ["", "flx", "io", "xyz"]           # default DEX + every HIP-3 DEX = N scopes
# INV08_SELFMUTANT=M1|M2 installs a deliberately weakened copy of a production predicate as the LIVE one and runs
# only that section: the harness must then EXIT 1. That is the non-vacuity control with a real process code.
SELFMUTANT = (os.environ.get("INV08_SELFMUTANT") or "").strip().upper()


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + str(detail)[:400]) if (detail and not cond) else ""))


class FakeExchange:
    """The follower account as the exchange would show it, per perp DEX scope. No socket is ever opened."""

    def __init__(self) -> None:
        self.dexes = list(HIP3)         # perpDexs answer (the default DEX is implicit, list_perp_dexes prepends "")
        self.positions = {}             # dex -> [position dicts]
        self.dead = set()               # dex names whose clearinghouseState cannot be read (throttled / non-JSON body)
        self.enum_down = False          # perpDexs itself unavailable
        self.reads = []                 # every read, in order: ("perpDexs"|"clearinghouseState", dex)
        self.on_read = None             # hook(payload) after a successful state read (used by S4)
        self.lock = threading.Lock()

    def fetch(self, payload):
        ptype = payload.get("type")
        if ptype == "perpDexs":
            with self.lock:
                self.reads.append(("perpDexs", ""))
            if self.enum_down:
                raise RuntimeError("perpDexs unavailable (simulated throttled body)")
            return [{"name": d} for d in self.dexes]
        dex = payload.get("dex", "")
        with self.lock:
            self.reads.append(("clearinghouseState", dex))
        if dex in self.dead:
            raise ValueError("Expecting value: line 1 column 1 (char 0)")   # 429 / non-JSON answer
        out = {"assetPositions": [{"position": p} for p in self.positions.get(dex, [])],
               "marginSummary": {"accountValue": "1000"}}
        hook = self.on_read
        if hook is not None:
            hook(payload)
        return out

    def state_reads(self):
        with self.lock:
            return [d for t, d in self.reads if t == "clearinghouseState"]

    def clear_reads(self):
        with self.lock:
            self.reads.clear()


def _account_book() -> dict:
    """One position on the default DEX and one on each builder DEX: every scope carries truth."""
    return {
        "": [{"coin": "GOLD", "szi": "1.0", "positionValue": "2500"}],
        "flx": [{"coin": "flx:FOO", "szi": "3.0", "positionValue": "30"}],
        "io": [{"coin": "io:BAR", "szi": "4.0", "positionValue": "40"}],
        "xyz": [{"coin": "xyz:AMD", "szi": "2.0", "positionValue": "100"}],
    }


def _extract_func(path: Path, func: str) -> str:
    """The exact source of one production function, for a source-level mutation (no hand-copied predicate)."""
    lines = path.read_text(encoding="utf-8").splitlines()
    start = next(i for i, l in enumerate(lines) if l.startswith("def %s(" % func))
    end = next((i for i in range(start + 1, len(lines))
                if lines[i].startswith("def ") or lines[i].startswith("class ")), len(lines))
    return "\n".join(lines[start:end])


def run_self_mutant(kind: str, X, fx: "FakeExchange", core) -> None:
    """Non-vacuity with a REAL failing exit code: install the mutant as the LIVE predicate, then run the same
    S1 / S2 assertions. Used by INV08_SELFMUTANT=M1|M2 so the RED of the harness is a process exit 1, not only
    an in-process False. Nothing here is written to production: only the module attribute of this process."""
    src_path = Path(X.__file__)
    if kind == "M1":
        src = _extract_func(src_path, "list_perp_dexes")
        drop = '            names.append(str(name).strip())'
        if drop not in src:
            check("MUT_M1_MUTATION_APPLIED", False, "mutation anchor not found in list_perp_dexes")
            return
        ns = dict(vars(X))
        exec(compile(src.replace(drop, '            pass  # MUTANT M1: builder/HIP-3 scope dropped'),
                     "<mutant M1 list_perp_dexes>", "exec"), ns)
        X.list_perp_dexes = ns["list_perp_dexes"]
        print("RED_QUOTE::SELF_M1 the LIVE scope-enumeration predicate is the mutant (builder scopes dropped)")
        fx.clear_reads()
        res = core.run_scope_sweep()
        check("MUT_M1_S1_SWEEP_READS_EVERY_BUILDER_SCOPE",
              res.get("ok") is True and sorted(fx.state_reads()) == sorted(HIP3),
              f"reads={sorted(fx.state_reads())} res={str(res)[:200]}")
        for name, ok, detail in s1_truth_read_checks(fx, X):
            check("MUT_M1_" + name[3:], ok, detail)
    elif kind == "M2":
        src = _extract_func(src_path, "master_account_net")
        fail = ('        if not isinstance(state, dict) or not isinstance(state.get("assetPositions"), list):\n'
                '            return {"ok": False, "status": SCOPE_UNAVAILABLE, "dex": dex, "detail": res.get("detail", "no assetPositions")}')
        if fail not in src:
            check("MUT_M2_MUTATION_APPLIED", False, "mutation anchor not found in master_account_net")
            return
        ns = dict(vars(X))
        exec(compile(src.replace(fail, '        if not isinstance(state, dict) or not isinstance(state.get("assetPositions"), list):\n'
                                       '            continue  # MUTANT M2: a missing scope is skipped'),
                     "<mutant M2 master_account_net>", "exec"), ns)
        X.master_account_net = ns["master_account_net"]
        print("RED_QUOTE::SELF_M2 the LIVE truth read is the fail-open mutant (a missing scope is skipped)")
        fx.dexes = HIP3 + ["qqq"]
        fx.positions["qqq"] = [{"coin": "qqq:NEW", "szi": "5.0", "positionValue": "50"}]
        fx.dead = {"qqq"}
        name, ok, detail = s2_truth_read_check(fx, X)
        check("MUT_M2_" + name[3:], ok, detail)
    else:
        check("MUT_UNKNOWN_KIND", False, kind)


def s1_truth_read_checks(fx: FakeExchange, xnet) -> list:
    """S1 at the truth-read layer: the enumeration and the truth rows must carry EVERY scope."""
    out = []
    enum = xnet.list_perp_dexes(fetcher=fx.fetch, info_url=OFFLINE_INFO, timeout=1.0)
    out.append(("S1_ENUM_HAS_DEFAULT_AND_EVERY_HIP3",
                enum.get("ok") is True and list(enum.get("dexes") or []) == ALL_SCOPES, str(enum)[:300]))
    net = xnet.master_account_net(FOLLOWER, "GOLD", fetcher=fx.fetch, info_url=OFFLINE_INFO, timeout=1.0)
    out.append(("S1_TRUTH_ROW_CARRIES_ALL_SCOPES",
                net.get("ok") is True and net.get("dex_count") == len(ALL_SCOPES)
                and [s.get("dex") for s in (net.get("scopes") or [])] == ["(default)", "flx", "io", "xyz"],
                str(net)[:300]))
    exp = xnet.master_exposure(FOLLOWER, list(ALL_SCOPES), fetcher=fx.fetch, info_url=OFFLINE_INFO, timeout=1.0)
    out.append(("S1_SCOPED_EXPOSURE_COVERS_DEFAULT_AND_HIP3",
                exp.get("ok") is True
                and set((exp.get("by_coin") or {}).keys()) == {"GOLD", "FLX:FOO", "IO:BAR", "XYZ:AMD"},
                str(exp)[:300]))
    return out


def s2_truth_read_check(fx: FakeExchange, xnet, want_dex: str = "qqq") -> tuple:
    """S2 at the truth-read layer: one required scope unreadable => NO green truth, and no net published."""
    net = xnet.master_account_net(FOLLOWER, "GOLD", fetcher=fx.fetch, info_url=OFFLINE_INFO, timeout=1.0)
    ok = (net.get("ok") is False and net.get("status") == "SCOPE_UNAVAILABLE" and net.get("dex") == want_dex
          and "net" not in net and "scopes" not in net)
    return ("S2_TRUTH_READ_FAILS_CLOSED_ON_MISSING_SCOPE", ok, str(net)[:300])


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="inv08scope_"))
    env_file = tmp / "stage2.env"
    env_file.write_text(f"HL_LIVE_HL_ACCOUNT_ADDRESS={FOLLOWER}\n", encoding="utf-8")
    for k in ("HL_FOLLOWER_DEXES", "HL_LIVE_HL_ACCOUNT_ADDRESS", "HL_USER_WALLET"):
        os.environ.pop(k, None)
    os.environ.update({
        "HL_LIVE_AUDIT_DIR": str(tmp), "HL_LEADER_NETWORK": "testnet", "HL_FOLLOWER_NETWORK": "testnet",
        "HL_LIVE_ENV_FILE": str(env_file), "HL_LIVE_SCOPE_SWEEP_THREAD": "0",
        "HL_LIVE_SCOPE_DEX_FRESH_SEC": "0", "HL_LIVE_SCOPE_SWEEP_WEIGHT_PER_MIN": "1000000",
        "HL_LIVE_SCOPE_BACKOFF_MULT": "0.01", "HL_LIVE_SCOPE_FAIL_ROW_AFTER": "2",
    })
    import requests
    import exchange_truth as X
    import HL_Live_Copy_Service_Core as c

    net_hits = []

    def offline(url=None, *a, **k):
        body = k.get("json")
        net_hits.append((str(url), (body or {}).get("type") if isinstance(body, dict) else None))
        raise RuntimeError("offline harness: no network")

    requests.post = offline
    c.requests.post = offline
    c.USER_WALLET = FOLLOWER
    fx = FakeExchange()
    fx.positions = _account_book()
    c.EXPOSURE_FETCHER = fx.fetch
    c._LEARNED_DEXES.clear()
    os.environ.pop("HL_FOLLOWER_DEXES", None)
    c.atomic_write_json(c.LIVE_CONFIG_FILE, {"auto_send_enabled": True, "global_controls": {}, "wallets": {
        LEADER: {"enabled": True, "mode": "LIVE", "copy_mode": "fixed", "fixed_notional": 12}}})
    os.environ.pop("HL_LIVE_MOCK_SEND", None)

    core = c.LiveCopyCore(source_csv=tmp / "none.csv")
    core2 = None
    try:
        core.cfg = c.ConfigManager()

        if SELFMUTANT:
            run_self_mutant(SELFMUTANT, X, fx, core)
            failed = [n for n, ok in RESULTS if not ok]
            print("SELF_MUTANT=%s (the live predicate is the MUTANT: this run MUST fail)" % SELFMUTANT)
            print(f"TOTAL={len(RESULTS)} FAILED={len(failed)}")
            raise SystemExit(1 if failed else 0)


        # ===================== S1: ALL SCOPES ON STARTUP / RECOVERY ==============================
        check("S1_SCOPE_STARTS_AT_DEFAULT_ONLY", c.follower_dex_scope() == [""], str(c.follower_dex_scope()))
        fx.clear_reads()
        res = core.run_scope_sweep()
        check("S1_SWEEP_READS_EVERY_BUILDER_SCOPE",
              res.get("ok") is True and sorted(fx.state_reads()) == sorted(HIP3),
              f"ok={res.get('ok')} reads={sorted(set(fx.state_reads()))} res={str(res)[:200]}")
        check("S1_SWEEP_ENUMERATION_COUNTS_ALL_SCOPES",
              res.get("dex_count") == len(ALL_SCOPES) and res.get("outside_count") == len(HIP3),
              f"dex_count={res.get('dex_count')} outside={res.get('outside_count')}")
        check("S1_TRUTH_CARRIES_A_HOLDING_FROM_EVERY_BUILDER_SCOPE",
              sorted(res.get("held") or []) == ["FLX:FOO", "IO:BAR", "XYZ:AMD"], str(res.get("held"))[:200])
        check("S1_SCOPE_NOW_COVERS_DEFAULT_AND_EVERY_HIP3",
              c.follower_dex_scope() == ALL_SCOPES, str(c.follower_dex_scope()))
        st = c.load_json(Path(c.CORE_RUNTIME_STATE_FILE).parent / "scope_sweep_state.json", {})
        check("S1_STARTUP_TRUTH_ROW_CARRIES_THE_SCOPES",
              st.get("ok") is True and st.get("dex_count") == len(ALL_SCOPES)
              and st.get("outside_count") == len(HIP3) and st.get("held_count") == len(HIP3),
              str(st)[:300])
        for name, ok, detail in s1_truth_read_checks(fx, X):
            check(name, ok, detail)

        # ===================== S2: MISSING REQUIRED SCOPE FAILS CLOSED ==========================
        # A NEW builder/HIP-3 DEX appears on the account (so it is enumerated but not yet in the scope) and it
        # cannot be read. The account's whole-scope truth is then unprovable, and the engine must SAY SO rather
        # than publish the three scopes it happens to have.
        green_before = getattr(core, "_scope_sweep_ok", None)
        fx.dexes = HIP3 + ["qqq"]
        fx.positions["qqq"] = [{"coin": "qqq:NEW", "szi": "5.0", "positionValue": "50"}]
        fx.dead = {"qqq"}
        res = core.run_scope_sweep()
        check("S2_NAMED_REFUSAL_FOR_THE_MISSING_SCOPE",
              res.get("ok") is False and res.get("status") == "SCOPE_UNAVAILABLE" and res.get("dex") == "qqq"
              and "Expecting value" in str(res.get("detail")),
              str(res)[:300])
        check("S2_NO_POSITION_TRUTH_PUBLISHED",
              "held" not in res and res.get("ok") is not True, str(res)[:200])
        check("S2_EARLIER_GREEN_TRUTH_IS_WITHDRAWN",
              green_before is not None and getattr(core, "_scope_sweep_ok", None) is None,
              f"before={str(green_before)[:80]} after={str(getattr(core, '_scope_sweep_ok', None))[:80]}")
        st = c.load_json(Path(c.CORE_RUNTIME_STATE_FILE).parent / "scope_sweep_state.json", {})
        check("S2_STATE_ROW_IS_NOT_GREEN",
              st.get("status") == "SCOPE_UNAVAILABLE" and st.get("dex") == "qqq"
              and st.get("held_count") == 0 and "held" not in st,
              str(st)[:300])
        check("S2_ENTRY_GATE_REFUSES_THE_TRUTH",
              core._scope_sweep_block().startswith("SCOPE_SWEEP_PENDING: SCOPE_UNAVAILABLE"),
              core._scope_sweep_block())
        cyc_err = ""
        try:
            core.run_cycle(use_source_csv=False)
        except Exception as exc:
            cyc_err = repr(exc)[:200]
        check("S2_CYCLE_PUBLISHES_THE_SCOPE_REFUSAL",
              not cyc_err and str(core._entry_sends_blocked_reason).startswith("SCOPE_SWEEP_PENDING"),
              f"cycle_err={cyc_err} reason={core._entry_sends_blocked_reason!r}")
        name, ok, detail = s2_truth_read_check(fx, X)
        check(name, ok, detail)

        # The same refusal on the SCOPED path: a DEX already inside the scope stops answering. Prices, meta and
        # exposure are read over the scope, so the scoped exposure truth must refuse - not silently total three.
        fx.dead = {"flx"}
        exp = X.master_exposure(FOLLOWER, list(c.follower_dex_scope()), fetcher=fx.fetch, info_url=OFFLINE_INFO, timeout=1.0)
        check("S2_SCOPED_EXPOSURE_FAILS_CLOSED_ON_AN_UNREADABLE_SCOPE_MEMBER",
              exp.get("ok") is False and exp.get("status") == "SCOPE_UNAVAILABLE" and exp.get("dex") == "flx"
              and "by_coin" not in exp, str(exp)[:250])
        scoped_net = X.master_account_net(FOLLOWER, "xyz:AMD", fetcher=fx.fetch, info_url=OFFLINE_INFO, timeout=1.0)
        check("S2_SCOPED_COIN_NET_FAILS_CLOSED_AND_PUBLISHES_NO_NET",
              scoped_net.get("ok") is False and scoped_net.get("status") == "SCOPE_UNAVAILABLE"
              and "net" not in scoped_net, str(scoped_net)[:250])
        fx.dead = set()

        # The enumeration itself unavailable: the refusal is named DEX_ENUM_UNAVAILABLE, on both the sweep and the
        # truth read, and no net is published.
        fx.enum_down = True
        core._scope_sweep_ok = None
        res = core.run_scope_sweep()
        check("S2_UNAVAILABLE_ENUMERATION_FAILS_CLOSED",
              res.get("ok") is False and res.get("status") == "DEX_ENUM_UNAVAILABLE", str(res)[:200])
        enum_net = X.master_account_net(FOLLOWER, "GOLD", fetcher=fx.fetch, info_url=OFFLINE_INFO, timeout=1.0)
        check("S2_TRUTH_READ_FAILS_CLOSED_ON_UNAVAILABLE_ENUMERATION",
              enum_net.get("ok") is False and enum_net.get("status") == "DEX_ENUM_UNAVAILABLE"
              and "net" not in enum_net, str(enum_net)[:200])
        fx.enum_down = False
        fx.dexes = list(HIP3)          # the new DEX is gone again; the account is the four scopes S1 proved

        # ===================== S3: NEGATIVE CONTROL (non-vacuity) ===============================
        src_path = Path(X.__file__)
        enum_src = _extract_func(src_path, "list_perp_dexes")
        net_src = _extract_func(src_path, "master_account_net")

        # M1: weakened COPY of the scope-enumeration predicate - HIP-3/builder scopes silently dropped.
        drop_line = '            names.append(str(name).strip())'
        m1_src = enum_src.replace(drop_line, '            pass  # MUTANT M1: builder/HIP-3 scope dropped')
        check("S3_M1_MUTATION_APPLIED", drop_line in enum_src and m1_src != enum_src, "mutant source not produced")
        ns1 = dict(vars(X))
        exec(compile(m1_src, "<mutant M1 list_perp_dexes>", "exec"), ns1)
        m1 = ns1["list_perp_dexes"]
        m1_alone = m1(fetcher=fx.fetch, info_url=OFFLINE_INFO, timeout=1.0)
        check("S3_M1_IS_WORKING_BUT_WEAKER",
              m1_alone.get("ok") is True and list(m1_alone.get("dexes") or []) == [""],
              str(m1_alone)[:200])
        orig_enum = X.list_perp_dexes
        try:
            X.list_perp_dexes = m1
            fx.clear_reads()
            m1_checks = s1_truth_read_checks(fx, X)
        finally:
            X.list_perp_dexes = orig_enum
        red1 = [n for n, ok, _d in m1_checks if not ok]
        print("RED_QUOTE::M1 %s" % ", ".join(red1))
        check("S3_M1_MAKES_S1_RED", "S1_TRUTH_ROW_CARRIES_ALL_SCOPES" in red1, f"red={red1}")

        # M2: fail-OPEN copy of the truth read - an unreadable required scope is skipped, truth goes green.
        fail_line = ('        if not isinstance(state, dict) or not isinstance(state.get("assetPositions"), list):\n'
                     '            return {"ok": False, "status": SCOPE_UNAVAILABLE, "dex": dex, "detail": res.get("detail", "no assetPositions")}')
        m2_src = net_src.replace(fail_line, '        if not isinstance(state, dict) or not isinstance(state.get("assetPositions"), list):\n'
                                            '            continue  # MUTANT M2: a missing scope is skipped')
        check("S3_M2_MUTATION_APPLIED", fail_line in net_src and m2_src != net_src, "mutant source not produced")
        ns2 = dict(vars(X))
        exec(compile(m2_src, "<mutant M2 master_account_net>", "exec"), ns2)
        m2 = ns2["master_account_net"]
        orig_net = X.master_account_net
        try:
            X.master_account_net = m2
            m2_net = m2(FOLLOWER, "GOLD", fetcher=fx.fetch, info_url=OFFLINE_INFO, timeout=1.0)
            check("S3_M2_IS_WORKING_BUT_FAIL_OPEN", m2_net.get("ok") is True, str(m2_net)[:200])
            m2_name, m2_ok, m2_detail = s2_truth_read_check(fx, X)
        finally:
            X.master_account_net = orig_net
        print("RED_QUOTE::M2 %s | %s" % (m2_name, m2_detail))
        check("S3_M2_MAKES_S2_RED", m2_ok is False, m2_detail)

        # restoring the real predicates restores the green S1 result: the RED above came from the MUTANT only
        fx.clear_reads()
        restored = s1_truth_read_checks(fx, X)
        check("S3_PREDICATES_RESTORED_S1_GREEN_AGAIN", all(ok for _n, ok, _d in restored),
              str([n for n, ok, _d in restored if not ok]))

        # ===================== S4: negative test "restart mid-sequence" =========================
        # A FIRST run whose sweep is interrupted mid-sequence (a STOP lands after the first scope): the scopes it
        # never reached have no reading at all, so the account's truth is unproven - even though one scope was read.
        fx.dead = set()
        fx.dexes = list(HIP3)
        fx.positions = _account_book()
        c._LEARNED_DEXES.clear()                            # a fresh process knows no learned DEX yet
        Path(c.CORE_RUNTIME_STATE_FILE).parent.joinpath("scope_dex_cache.json").unlink(missing_ok=True)
        core.__dict__.pop("_scope_dex_cache", None)
        core._scope_cache_loaded = False
        core._scope_sweep_ok = None
        os.environ["HL_LIVE_READ_CONCURRENCY"] = "1"        # one scope per chunk, so a stop can land mid-sequence
        os.environ["HL_LIVE_SCOPE_DEX_FRESH_SEC"] = "0"
        core._hot_stop_event.clear()
        fx.clear_reads()

        def stop_after_first(_payload):
            if len(fx.state_reads()) >= 1:                  # the stop request arrives mid-sequence
                core._hot_stop_event.set()

        fx.on_read = stop_after_first
        mid = core.run_scope_sweep()
        fx.on_read = None
        check("S4_ABORTED_MID_SEQUENCE_LEAVES_SCOPES_UNPROVEN",
              mid.get("ok") is False and mid.get("status") == "SCOPE_UNAVAILABLE"
              and mid.get("failed_dexes") == 2 and len(fx.state_reads()) == 1,
              f"reads={fx.state_reads()} res={str(mid)[:250]}")
        partial_dex = fx.state_reads()[0]

        core._hot_stop_event.clear()
        os.environ["HL_LIVE_SCOPE_DEX_FRESH_SEC"] = "240"   # readings inside the window survive the restart
        fx.clear_reads()
        core2 = c.LiveCopyCore(source_csv=tmp / "none.csv")
        core2.cfg = c.ConfigManager()
        check("S4_RESTART_DECLARES_NO_GREEN_STARTUP_TRUTH",
              core2._scope_sweep_block().startswith("SCOPE_SWEEP_PENDING"),
              core2._scope_sweep_block())
        res2 = core2.run_scope_sweep()
        unproven = sorted(set(HIP3) - {partial_dex})
        check("S4_RESTART_REREADS_ONLY_THE_UNPROVEN_SCOPES",
              res2.get("ok") is True and sorted(set(fx.state_reads())) == unproven,
              f"reads={sorted(set(fx.state_reads()))} expected={unproven} res={str(res2)[:150]}")
        check("S4_TRUTH_GOES_GREEN_ONLY_AFTER_EVERY_SCOPE_READ",
              core2._scope_sweep_block() == "" and res2.get("ok") is True
              and sorted(res2.get("held") or []) == ["FLX:FOO", "IO:BAR", "XYZ:AMD"],
              f"block={core2._scope_sweep_block()!r} res={str(res2)[:200]}")

        check("S0_OFFLINE_NO_NETWORK_READ",
              not [x for x in net_hits if x[1] in ("perpDexs", "clearinghouseState")],
              f"all attempts={net_hits}")
        print("NET_ATTEMPTS::%s" % (net_hits or "none"))
    finally:
        try:
            core.stop()
        except Exception:
            pass
        if core2 is not None:
            try:
                core2.stop()
            except Exception:
                pass

    failed = [n for n, ok in RESULTS if not ok]
    print(f"TOTAL={len(RESULTS)} FAILED={len(failed)}")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
