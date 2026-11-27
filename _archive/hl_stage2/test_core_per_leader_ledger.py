"""Per-leader copy ledger regressions. Run: python test_core_per_leader_ledger.py"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
tmp = Path(tempfile.mkdtemp(prefix="per_leader_ledger_"))
os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LIVE_ENV_FILE": str(tmp / "none.env")})

import HL_Live_Copy_Service_Core as c

RESULTS = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(ok)))
    print("RESULT::%s_%s%s" % (name, "PASS" if ok else "FAIL", (" | " + detail) if detail and not ok else ""))


def fill(fill_id: str, wallet: str, side: str, price: float, size: float, timestamp_ms: int) -> c.LeaderFill:
    return c.LeaderFill(fill_id, wallet, "BTC", side, price, size, timestamp_ms, "TEST",
                        raw={"dir": "Open Long" if side == "BUY" else "Open Short"})


def intent(intent_id: str, leader_fill: c.LeaderFill) -> c.Intent:
    return c.Intent(
        intent_id=intent_id,
        fill=leader_fill,
        copy_side=leader_fill.side,
        copy_size=leader_fill.size,
        copy_notional=leader_fill.price * leader_fill.size,
        wallet_mode="LIVE",
        copy_mode="fixed",
        decision="ENTRY_ALLOWED",
        reason="test",
        sleeve_id=c.ManualLedger.sleeve_id(leader_fill.leader_wallet, leader_fill.coin),
        position_id="",
        position_direction_before="FLAT",
        wallet_position_before=0.0,
        coin_net_before=0.0,
        reduce_only_intended=False,
        reduce_only_sent_planned=False,
    )


def test_crossing_fill_opens_new_leader_positions() -> None:
    ledger = c.ManualLedger(path=tmp / "crossing.json")
    alpha = "0x" + "a" * 40
    beta = "0x" + "b" * 40
    alpha_open = fill("a-open", alpha, "BUY", 100.0, 1.0, 10)
    beta_open = fill("b-open", beta, "SELL", 90.0, 2.0, 11)
    ledger.apply_copy_fill(intent("a-open-intent", alpha_open), {"side": "BUY", "size": 1.0, "price": 100.0, "copy_fill_id": "a1"})
    ledger.apply_copy_fill(intent("b-open-intent", beta_open), {"side": "SELL", "size": 2.0, "price": 90.0, "copy_fill_id": "b1"})

    alpha_cross = fill("a-cross", alpha, "SELL", 110.0, 2.0, 12)
    beta_cross = fill("b-cross", beta, "BUY", 120.0, 3.0, 13)
    ledger.apply_copy_fill(intent("a-cross-intent", alpha_cross), {"side": "SELL", "size": 2.0, "price": 110.0, "copy_fill_id": "a2"})
    ledger.apply_copy_fill(intent("b-cross-intent", beta_cross), {"side": "BUY", "size": 3.0, "price": 120.0, "copy_fill_id": "b2"})

    a, b = ledger.sleeve(alpha, "BTC"), ledger.sleeve(beta, "BTC")
    check("CROSSING_RESETS_ALPHA_ENTRY", a["direction"] == "SHORT" and a["signed_size"] == -1.0
          and a["avg_entry_px"] == 110.0 and a["opened_at_ms"] == 12 and a["opened_by_intent_id"] == "a-cross-intent"
          and a["position_id"] == c.ManualLedger.position_id(alpha, "BTC", "SHORT", "a-cross-intent"), str(a))
    check("CROSSING_RESETS_BETA_ENTRY", b["direction"] == "LONG" and b["signed_size"] == 1.0
          and b["avg_entry_px"] == 120.0 and b["opened_at_ms"] == 13 and b["opened_by_intent_id"] == "b-cross-intent"
          and b["position_id"] == c.ManualLedger.position_id(beta, "BTC", "LONG", "b-cross-intent"), str(b))
    check("CROSSING_REMAINS_PER_LEADER", ledger.wallet_coin_position(alpha, "BTC") == -1.0
          and ledger.wallet_coin_position(beta, "BTC") == 1.0 and ledger.coin_net("BTC") == 0.0)


def test_merged_fills_are_one_twelve_dollar_intent() -> None:
    wallet = "0x" + "c" * 40
    first = fill("m1", wallet, "BUY", 100.0, 1.0, 1)
    second = fill("m2", wallet, "BUY", 100.0, 2.0, 2)
    second = c.LeaderFill(second.leader_fill_id, second.leader_wallet, second.coin, second.side,
                          second.price, second.size, 2, second.source, raw={"dir": "Open Long"})
    merged = c.merge_leader_fills([first, second])
    cfg = SimpleNamespace(copy_mode=lambda _wallet: "fixed", fixed_notional=lambda _wallet: 12.0)
    builder = c.IntentBuilder.__new__(c.IntentBuilder)
    builder.cfg = cfg

    check("MERGE_RETAINS_BOTH_FILL_IDS", merged.raw["merged_fill_ids"] == ["m2"] and merged.raw["merged_fill_count"] == 2)
    check("MERGED_FILL_MAKES_ONE_TWELVE_DOLLAR_INTENT", builder._copy_notional(wallet, merged) == 12.0,
          str(builder._copy_notional(wallet, merged)))


def main() -> int:
    test_crossing_fill_opens_new_leader_positions()
    test_merged_fills_are_one_twelve_dollar_intent()
    failed = [name for name, ok in RESULTS if not ok]
    print(f"TOTAL={len(RESULTS)} FAILED={len(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
