"""G3 EXCHANGE_TRUTH / SETTLEMENT seam (ruling B3-A2C-G2-PASS-G3-1). Read-only MASTER truth.

Follower ACTUAL = MASTER exchange truth over ALL perp DEX scopes, failing closed when a scope is
unavailable; signer != MASTER; snapshots mint zero authority; an ack is NOT settlement (in-flight
clears only on independent MASTER userFills + position, or a terminal rejection); divergence
surfaces; unattributed inventory is excluded from sleeve convergence.
"""
import re

HL_INFO_URL = "https://api.hyperliquid.xyz/info"
_ADDR = re.compile(r"^0x[0-9a-fA-F]{40}$")
TRUTH_OK, IDENTITY_INVALID = "OK", "IDENTITY_INVALID"
DEX_ENUM_UNAVAILABLE, SCOPE_UNAVAILABLE = "DEX_ENUM_UNAVAILABLE", "SCOPE_UNAVAILABLE"
TRUTH_UNAVAILABLE, SETTLE_UNKNOWN = "TRUTH_UNAVAILABLE", "SETTLEMENT_UNKNOWN"
SETTLE_FULL, SETTLE_PARTIAL, SETTLE_NONE, SETTLE_REJECTED = "SETTLED_FULL", "SETTLED_PARTIAL", "UNSETTLED", "TERMINAL_REJECT_NO_FILL"

def valid_address(value) -> bool:
    return bool(_ADDR.match(str(value or "").strip()))

def identity_ok(signer_address, master_address) -> bool:
    """API signer and MASTER/trading account are DISTINCT, well-formed identities."""
    signer, master = str(signer_address or "").strip().lower(), str(master_address or "").strip().lower()
    return valid_address(signer) and valid_address(master) and signer != master

def _post(fetcher, payload, info_url, timeout):
    """Read-only POST to /info; `fetcher` is injected so tests use offline fixtures."""
    try:
        if fetcher is not None:
            raw = fetcher(payload)
        else:  # pragma: no cover - live read-only plumbing
            import requests  # type: ignore
            raw = requests.post(info_url, json=payload, timeout=timeout).json()
    except Exception as exc:
        return {"ok": False, "status": TRUTH_UNAVAILABLE, "detail": repr(exc)[:200]}
    if not isinstance(raw, (dict, list)):
        return {"ok": False, "status": TRUTH_UNAVAILABLE, "detail": "non-JSON payload"}
    return {"ok": True, "data": raw}

def list_perp_dexes(fetcher=None, info_url=HL_INFO_URL, timeout=8.0):
    """Every perp DEX scope: the default scope plus HIP-3/builder DEXes."""
    res = _post(fetcher, {"type": "perpDexs"}, info_url, timeout)
    if not res.get("ok"):
        return {"ok": False, "status": DEX_ENUM_UNAVAILABLE, "detail": res.get("detail", "")}
    names = [""]
    for item in (res["data"] if isinstance(res["data"], list) else []):
        name = (item.get("name") if isinstance(item, dict) else item) or ""
        if str(name).strip():
            names.append(str(name).strip())
    return {"ok": True, "status": TRUTH_OK, "dexes": sorted(set(names))}

def master_account_net(master_address, coin, fetcher=None, info_url=HL_INFO_URL, timeout=8.0, dexes=None):
    """MASTER signed exposure for `coin` aggregated over every perp DEX scope. Missing scope fails closed."""
    if not valid_address(master_address):
        return {"ok": False, "status": IDENTITY_INVALID}
    if dexes is None:
        enum = list_perp_dexes(fetcher, info_url, timeout)
        if not enum.get("ok"):
            return {"ok": False, "status": DEX_ENUM_UNAVAILABLE, "detail": enum.get("detail", "")}
        dexes = enum["dexes"]
    want, total, scopes = str(coin or "").upper().strip(), 0.0, []
    for dex in dexes:
        payload = {"type": "clearinghouseState", "user": master_address}
        if dex:
            payload["dex"] = dex
        res = _post(fetcher, payload, info_url, timeout)
        state = res.get("data") if res.get("ok") else None
        if not isinstance(state, dict) or not isinstance(state.get("assetPositions"), list):
            return {"ok": False, "status": SCOPE_UNAVAILABLE, "dex": dex, "detail": res.get("detail", "no assetPositions")}
        signed = 0.0
        for item in state["assetPositions"]:
            pos = (item or {}).get("position") if isinstance(item, dict) else None
            if isinstance(pos, dict) and str(pos.get("coin") or "").upper().strip() == want:
                signed = float(pos.get("szi") or 0.0)
                break
        scopes.append({"dex": dex or "(default)", "signed": signed})
        total += signed
    return {"ok": True, "status": TRUTH_OK, "net": total, "scopes": scopes, "dex_count": len(dexes)}

