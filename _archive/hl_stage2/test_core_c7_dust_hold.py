#!/usr/bin/env python3
"""C7 lane 3 (commit 4): close-path dust hold for engine-owned sub-minimum EXIT/REDUCE remainders.

Run (from _archive/hl_stage2):  env -u HL_LIVE_AUDIT_DIR python test_core_c7_dust_hold.py

Proves, offline and with no network/orders:
  * a sub-minimum engine-owned close remainder is HELD and journaled per leader fill id (replay cannot double count);
  * combination is capped at the engine sleeve's own signed size (USER residual / other sleeves never added);
  * an exact whole-position close (fresh exchange net == engine sleeve == this close) is exempt from the $10 minimum;
  * a partial dust close with a larger exchange net is never rounded up or sent (held + durable RED);
  * holds clear only on the existing fresh double-flat proof (exchange flat AND engine sleeve flat).
Prints RESULT::name_PASS/FAIL and TOTAL=n FAILED=m.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
TMP = Path(tempfile.mkdtemp(prefix="c7dust_"))
os.environ.update({"HL_LIVE_AUDIT_DIR": str(TMP), "HL_LIVE_ENV_FILE": str(TMP / "none.env"),
                   "HL_LEADER_NETWORK": "testnet", "HL_FOLLOWER_NETWORK": "testnet"})
import HL_Live_Copy_Service_Core as c  # noqa: E402

RESULTS = []


def check(name: str, cond: object, detail: object = "") -> None:
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + str(detail)) if detail and not cond else ""))


WALLET = "0x" + "d" * 40
USER = "0x" + "e" * 40
c.CLOSE_DUST_HOLDS_FILE = TMP / "close_dust_holds.json"
c.CLOSE_ESCALATIONS_FILE = TMP / "close_escalations.json"
c.EXCHANGE_ACCOUNT_SNAPSHOT_FILE = TMP / "exchange_account_snapshot.json"
RESOLVED = {"ok": True, "raw_coin": "NEAR", "sdk_coin": "NEAR", "min_order_value_usd": 10.0,
            "sz_decimals": 2, "price_max_decimals": 4, "perp_dexs": [""]}
_seq = {"n": 0}


class Audit:
    def __init__(self) -> None:
        self.rows = []

    def append_reconciliation(self, event, status, **kwargs) -> None:
        self.rows.append((event, status, kwargs))


def reset_files() -> None:
    for p in (c.CLOSE_DUST_HOLDS_FILE, c.CLOSE_ESCALATIONS_FILE):
        if p.exists():
            p.unlink()


def ledger(sleeve_sizes, user_size=None):
    """A real ManualLedger with explicit sleeve sizes and a fresh by_coin_net."""
    _seq["n"] += 1
    led = c.ManualLedger(path=TMP / ("led_%d.json" % _seq["n"]))
    for wallet, coin, size in sleeve_sizes:
        led.sleeve(wallet, coin)["signed_size"] = size
    if user_size is not None:
        led.sleeve(USER, "NEAR")["signed_size"] = user_size
    led._recompute_net(led.data)
    return led


def gateway(led, exchange_net):
    g = c.SenderGateway(c.ConfigManager(), Audit(), led)  # type: ignore[arg-type]
    box = {"net": exchange_net}
    g._fresh_exchange_net = lambda coin: box["net"]
    g._close_proof_account_ok = lambda: True
    return g, box


def intent(fill_id="f1", side="BUY", size=0.1, price=4.4, lifecycle="EXIT"):
    fill = c.LeaderFill(fill_id, WALLET, "NEAR", side, price, 0.1, c.utc_now_ms(), "TEST")
    return c.Intent("i-" + fill_id, fill, side, size, size * price, "CLO", "fixed",
                    "EXIT_ALLOWED", lifecycle, c.ManualLedger.sleeve_id(WALLET, "NEAR"),
                    "pos-NEAR", "SHORT" if side == "BUY" else "LONG",
                    -1.0 if side == "BUY" else 1.0, -1.0 if side == "BUY" else 1.0,
                    True, True, c.utc_now_ms(), "lifecycle=%s;" % lifecycle)


def dust_rows():
    rows = c.load_json(c.CLOSE_DUST_HOLDS_FILE, {})
    return rows if isinstance(rows, dict) else {}


def main() -> None:
    # 1. 40 distinct fills at 0.1 combine to the sleeve's 4.0; a replay of any fill adds nothing.
    reset_files()
    led = ledger([(WALLET, "NEAR", -4.0)])
    g, box = gateway(led, -4.0)
    total = 0.0
    for n in range(40):
        total = g._record_close_dust_hold(intent("fill-%02d" % n), 0.1, 4.4, "HELD")
    check("C7_DUST_40_FILLS_COMBINE", abs(total - 4.0) <= 1e-9 and len(dust_rows()) == 40, total)
    replayed = g._record_close_dust_hold(intent("fill-00"), 0.1, 4.4, "REPLAY")
    check("C7_DUST_REPLAY_CANNOT_DOUBLE_COUNT", abs(replayed - 4.0) <= 1e-9 and len(dust_rows()) == 40, replayed)
    check("C7_DUST_ROWS_KEYED_PER_FILL_AND_ENGINE_OWNED",
          all(r.get("engine_owned_only") is True and bool(r.get("leader_fill_id")) for r in dust_rows().values()))

    # 2. Combination never exceeds the engine sleeve's own signed size.
    reset_files()
    led = ledger([(WALLET, "NEAR", -0.3)])
    g, box = gateway(led, -0.3)
    total = 0.0
    for n in range(40):
        total = g._record_close_dust_hold(intent("cap-%02d" % n), 0.1, 4.4, "HELD")
    capped = g._record_close_dust_hold(intent("cap-oversized"), 5.0, 4.4, "HELD")
    check("C7_DUST_NEVER_EXCEEDS_ENGINE_SLEEVE", abs(total - 0.3) <= 1e-9 and abs(capped - 0.3) <= 1e-9,
          (total, capped))

    # 3. A partial dust remainder (exchange holds more than the engine sleeve) is HELD, never sent or rounded up.
    reset_files()
    led = ledger([(WALLET, "NEAR", -0.1)], user_size=-10.4)
    g, box = gateway(led, -10.5)
    ok, wire, ro, block = g._plan_close_dust(intent(), RESOLVED, 0.1, 4.4, 2, True, {})
    check("C7_DUST_PARTIAL_HELD_NOT_SENT",
          ok is False and block.get("status") == "DUST_CLOSE_HELD_BELOW_VENUE_MINIMUM" and len(dust_rows()) == 1,
          (ok, block.get("status"), len(dust_rows())))
    check("C7_DUST_PARTIAL_CANNOT_BORROW_USER_RESIDUAL",
          led.sleeve(USER, "NEAR")["signed_size"] == -10.4
          and abs(list(dust_rows().values())[0]["size"] - 0.1) <= 1e-9)
    esc = c.load_json(c.CLOSE_ESCALATIONS_FILE, {})
    check("C7_DUST_PARTIAL_LEAVES_DURABLE_RED",
          esc.get(c.ManualLedger.sleeve_id(WALLET, "NEAR"), {}).get("state") == "OPEN", esc)

    # 4. A partial dust gate call is still blocked below the venue minimum (fresh read larger than the sleeve).
    g2, box2 = gateway(ledger([(WALLET, "NEAR", -0.1)], user_size=-10.4), -10.5)
    timing = {}
    gate_ok, gate_block = g2._validate_final_wire_order(intent(), dict(RESOLVED), "NEAR", 0.1, 4.4, timing,
                                                        wire_reduce_only=True)
    check("C7_DUST_PARTIAL_GATE_BLOCKED",
          gate_ok is False and gate_block.get("terminal_state") == "DUST_BELOW_MIN_NOTIONAL"
          and "fresh_whole_exchange_close_exempt" not in timing, (gate_ok, gate_block.get("terminal_state")))

    # 5. A single sub-$10 close that IS the whole exchange position (engine sleeve == fresh net) is sent, exempt,
    #    and not journaled as held.
    reset_files()
    led = ledger([(WALLET, "NEAR", -0.1)])
    g, box = gateway(led, -0.1)
    ok, wire, ro, block = g._plan_close_dust(intent(), RESOLVED, 0.1, 4.4, 2, True, {})
    check("C7_DUST_SINGLE_WHOLE_POSITION_SENT", ok is True and abs(wire - 0.1) <= 1e-9 and ro is True
          and not dust_rows(), (ok, wire, ro, block))
    timing = {}
    gate_ok, gate_block = g._validate_final_wire_order(intent(), dict(RESOLVED), "NEAR", 0.1, 4.4, timing,
                                                        wire_reduce_only=True)
    check("C7_DUST_WHOLE_POSITION_GATE_EXEMPT",
          gate_ok is True and bool(timing.get("fresh_whole_exchange_close_exempt")), (gate_ok, timing))

    # 5b. REDUCE lifecycle gets the same exemption (lane covers EXIT and REDUCE).
    timing = {}
    reduce_ok, _ = g._validate_final_wire_order(intent("reduce", lifecycle="REDUCE"), dict(RESOLVED), "NEAR",
                                                0.1, 4.4, timing, wire_reduce_only=True)
    check("C7_DUST_REDUCE_LIFECYCLE_WHOLE_CLOSE_EXEMPT", reduce_ok is True and bool(timing), timing)

    # 6. Combined dust BELOW $10 that equals the whole position is sent as that exact whole-position close.
    reset_files()
    led = ledger([(WALLET, "NEAR", -4.0)])
    g, box = gateway(led, -4.0)
    for n in range(40):
        g._record_close_dust_hold(intent("whole-%02d" % n), 0.1, 1.0, "HELD")
    timing = {}
    ok, wire, ro, block = g._plan_close_dust(intent("whole-00"), RESOLVED, 0.1, 1.0, 2, True, timing)
    check("C7_DUST_COMBINED_WHOLE_POSITION_SENT",
          ok is True and abs(wire - 4.0) <= 1e-9 and ro is True
          and timing.get("dust_combined_whole_position_size") == 4.0, (ok, wire, timing))
    gate_ok, gate_block = g._validate_final_wire_order(intent("whole-00"), dict(RESOLVED), "NEAR", wire, 1.0,
                                                        {}, wire_reduce_only=True)
    check("C7_DUST_COMBINED_WHOLE_POSITION_GATE_EXEMPT", gate_ok is True, gate_block)

    # 7. Combined engine dust above $10 on a PARTIAL sleeve is sent reduce-only within that sleeve; the
    #    10.5 account net (0.1 engine + 10.4 USER) is never closed.
    reset_files()
    led = ledger([(WALLET, "NEAR", -4.0)], user_size=-6.5)
    g, box = gateway(led, -10.5)
    for n in range(40):
        g._record_close_dust_hold(intent("part-%02d" % n), 0.1, 4.4, "HELD")
    timing = {}
    ok, wire, ro, block = g._plan_close_dust(intent("part-00"), RESOLVED, 0.1, 4.4, 2, True, timing)
    check("C7_DUST_COMBINED_PARTIAL_SLEEVE_SENDS_ONLY_ENGINE_SIZE",
          ok is True and abs(wire - 4.0) <= 1e-9 and ro is True
          and timing.get("dust_combined_same_sleeve_size") == 4.0
          and "dust_combined_whole_position_size" not in timing, (ok, wire, timing))
    check("C7_DUST_COMBINED_PARTIAL_NEVER_TOUCHES_USER", led.sleeve(USER, "NEAR")["signed_size"] == -6.5)

    # 8. Holds clear only on the existing fresh double-flat proof.
    reset_files()
    led = ledger([(WALLET, "NEAR", -0.1)])
    g, box = gateway(led, -10.5)
    ok, _w, _r, _b = g._plan_close_dust(intent(), RESOLVED, 0.1, 4.4, 2, True, {})
    box["net"] = 0.0  # exchange flat, engine sleeve still non-flat
    check("C7_DUST_EXCHANGE_FLAT_ALONE_DOES_NOT_CLEAR",
          ok is False and g._clear_flat_close_dust() == 0 and len(dust_rows()) == 1)
    led.sleeve(WALLET, "NEAR")["signed_size"] = 0.0
    led._recompute_net(led.data)
    box["net"] = -10.5  # engine sleeve flat, account still holds USER residual
    check("C7_DUST_SLEEVE_FLAT_ALONE_DOES_NOT_CLEAR",
          g._clear_flat_close_dust() == 0 and len(dust_rows()) == 1)
    box["net"] = 0.0
    cleared = g._clear_flat_close_dust()
    check("C7_DUST_DOUBLE_FLAT_CLEARS_HOLDS", cleared == 1 and not dust_rows(), (cleared, dust_rows()))

    # 9. The same double-flat proof retires the durable RED via clear_close_escalations (existing hook).
    reset_files()
    led = ledger([(WALLET, "NEAR", -0.1)])
    g, box = gateway(led, -10.5)
    g._plan_close_dust(intent(), RESOLVED, 0.1, 4.4, 2, True, {})
    key = c.ManualLedger.sleeve_id(WALLET, "NEAR")
    check("C7_DUST_RED_OPEN_BEFORE_FLAT", key in c.load_json(c.CLOSE_ESCALATIONS_FILE, {}))
    led.sleeve(WALLET, "NEAR")["signed_size"] = 0.0
    led._recompute_net(led.data)
    box["net"] = 0.0
    check("C7_DUST_DOUBLE_FLAT_CLEARS_RED_AND_HOLDS",
          g.clear_close_escalations() == 1 and not dust_rows()
          and not c.load_json(c.CLOSE_ESCALATIONS_FILE, {}),
          (c.load_json(c.CLOSE_ESCALATIONS_FILE, {}), dust_rows()))

    failed = [n for n, ok in RESULTS if not ok]
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
