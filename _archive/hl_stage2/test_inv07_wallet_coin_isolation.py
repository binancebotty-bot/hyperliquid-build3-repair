#!/usr/bin/env python3
"""ENG-INV-07: leader mutable state is isolated by (wallet, coin) -- CONTROLLED TWO-LEADER PROOF.

The claim under test (ARCHITECTURE.md "ARCH inv7"): every piece of per-leader mutable
engine state is keyed by BOTH the leader wallet and the coin, so two leaders that trade
the SAME coin inside ONE process can never read, move, adopt or close each other's sleeve.

Keys under test (real engine code, unchanged):
  ManualLedger.sleeve_id(wallet, coin)                  -> "<wallet>::<coin>"
  ManualLedger.position_id(wallet, coin, dir, intent)   -> "<wallet>::<coin>::<dir>::<intent>"
  ManualLedger.data["by_wallet"][wallet][coin]          -> the sleeve row itself
  IntentBuilder._exit_chain[sleeve_id(...)]             -> the per-sleeve close-chain head

Cases (each one prints RESULT::<NAME>_PASS|_FAIL; the ABSENCE of a cross effect is what is
asserted, never merely the presence of the intended one):

  I1  TWO WALLETS, ONE COIN   -- leaders A and B both BUY BTC, interleaved fills A1 B1 A2 B2.
                                 Each sleeve's desired net / signed_size / position_id stays
                                 its own and the OTHER wallet's sleeve row is unchanged after
                                 every fill; no intent carries the other wallet's size.
  I2  ONE WALLET, TWO COINS   -- follower A on BTC and ETH: a BTC fill never moves the ETH
                                 sleeve and vice versa; per-coin nets stay separate.
  I3  FLAT-vs-LONG COLLISION  -- wallet A flat, wallet B long on the same coin: B's close
                                 decision reads B's sleeve only, never consumes A's, and a
                                 close-shaped event for flat A is refused instead of adopting
                                 B's position ("the engine never adopts or closes a position
                                 it did not open"). Exit-chain heads stay per sleeve, so B's
                                 close size can never be clamped by A's sleeve.
  I4  RESTART-INDEPENDENCE    -- the ledger rebuilt from its OWN rows reproduces every
                                 per-sleeve value; no coin-only dict, no shared mutable
                                 default between sleeves or between ledger instances.
  I5  MUTATION CONTROL        -- a SCRATCH COPY of this tree with sleeve_id degraded to
                                 coin-only (one line) must make this harness FAIL; the
                                 reddened check names are printed. Nothing outside the
                                 scratch copy is written. This is what makes the run
                                 evidence rather than a green assertion.

Offline: no network, no exchange, no send path, no live state dir. HL_LIVE_ENV_FILE is
pointed at /nonexistent so no operator secrets are loaded. The only data sources replaced
are the price mids (a deterministic dict); the ledger, the intent builder, the isolation
keys and the close-chain code are the real engine's.

Run:
  cd C:/Users/wigmore/oc-runs/r4-v2-inv07/_archive/hl_stage2 && \\
  HL_LIVE_ENV_FILE=/nonexistent python -u test_inv07_wallet_coin_isolation.py

Exit 0 when every check passes, 1 otherwise.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
TMP = Path(tempfile.mkdtemp(prefix="inv07_"))

# Isolation must be proved inside this process, with no live state and no network.
os.environ.update({
    "HL_LIVE_AUDIT_DIR": str(TMP),
    "HL_LIVE_ENV_FILE": "/nonexistent",
    "HL_LIVE_WS_ENABLED": "0",
    "HL_LIVE_AUTO_SEND_ENABLED": "0",
    "HL_LIVE_POLL_ENABLED": "0",
    "HL_FOLLOWER_DEXES": "",
    "PYTHONHASHSEED": "0",
})
sys.path.insert(0, str(HERE))
import HL_Live_Copy_Service_Core as c  # noqa: E402
import HL_Live_Copy_Service as svc  # noqa: E402  (pure per-wallet sizing helpers live here)

# ----------------------------------------------------------------------------- fixtures
A = "0x" + "a" * 40          # leader wallet A  (synthetic, public shape only)
B = "0x" + "b" * 40          # leader wallet B
UNKNOWN = "0x" + "c" * 40    # a wallet the ledger has never seen
PX = {"BTC": 100.0, "ETH": 50.0}
FIX_A, FIX_B = 100.0, 250.0  # different fixed notionals: a crossed size is unmistakable
SIZE_A, SIZE_B = FIX_A / PX["BTC"], FIX_B / PX["BTC"]   # 1.0 / 2.5 BTC
N_A, N_B = FIX_A / PX["ETH"], FIX_B / PX["ETH"]         # 2.0 / 5.0 ETH

c.MIDS_FETCHER = lambda p: [] if isinstance(p, dict) and p.get("type") == "perpDexs" else dict(PX)
c.LEADER_MIDS_FETCHER = c.MIDS_FETCHER

(TMP / "live_config.json").write_text(json.dumps({
    "global_controls": {"min_notional": 10.0, "marketable_bps": 0},
    "wallets": {
        A: {"mode": "LIVE", "enabled": True, "copy_mode": "fixed", "fixed_notional": FIX_A},
        B: {"mode": "LIVE", "enabled": True, "copy_mode": "fixed", "fixed_notional": FIX_B},
    },
}), encoding="utf-8")
CFG = c.ConfigManager()

RESULTS = []


def check(name: str, ok: bool, detail: str = "") -> None:
    ok = bool(ok)
    RESULTS.append((name, ok))
    print("RESULT::%s_%s%s" % (name, "PASS" if ok else "FAIL",
                               ("" if ok or not detail else " | " + str(detail)[:700])), flush=True)


def case(name: str, fn) -> None:
    """Run one case; an exception is a named FAIL carrying the exception text, never a crash."""
    try:
        fn()
    except Exception as exc:                                    # noqa: BLE001
        check(name, False, "EXCEPTION %s: %s" % (type(exc).__name__, str(exc)[:400]))


_n = [0]


def new_ledger(tag: str) -> "c.ManualLedger":
    return c.ManualLedger(path=TMP / ("ledger_%s.json" % tag))


def fill(fid: str, wallet: str, coin: str, side: str, size: float, ts: int, sp=None, direction=None):
    raw = {}
    if sp is not None:
        raw["startPosition"] = str(sp)
    if direction is not None:
        raw["dir"] = direction
    return c.LeaderFill(fid, wallet, coin, side, PX[coin], size, ts, "TEST", raw=raw)


def sig(ledger, wallet: str, coin: str):
    """The full identity of one sleeve row: everything a cross-wallet write would disturb."""
    s = ledger.sleeve(wallet, coin)
    return (round(float(s.get("signed_size") or 0.0), 12), str(s.get("direction") or ""),
            str(s.get("position_id") or ""), str(s.get("opened_by_intent_id") or ""),
            str(s.get("last_copy_fill_id") or ""), str(s.get("sleeve_id") or ""),
            str(s.get("leader_wallet") or ""), str(s.get("coin") or ""))


def settle(ledger, it, tag: str):
    """Settle an ALREADY BUILT intent into the real ledger as the copy fill (one build per fill)."""
    ledger.apply_copy_fill(it, {"side": it.copy_side, "size": it.copy_size,
                                "price": PX[it.fill.coin], "copy_fill_id": "cf_" + tag})
    return it


def apply(builder, ledger, f, tag: str):
    """Build the real intent, then settle it into the real ledger as the copy fill."""
    return settle(ledger, builder.build(f), tag)


def near(a: float, b: float, tol: float = 1e-9) -> bool:
    return abs(float(a) - float(b)) <= tol


# =============================================================== I1 two wallets, one coin
def case_i1() -> None:
    ledger = new_ledger("i1")
    builder = c.IntentBuilder(CFG, ledger)
    coin = "BTC"

    check("I1_SLEEVE_IDS_WALLET_SCOPED",
          ledger.sleeve_id(A, coin) != ledger.sleeve_id(B, coin)
          and A in ledger.sleeve_id(A, coin) and B in ledger.sleeve_id(B, coin),
          "%r vs %r" % (ledger.sleeve_id(A, coin), ledger.sleeve_id(B, coin)))
    check("I1_SLEEVE_ROWS_ARE_DISTINCT_OBJECTS",
          ledger.sleeve(A, coin) is not ledger.sleeve(B, coin),
          "the two wallet sleeves must not be one shared dict")

    flat_b = sig(ledger, B, coin)
    it_a1 = apply(builder, ledger, fill("i1a1", A, coin, "BUY", 4.0, 1000), "i1a1")
    after_a1 = sig(ledger, A, coin)
    check("I1_A1_SIZES_A_SLEEVE_AND_LEAVES_B_UNTOUCHED",
          near(it_a1.copy_size, SIZE_A) and near(after_a1[0], SIZE_A) and sig(ledger, B, coin) == flat_b,
          "copy=%s A=%s B=%s" % (it_a1.copy_size, after_a1[0], sig(ledger, B, coin)))

    after_b1 = None
    it_b1 = apply(builder, ledger, fill("i1b1", B, coin, "BUY", 4.0, 2000), "i1b1")
    after_b1 = sig(ledger, B, coin)
    check("I1_B1_SIZES_B_SLEEVE_AND_LEAVES_A_UNTOUCHED",
          near(it_b1.copy_size, SIZE_B) and near(after_b1[0], SIZE_B)
          and sig(ledger, A, coin) == after_a1,
          "copy=%s B=%s A=%s" % (it_b1.copy_size, after_b1[0], sig(ledger, A, coin)))

    it_a2 = apply(builder, ledger, fill("i1a2", A, coin, "BUY", 4.0, 3000), "i1a2")
    after_a2 = sig(ledger, A, coin)
    check("I1_A2_ADDS_TO_A_ONLY",
          near(it_a2.copy_size, SIZE_A) and near(after_a2[0], 2 * SIZE_A)
          and sig(ledger, B, coin) == after_b1,
          "copy=%s A=%s B=%s" % (it_a2.copy_size, after_a2[0], sig(ledger, B, coin)))

    it_b2 = apply(builder, ledger, fill("i1b2", B, coin, "BUY", 4.0, 4000), "i1b2")
    after_b2 = sig(ledger, B, coin)
    check("I1_B2_ADDS_TO_B_ONLY",
          near(it_b2.copy_size, SIZE_B) and near(after_b2[0], 2 * SIZE_B)
          and sig(ledger, A, coin) == after_a2,
          "copy=%s B=%s A=%s" % (it_b2.copy_size, after_b2[0], sig(ledger, A, coin)))

    intents = [it_a1, it_b1, it_a2, it_b2]
    own_sizes_ok = all(
        (near(it.copy_size, SIZE_A) if it.fill.leader_wallet == A else near(it.copy_size, SIZE_B))
        for it in intents)
    no_foreign = all(
        (it.sleeve_id.startswith(it.fill.leader_wallet) and it.fill.leader_wallet in it.sleeve_id)
        for it in intents)
    check("I1_NO_INTENT_CARRIES_THE_OTHER_WALLETS_SIZE",
          own_sizes_ok and no_foreign,
          "sizes=%s sleeve_ids=%s" % ([it.copy_size for it in intents], [it.sleeve_id for it in intents]))

    pa, pb = str(after_a2[2]), str(after_b2[2])
    check("I1_POSITION_IDS_ARE_WALLET_SCOPED_AND_DISTINCT",
          pa and pb and pa != pb and pa.startswith(A) and pb.startswith(B),
          "%r vs %r" % (pa, pb))

    # desired net per sleeve, with BOTH leaders present in one call
    la = svc.LiveWalletConfig(wallet=A, mode="LIVE", copy_mode="fixed", fixed_notional=FIX_A, enabled=True)
    lb = svc.LiveWalletConfig(wallet=B, mode="LIVE", copy_mode="fixed", fixed_notional=FIX_B, enabled=True)
    units = {A: 2 * SIZE_A, B: 2 * SIZE_B}
    both = svc.event_authorised_desired_net(coin, {A: 4.0, B: 4.0}, {A: la, B: lb}, units)
    b_flipped = svc.event_authorised_desired_net(coin, {A: 4.0, B: -4.0}, {A: la, B: lb}, units)
    check("I1_DESIRED_NET_PER_SLEEVE_IS_ITS_OWN",
          both.get("ok") and near(both["sleeves"][A], 2 * SIZE_A)
          and near(both["sleeves"][B], 2 * SIZE_B)
          and near(both["desired_net"], 2 * SIZE_A + 2 * SIZE_B),
          str(both))
    check("I1_DESIRED_NET_A_UNMOVED_BY_B_LEADERS_SIGN_FLIP",
          near(b_flipped["sleeves"][A], both["sleeves"][A])
          and near(b_flipped["sleeves"][B], -both["sleeves"][B]),
          "%s -> %s" % (both.get("sleeves"), b_flipped.get("sleeves")))

    net = ledger.data.get("by_coin_net") or {}
    check("I1_ACCOUNT_COIN_NET_IS_THE_SUM_OF_THE_TWO_SLEEVES",
          near((net.get("BTC") or {}).get("signed_size"), 2 * SIZE_A + 2 * SIZE_B),
          str(net))


# =============================================================== I2 one wallet, two coins
def case_i2() -> None:
    ledger = new_ledger("i2")
    builder = c.IntentBuilder(CFG, ledger)
    btc, eth = "BTC", "ETH"

    check("I2_SLEEVE_IDS_COIN_SCOPED",
          ledger.sleeve_id(A, btc) != ledger.sleeve_id(A, eth)
          and btc in ledger.sleeve_id(A, btc) and eth in ledger.sleeve_id(A, eth),
          "%r vs %r" % (ledger.sleeve_id(A, btc), ledger.sleeve_id(A, eth)))

    flat_eth = sig(ledger, A, eth)
    it1 = apply(builder, ledger, fill("i2b1", A, btc, "BUY", 4.0, 1000), "i2b1")
    btc_after = sig(ledger, A, btc)
    check("I2_BTC_FILL_NEVER_MOVES_THE_ETH_SLEEVE",
          near(it1.copy_size, SIZE_A) and near(btc_after[0], SIZE_A) and sig(ledger, A, eth) == flat_eth,
          "btc=%s eth=%s" % (btc_after[0], sig(ledger, A, eth)))

    it2 = apply(builder, ledger, fill("i2e1", A, eth, "BUY", 2.0, 2000), "i2e1")
    eth_after = sig(ledger, A, eth)
    check("I2_ETH_FILL_NEVER_MOVES_THE_BTC_SLEEVE",
          near(it2.copy_size, N_A) and near(eth_after[0], N_A) and sig(ledger, A, btc) == btc_after,
          "eth=%s btc=%s" % (eth_after[0], sig(ledger, A, btc)))

    it3 = apply(builder, ledger, fill("i2b2", A, btc, "BUY", 4.0, 3000), "i2b2")
    check("I2_SECOND_BTC_FILL_STILL_LEAVES_ETH_ALONE",
          near(sig(ledger, A, btc)[0], 2 * SIZE_A) and sig(ledger, A, eth) == eth_after,
          "btc=%s eth=%s" % (sig(ledger, A, btc)[0], sig(ledger, A, eth)))

    net = ledger.data.get("by_coin_net") or {}
    check("I2_PER_COIN_NETS_ARE_SEPARATE",
          near((net.get("BTC") or {}).get("signed_size"), 2 * SIZE_A)
          and near((net.get("ETH") or {}).get("signed_size"), N_A),
          str(net))

    pa, pe = str(sig(ledger, A, btc)[2]), str(sig(ledger, A, eth)[2])
    check("I2_POSITION_IDS_DIFFER_ACROSS_COINS",
          pa and pe and pa != pe and "::BTC::" in pa and "::ETH::" in pe, "%r vs %r" % (pa, pe))


# =========================================================== I3 flat-vs-long collision
def case_i3() -> None:
    coin = "BTC"
    ledger = new_ledger("i3")
    builder = c.IntentBuilder(CFG, ledger)

    # wallet A opens and then fully closes: A is FLAT. wallet B is LONG on the same coin.
    apply(builder, ledger, fill("i3a_open", A, coin, "BUY", 4.0, 1000), "i3a_open")
    apply(builder, ledger, fill("i3a_close", A, coin, "SELL", 4.0, 2000, sp=4.0), "i3a_close")
    a_flat = sig(ledger, A, coin)
    it_b_open = apply(builder, ledger, fill("i3b_open", B, coin, "BUY", 4.0, 3000), "i3b_open")
    b_long = sig(ledger, B, coin)
    b_position_id = it_b_open.position_id

    check("I3_PRECONDITION_A_FLAT_B_LONG",
          near(a_flat[0], 0.0) and a_flat[1] == "FLAT" and a_flat[2] == ""
          and near(b_long[0], SIZE_B) and b_long[1] == "LONG" and b_long[2] == b_position_id,
          "A=%s B=%s" % (a_flat, b_long))

    # A close DECISION for B: it must read B's sleeve and B's position id, nothing of A's.
    b_close_fill = fill("i3b_close", B, coin, "SELL", 4.0, 4000, sp=4.0, direction="Close Long")
    it_close = builder.build(b_close_fill)
    check("I3_CLOSE_FOR_B_READS_B_SLEEVE_ONLY",
          it_close.sleeve_id == ledger.sleeve_id(B, coin)
          and near(it_close.wallet_position_before, SIZE_B)
          and it_close.position_id == b_position_id
          and it_close.decision == "EXIT_ALLOWED"
          and near(it_close.copy_size, SIZE_B),
          "sleeve=%r before=%s pos=%r decision=%s size=%s"
          % (it_close.sleeve_id, it_close.wallet_position_before, it_close.position_id,
             it_close.decision, it_close.copy_size))
    check("I3_BUILDING_B_CLOSE_DOES_NOT_WRITE_A_SLEEVE",
          sig(ledger, A, coin) == a_flat and sig(ledger, B, coin) == b_long,
          "A=%s B=%s" % (sig(ledger, A, coin), sig(ledger, B, coin)))

    # a close-shaped event for the FLAT wallet A must never adopt B's position (never adopt invariant)
    a_close_fill = fill("i3a_bogus", A, coin, "SELL", 4.0, 5000, sp=4.0, direction="Close Long")
    it_a = builder.build(a_close_fill)
    check("I3_FLAT_WALLET_CLOSE_EVENT_IS_REFUSED_NOT_ADOPTED",
          it_a.decision == "SEND_NOT_ATTEMPTED_NO_MANUAL_POSITION"
          and it_a.send_allowed is False
          and near(it_a.wallet_position_before, 0.0)
          and it_a.sleeve_id == ledger.sleeve_id(A, coin)
          and sig(ledger, A, coin) == a_flat and sig(ledger, B, coin) == b_long,
          "decision=%s send_allowed=%s before=%s A=%s B=%s"
          % (it_a.decision, it_a.send_allowed, it_a.wallet_position_before,
             sig(ledger, A, coin), sig(ledger, B, coin)))

    # B's close settles on B; A stays flat and untouched, so B's position is never adopted into A.
    settle(ledger, it_close, "i3b_close")
    check("I3_B_CLOSE_NEVER_ADOPTS_INTO_A",
          near(sig(ledger, B, coin)[0], 0.0) and sig(ledger, B, coin)[1] == "FLAT"
          and sig(ledger, A, coin) == a_flat,
          "A=%s B=%s" % (sig(ledger, A, coin), sig(ledger, B, coin)))

    # ---- exit-chain heads are per-sleeve mutable state: A's head must never size B's close
    ledger2 = new_ledger("i3chain")
    builder2 = c.IntentBuilder(CFG, ledger2)
    apply(builder2, ledger2, fill("c_a1", A, coin, "BUY", 4.0, 1000), "c_a1")
    apply(builder2, ledger2, fill("c_a2", A, coin, "SELL", 1.0, 2000, sp=4.0), "c_a2")   # A head: copy 1.0 @ cursor 3.0
    a_head = dict((builder2._exit_chain or {}).get(ledger2.sleeve_id(A, coin)) or {})
    apply(builder2, ledger2, fill("c_b1", B, coin, "BUY", 4.0, 3000), "c_b1")             # B opens; A's head must survive
    a_head_after_b_open = dict((builder2._exit_chain or {}).get(ledger2.sleeve_id(A, coin)) or {})
    b_close_c = fill("c_b2", B, coin, "SELL", 1.5, 4000, sp=3.0)
    it_b_close = builder2.build(b_close_c)
    # B's own sleeve is 2.5 at leader head 3.0, so its 1.5 close is 50% of the sleeve = 1.25.
    # If B's close were sized off A's head it would be 1.0*(1.5/4.0) = 0.375 - and in any case
    # A's copy sleeve (1.0) could never be the clamp on a 2.5-sized close.
    check("I3_CLOSE_SIZE_COMES_FROM_ITS_OWN_ANCHOR",
          near(it_b_close.copy_size, 1.25, 1e-6) and it_b_close.copy_size > a_head.get("copy_sleeve", 0.0),
          "copy=%s expected=1.25 A_head_copy=%s" % (it_b_close.copy_size, a_head.get("copy_sleeve")))
    check("I3_EXIT_CHAIN_HEAD_ISOLATED_FROM_THE_OTHER_WALLET",
          a_head and a_head == a_head_after_b_open
          and near(a_head.get("copy_sleeve"), SIZE_A) and near(a_head.get("cursor"), 3.0),
          "A head before B open=%s after=%s" % (a_head, a_head_after_b_open))
    settle(ledger2, it_b_close, "c_b2")
    keys = set((builder2._exit_chain or {}).keys())
    check("I3_EXIT_CHAIN_KEYS_ARE_WALLET_SCOPED",
          ledger2.sleeve_id(A, coin) in keys and ledger2.sleeve_id(B, coin) in keys and len(keys) == 2,
          "keys=%s" % sorted(keys))
    check("I3_B_CLOSE_SHRANK_B_ONLY",
          near(sig(ledger2, B, coin)[0], SIZE_B - 1.25) and near(sig(ledger2, A, coin)[0], SIZE_A - 0.25),
          "A=%s B=%s" % (sig(ledger2, A, coin)[0], sig(ledger2, B, coin)[0]))


# ============================================================ I4 restart-independence
def case_i4() -> None:
    coin = "BTC"
    ledger = new_ledger("i4")
    builder = c.IntentBuilder(CFG, ledger)
    apply(builder, ledger, fill("r_a1", A, coin, "BUY", 4.0, 1000), "r_a1")
    apply(builder, ledger, fill("r_a2", A, coin, "BUY", 4.0, 2000), "r_a2")
    apply(builder, ledger, fill("r_e1", A, "ETH", "BUY", 2.0, 3000), "r_e1")
    apply(builder, ledger, fill("r_b1", B, coin, "BUY", 4.0, 4000), "r_b1")
    apply(builder, ledger, fill("r_b2", B, coin, "BUY", 4.0, 5000), "r_b2")
    before = {(w, k): sig(ledger, w, k) for w in (A, B) for k in (coin, "ETH")}
    ledger.save()

    rebuilt = c.ManualLedger(path=ledger.path)
    after = {(w, k): sig(rebuilt, w, k) for w in (A, B) for k in (coin, "ETH")}
    check("I4_REBUILD_FROM_OWN_ROWS_REPRODUCES_EVERY_SLEEVE", before == after,
          "before=%s after=%s" % (before, after))

    by_wallet = rebuilt.data.get("by_wallet") or {}
    rows_wallet_scoped = True
    for w, wallet_map in by_wallet.items():
        if not isinstance(wallet_map, dict):
            rows_wallet_scoped = False
            continue
        for k, row in wallet_map.items():
            if str((row or {}).get("leader_wallet")) != w or str((row or {}).get("coin")) != k:
                rows_wallet_scoped = False
    check("I4_LEDGER_KEYED_BY_WALLET_THEN_COIN",
          set(by_wallet.keys()) == {A, B}
          and "BTC" not in by_wallet and "ETH" not in by_wallet
          and rows_wallet_scoped
          and near(rebuilt.wallet_coin_position(B, "ETH"), 0.0),
          "by_wallet keys=%s rows_wallet_scoped=%s" % (sorted(by_wallet.keys()), rows_wallet_scoped))
    check("I4_SLEEVE_ROW_IDENTITIES_SURVIVE_THE_REBUILD",
          rebuilt.sleeve_id(A, coin) != rebuilt.sleeve_id(B, coin)
          and str(rebuilt.sleeve(A, coin).get("sleeve_id")) == rebuilt.sleeve_id(A, coin)
          and str(rebuilt.sleeve(B, coin).get("sleeve_id")) == rebuilt.sleeve_id(B, coin)
          and str(rebuilt.sleeve(A, coin).get("position_id")) != str(rebuilt.sleeve(B, coin).get("position_id"))
          and str(rebuilt.sleeve(A, coin).get("position_id")).startswith(A)
          and str(rebuilt.sleeve(B, coin).get("position_id")).startswith(B),
          "A=%r B=%r" % (rebuilt.sleeve(A, coin).get("sleeve_id"), rebuilt.sleeve(B, coin).get("sleeve_id")))

    check("I4_UNKNOWN_WALLET_READS_FLAT_NOT_ANOTHER_WALLET",
          near(rebuilt.wallet_coin_position(UNKNOWN, coin), 0.0)
          and rebuilt.sleeve(UNKNOWN, coin).get("position_id") == "",
          "unknown=%s" % rebuilt.wallet_coin_position(UNKNOWN, coin))

    # no shared mutable default: one sleeve row, one ledger instance, cannot be another's
    row_a = rebuilt.sleeve(A, coin)
    untouched_b = sig(rebuilt, B, coin)
    untouched_orig = sig(ledger, A, coin)
    row_a["signed_size"] = 99.0
    check("I4_NO_SHARED_MUTABLE_DEFAULT_BETWEEN_SLEEVES",
          sig(rebuilt, B, coin) == untouched_b and sig(ledger, A, coin) == untouched_orig,
          "B=%s original_A=%s" % (sig(rebuilt, B, coin), sig(ledger, A, coin)))
    check("I4_SEPARATE_SLEEVE_ROWS_PER_WALLET_AND_COIN",
          rebuilt.sleeve(A, coin) is not rebuilt.sleeve(B, coin)
          and rebuilt.sleeve(A, coin) is not rebuilt.sleeve(A, "ETH"),
          "distinct dict objects required")

    empty1 = c.ManualLedger(path=TMP / "i4_empty1.json")
    empty2 = c.ManualLedger(path=TMP / "i4_empty2.json")
    empty1.sleeve(A, coin)["signed_size"] = 7.0
    check("I4_TWO_LEDGER_INSTANCES_DO_NOT_SHARE_STATE",
          near(empty2.wallet_coin_position(A, coin), 0.0)
          and near(empty1.wallet_coin_position(A, coin), 7.0),
          "empty2=%s empty1=%s" % (empty2.wallet_coin_position(A, coin), empty1.wallet_coin_position(A, coin)))


# ============================================================== I5 mutation control
ISOLATION_LINE = '        return f"{normalise_wallet(wallet)}::{canonical_coin_key(coin)}"'
MUTATED_LINE = '        return f"{canonical_coin_key(coin)}"'


def case_i5() -> None:
    """Degrade sleeve_id to coin-only in a SCRATCH COPY of this tree; the harness must go red."""
    scratch = Path(tempfile.mkdtemp(prefix="inv07_mut_", dir=str(TMP)))
    copy = scratch / "tree"
    shutil.copytree(HERE, copy, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".git"))
    target = copy / "HL_Live_Copy_Service_Core.py"
    src = target.read_text(encoding="utf-8")
    hits = src.count(ISOLATION_LINE)
    if hits != 1:
        check("I5_MUTATION_APPLIED_TO_THE_SCRATCH_COPY", False,
              "expected exactly 1 sleeve_id return line, found %d" % hits)
        return
    target.write_text(src.replace(ISOLATION_LINE, MUTATED_LINE), encoding="utf-8")
    mutated_line_present = MUTATED_LINE.strip() in target.read_text(encoding="utf-8")
    real_line_absent = ISOLATION_LINE.strip() not in target.read_text(encoding="utf-8")
    check("I5_MUTATION_APPLIED_TO_THE_SCRATCH_COPY",
          mutated_line_present and real_line_absent and copy != HERE,
          "mutated=%s real_removed=%s copy=%s" % (mutated_line_present, real_line_absent, copy))

    child_env = dict(os.environ)
    child_env.update({
        "HL_LIVE_AUDIT_DIR": str(scratch / "state"),
        "HL_LIVE_ENV_FILE": "/nonexistent",
        "INV07_MUTATION_CHILD": "1",
        "PYTHONPATH": "",
    })
    Path(child_env["HL_LIVE_AUDIT_DIR"]).mkdir(parents=True, exist_ok=True)
    proc = subprocess.run([sys.executable, "-u", "test_inv07_wallet_coin_isolation.py"],
                          cwd=str(copy), env=child_env, capture_output=True, text=True, timeout=900)
    out = (proc.stdout or "") + (proc.stderr or "")
    log = TMP / "i5_mutation_child.log"
    log.write_text(out, encoding="utf-8")
    reddened = sorted({ln[len("RESULT::"):].split(" | ")[0].rsplit("_FAIL", 1)[0]
                       for ln in out.splitlines()
                       if ln.startswith("RESULT::") and "_FAIL" in ln.split(" | ")[0]})
    total_line = [ln for ln in out.splitlines() if ln.startswith("TOTAL=")]
    print("MUTATION::child_rc=%d reddened=%d checks log=%s" % (proc.returncode, len(reddened), log))
    for name in reddened:
        print("MUTATION::RED::%s" % name)
    if total_line:
        print("MUTATION::child_%s" % total_line[-1])

    expected = {"I1_SLEEVE_IDS_WALLET_SCOPED", "I3_EXIT_CHAIN_KEYS_ARE_WALLET_SCOPED",
                "I4_SLEEVE_ROW_IDENTITIES_SURVIVE_THE_REBUILD"}
    missing = sorted(expected - set(reddened))
    check("I5_MUTATED_TREE_FAILS_THE_HARNESS", proc.returncode != 0,
          "child exit=%d (a coin-only sleeve_id must not pass)" % proc.returncode)
    check("I5_MUTATION_REDDENS_THE_ISOLATION_CHECKS",
          not missing and len(reddened) >= len(expected),
          "reddened=%s missing=%s" % (reddened, missing))


def main() -> int:
    print("ENG-INV-07 controlled two-leader (wallet, coin) isolation proof")
    print("tree=%s ledger_keys=sleeve_id/position_id/by_wallet" % HERE)
    print("wallets A=%s fixed=%.1f  B=%s fixed=%.1f  prices=%s" % (A, FIX_A, B, FIX_B, PX))
    case("I1_CASE_RAISED", case_i1)
    case("I2_CASE_RAISED", case_i2)
    case("I3_CASE_RAISED", case_i3)
    case("I4_CASE_RAISED", case_i4)
    if os.environ.get("INV07_MUTATION_CHILD") != "1":
        case("I5_CASE_RAISED", case_i5)
    failed = [n for n, ok in RESULTS if not ok]
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
    if failed:
        print("FAILED_CHECKS=%s" % ",".join(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