def master_userfills(master_address, start_ms, fetcher=None, info_url=HL_INFO_URL, timeout=8.0):
    """MASTER settlement evidence: genuine fills at/after start_ms (read-only)."""
    if not valid_address(master_address):
        return {"ok": False, "status": IDENTITY_INVALID}
    res = _post(fetcher, {"type": "userFillsByTime", "user": master_address, "startTime": int(start_ms)}, info_url, timeout)
    rows = res.get("data") if res.get("ok") else None
    if not isinstance(rows, list):
        return {"ok": False, "status": TRUTH_UNAVAILABLE, "detail": res.get("detail", "userFillsByTime not a list")}
    return {"ok": True, "status": TRUTH_OK, "fills": [r for r in rows if isinstance(r, dict)]}

def _match(fill, coin, side, oid) -> bool:
    if str((fill or {}).get("coin") or "").upper().strip() != str(coin or "").upper().strip():
        return False
    fside_raw = str((fill or {}).get("side") or "").upper().strip()
    fside = {"B": "BUY", "A": "SELL"}.get(fside_raw, fside_raw)  # Hyperliquid userFills uses B/A
    if fside and side and fside != str(side).upper().strip():
        return False
    if oid not in (None, "") and (fill or {}).get("oid") not in (None, ""):
        return str(fill.get("oid")) == str(oid)
    return True

def resolve_settlement(intent, fills, master_net, terminal_reject=False):
    """Clear an in-flight reservation ONLY from independent MASTER evidence for this intent."""
    size = abs(float(intent.get("size") or 0.0))
    coin, side, oid = intent.get("coin"), intent.get("side"), intent.get("oid")
    if terminal_reject:
        if [f for f in (fills or []) if _match(f, coin, side, oid)]:
            return {"settled": False, "status": SETTLE_UNKNOWN, "detail": "reject conflicts with matching fill"}
        return {"settled": True, "status": SETTLE_REJECTED, "filled": 0.0, "remaining": 0.0, "position_after": None}
    if fills is None or master_net is None:
        return {"settled": False, "status": SETTLE_UNKNOWN, "detail": "no independent MASTER evidence"}
    matched = [f for f in fills if _match(f, coin, side, oid)]
    if not matched:
        return {"settled": False, "status": SETTLE_NONE, "filled": 0.0, "remaining": size}
    filled = 0.0
    for f in matched:
        try:
            filled += abs(float(f.get("sz") or 0.0))
        except Exception:
            return {"settled": False, "status": SETTLE_UNKNOWN, "detail": "unparseable fill size"}
    remaining = max(0.0, size - filled)
    if remaining <= 1e-9:
        return {"settled": True, "status": SETTLE_FULL, "filled": filled, "remaining": 0.0, "position_after": master_net}
    return {"settled": False, "status": SETTLE_PARTIAL, "filled": filled, "remaining": remaining, "position_after": master_net}

def reconcile_sleeve(desired_net, master_net, unattributed_net):
    """Divergence blocker + unrelated-inventory preservation: converge the COPY SLEEVE only."""
    expected = float(desired_net) + float(unattributed_net)
    divergence = abs(float(master_net) - expected)
    return {"ok": True, "sleeve_net": float(master_net) - float(unattributed_net),
            "unattributed_net": float(unattributed_net), "divergence": divergence,
            "blocker": None if divergence <= max(1e-9, abs(expected) * 1e-6) else "RECONCILIATION_DIVERGENCE"}
