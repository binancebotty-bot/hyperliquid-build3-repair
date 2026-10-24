"""Assert-based self-check for the ownership seam and the builder-dex fetch. No network, no live
state: the classifier's proven seam and the /info POST are both injected fakes.

Run: python test_ownership_classify.py
"""
import sys

import ownership_classify as oc

OVERRIDES = {c: {"class": "KNOWN_UNMANAGED", "reason": "empty book, no bids"}
             for c in ("XYZ:ORCL", "XYZ:PLTR", "XYZ:MSTR", "XYZ:LLY")}
OVERRIDES["XYZ:USER"] = {"class": "USER_OWNED", "reason": "placed by hand"}


def fake_proven(item):
    """A stand-in for Codex's rule: only an item carrying a field the engine writes is proven."""
    if item.get("engine_cloid"):
        return "ENGINE"
    if item.get("operator_placed") is True:
        return "USER_OWNED"
    return None


def check_four_classes():
    rows = [
        {"coin": "BTC", "engine_cloid": "0xeng1"},
        {"coin": "ETH", "operator_placed": True},
        {"coin": "xyz:ORCL", "dex": "xyz", "signed_size": 0.058},
        {"coin": "SOL"},
    ]
    got = [oc.classify_ownership(r, OVERRIDES, fake_proven) for r in rows]
    assert got == ["ENGINE", "USER_OWNED", "KNOWN_UNMANAGED", "UNKNOWN"], got
    print("four classes:", got)


def check_unproven_is_unknown():
    bare = {"coin": "DOGE", "signed_size": 3.0}
    assert oc.classify_ownership(bare, OVERRIDES) == "UNKNOWN"
    assert oc.classify_ownership(bare, OVERRIDES, fake_proven) == "UNKNOWN"
    assert oc.classify_ownership({"coin": "DOGE", "engine_cloid": ""}, OVERRIDES, fake_proven) == "UNKNOWN"
    assert oc.classify_ownership(None, OVERRIDES) == "UNKNOWN"
    assert oc.classify_ownership({"coin": "xyz:USER"}, OVERRIDES, fake_proven) == "USER_OWNED"
    assert oc.classify_ownership({"coin": "xyz:UNLISTED"}, OVERRIDES, fake_proven) == "UNKNOWN"
    print("no cloid and no ledger entry -> UNKNOWN: ok")


def check_xyz_leftovers_not_engine():
    leftovers = [
        {"coin": "xyz:ORCL", "signed_size": 0.058, "dex": "xyz"},
        {"coin": "xyz:PLTR", "signed_size": 0.186, "dex": "xyz"},
        {"coin": "xyz:MSTR", "signed_size": -0.378, "dex": "xyz"},
        {"coin": "xyz:LLY", "signed_size": -0.024, "dex": "xyz"},
    ]
    got = [oc.classify_ownership(r, OVERRIDES, fake_proven) for r in leftovers]
    assert got == ["KNOWN_UNMANAGED"] * 4, got
    print("xyz leftovers never ENGINE:", got)


def check_unknown_without_list():
    assert oc.load_ownership_overrides(r"C:/definitely/not/here/ownership_overrides.json") == {}
    assert oc.classify_ownership({"coin": "xyz:NOTLISTED"}, None, fake_proven) == "UNKNOWN"
    print("absent ownership_overrides.json -> UNKNOWN, no error: ok")


def check_label_rows():
    rows = [{"coin": "BTC", "engine_cloid": "e"}, {"coin": "xyz:PLTR"}, {"coin": "WIF"}]
    res = oc.label_rows(rows, OVERRIDES, fake_proven)
    assert [r["ownership"] for r in rows] == ["ENGINE", "KNOWN_UNMANAGED", "UNKNOWN"]
    assert rows[1]["ownership_reason"] == "empty book, no bids"
    assert res["counts"] == {"ENGINE": 1, "USER_OWNED": 0, "KNOWN_UNMANAGED": 1, "UNKNOWN": 1}, res
    print("labels + counts:", res["counts"])


def check_builder_dex_fetch():
    calls = []

    def post(payload):
        calls.append(payload)
        if payload["type"] == "perpDexs":
            return [{"name": "xyz"}, {"name": "flx"}]
        if payload["dex"] == "xyz":
            return {"assetPositions": [
                {"position": {"coin": "xyz:ORCL", "szi": "0.058", "entryPx": "1", "positionValue": "0.058", "unrealizedPnl": "0"}},
                {"position": {"coin": "xyz:MSTR", "szi": "-0.378", "entryPx": "2", "positionValue": "0.756", "unrealizedPnl": "0.01"}},
                {"position": {"coin": "xyz:ZERO", "szi": "0"}},
            ]}
        raise RuntimeError("dex flx unreachable")

    out = oc.fetch_builder_dex_positions("0xabc", post)
    assert [c.get("dex") for c in calls if c["type"] == "clearinghouseState"] == ["xyz", "flx"], calls
    assert out["ok"] is True and out["status"] == "SCOPE_UNAVAILABLE", out
    coins = [p["coin"] for p in out["positions"]]
    assert coins == ["XYZ:ORCL", "XYZ:MSTR"], coins
    assert out["positions"][1]["side"] == "SHORT"
    assert out["scopes"] == [{"dex": "xyz", "status": "OK", "position_count": 2},
                             {"dex": "flx", "status": "SCOPE_UNAVAILABLE", "detail": "RuntimeError: dex flx unreachable"}], out["scopes"]
    assert oc.fetch_builder_dex_positions("", post)["status"] == "ACCOUNT_ADDRESS_UNAVAILABLE"
    print("builder dex: perpDexs enumerated, per-dex clearinghouseState read, dead scope reported: ok")


if __name__ == "__main__":
    for fn in (check_four_classes, check_unproven_is_unknown, check_xyz_leftovers_not_engine,
               check_unknown_without_list, check_label_rows, check_builder_dex_fetch):
        fn()
    print("ALL OWNERSHIP SELF-CHECKS PASSED (6/6)")
    sys.exit(0)
