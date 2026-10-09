"""G3 EXCHANGE_TRUTH / SETTLEMENT seam (ruling B3-A2C-G2-PASS-G3-1). Read-only MASTER truth.

Follower ACTUAL = MASTER exchange truth over ALL perp DEX scopes, failing closed when a scope is
unavailable; signer != MASTER; snapshots mint zero authority; an ack is NOT settlement (in-flight
clears only on independent MASTER userFills + position, or a terminal rejection); divergence
surfaces; unattributed inventory is excluded from sleeve convergence.
"""
import json
import os
import re
from urllib.parse import urlparse

# Network selection. The leader feed and the follower account are chosen independently, so an
# instance can watch real mainnet leaders while trading and verifying a testnet follower. Every
# follower read (positions, fills, settlement, meta/precision, quotes) and every order goes to the
# FOLLOWER network; only leader fill intake uses the LEADER network. Unknown names fail closed.
NETWORK_HOSTS = {"mainnet": "https://api.hyperliquid.xyz", "testnet": "https://api.hyperliquid-testnet.xyz"}
DEFAULT_LEADER_NETWORK, DEFAULT_FOLLOWER_NETWORK = "mainnet", "testnet"
NETWORK_STAMP_FILE = "network.json"


class NetworkConfigError(ValueError):
    pass


def network_endpoints(name):
    key = str(name or "").strip().lower()
    if key not in NETWORK_HOSTS:
        raise NetworkConfigError(f"UNKNOWN_NETWORK:{name!r} (expected one of {sorted(NETWORK_HOSTS)})")
    base = NETWORK_HOSTS[key]
    return {"network": key, "base": base, "info": base + "/info", "exchange": base + "/exchange",
            "ws": "wss://" + urlparse(base).netloc + "/ws"}


def resolve_networks(env=None):
    """{'leader': endpoints, 'follower': endpoints} from HL_LEADER_NETWORK / HL_FOLLOWER_NETWORK.

    The follower defaults to testnet: a mainnet follower must be named explicitly. Legacy URL
    overrides (HL_LIVE_ORDER_ENDPOINT, HL_LIVE_WS_URL, HL_INFO_URL) must point at the selected host,
    else NetworkConfigError - orders and truth can never silently land on different networks.
    """
    env = os.environ if env is None else env
    leader = network_endpoints(env.get("HL_LEADER_NETWORK") or DEFAULT_LEADER_NETWORK)
    follower = network_endpoints(env.get("HL_FOLLOWER_NETWORK") or DEFAULT_FOLLOWER_NETWORK)
    # HL_INFO_URL (Core) once served leader AND follower reads, so it must match both networks
    for var, net in (("HL_LIVE_ORDER_ENDPOINT", follower), ("HL_LIVE_WS_URL", leader),
                     ("HL_INFO_URL", follower), ("HL_INFO_URL", leader)):
        url = str(env.get(var) or "").strip()
        if url and urlparse(url).netloc.lower() != urlparse(net["base"]).netloc:
            raise NetworkConfigError(f"NETWORK_ENDPOINT_MISMATCH:{var}={url} but {net['network']} selected")
    return {"leader": leader, "follower": follower}


def env_with_file(path):
    """os.environ over KEY=VALUE lines of a local env file (os.environ wins), for processes that read
    hl_stage2.env without loading it into os.environ (the UI), so both sides pick the same networks."""
    merged = {}
    try:
        with open(str(path), encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    merged[k.strip()] = v.strip()
    except OSError:
        pass
    merged.update(os.environ)
    return merged


def claim_network_stamp(state_dir, networks):
    """Bind a state directory to one leader/follower network pair. A directory already stamped for
    a different pair raises, so a testnet instance can never resume mainnet state or vice versa."""
    want = {"leader": networks["leader"]["network"], "follower": networks["follower"]["network"]}
    path = os.path.join(str(state_dir), NETWORK_STAMP_FILE)
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as fh:
                have = json.load(fh)
        except Exception as exc:
            raise NetworkConfigError(f"NETWORK_STAMP_UNREADABLE:{path}:{exc!r}")
        if not isinstance(have, dict) or {k: have.get(k) for k in want} != want:
            raise NetworkConfigError(f"NETWORK_STAMP_MISMATCH:{path} is {have} but this instance is {want}")
        return want
    os.makedirs(str(state_dir), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(want, fh)
    return want


try:
    NETWORKS = resolve_networks()
    HL_INFO_URL = NETWORKS["follower"]["info"]
except NetworkConfigError as _net_exc:  # follower truth reads fail closed; the service refuses to start
    NETWORKS, HL_INFO_URL, NETWORK_ERROR = None, "", str(_net_exc)
else:
    NETWORK_ERROR = ""
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

def master_exposure(master_address, dexes, fetcher=None, info_url=HL_INFO_URL, timeout=8.0):
    """MASTER exposure across every perp DEX scope: total |positionValue| plus per-coin signed size
    and |value|. Used by the global exposure caps; any unreadable scope fails closed."""
    if not valid_address(master_address):
        return {"ok": False, "status": IDENTITY_INVALID}
    total, by_coin = 0.0, {}
    for dex in (dexes if dexes is not None else [""]):
        payload = {"type": "clearinghouseState", "user": master_address}
        if dex:
            payload["dex"] = dex
        res = _post(fetcher, payload, info_url, timeout)
        state = res.get("data") if res.get("ok") else None
        if not isinstance(state, dict) or not isinstance(state.get("assetPositions"), list):
            return {"ok": False, "status": SCOPE_UNAVAILABLE, "dex": dex, "detail": res.get("detail", "no assetPositions")}
        for item in state["assetPositions"]:
            pos = (item or {}).get("position") if isinstance(item, dict) else None
            if not isinstance(pos, dict):
                continue
            coin, value = str(pos.get("coin") or "").upper().strip(), abs(float(pos.get("positionValue") or 0.0))
            row = by_coin.setdefault(coin, {"net": 0.0, "value": 0.0})
            row["net"] += float(pos.get("szi") or 0.0)
            row["value"] += value
            total += value
    return {"ok": True, "status": TRUTH_OK, "total_usd": total, "by_coin": by_coin}

def master_userfills(master_address, start_ms, dex="", fetcher=None, info_url=HL_INFO_URL, timeout=8.0):
    """MASTER settlement evidence: genuine fills at/after start_ms, scoped to one perp DEX ('' = default)."""
    if not valid_address(master_address):
        return {"ok": False, "status": IDENTITY_INVALID}
    payload = {"type": "userFillsByTime", "user": master_address, "startTime": int(start_ms)}
    if dex:
        payload["dex"] = dex
    res = _post(fetcher, payload, info_url, timeout)
    rows = res.get("data") if res.get("ok") else None
    if not isinstance(rows, list):
        return {"ok": False, "status": TRUTH_UNAVAILABLE, "dex": dex, "detail": res.get("detail", "userFillsByTime not a list")}
    return {"ok": True, "status": TRUTH_OK, "dex": dex, "fills": [r for r in rows if isinstance(r, dict)]}


def _fill_key(fill):
    """Deterministic dedupe identity for a MASTER fill across DEX scopes."""
    return "|".join(str((fill or {}).get(k) or "") for k in ("oid", "tid", "time", "coin", "sz", "px", "side"))


def master_userfills_all_dexes(master_address, start_ms, dexes, fetcher=None, info_url=HL_INFO_URL, timeout=8.0):
    """Per-scope MASTER userFillsByTime for the default DEX and every HIP-3/builder scope.

    Any required scope unavailable/unreadable => settlement truth unavailable (caller keeps blocking).
    Fills are deduplicated deterministically across scopes.
    """
    if not valid_address(master_address):
        return {"ok": False, "status": IDENTITY_INVALID}
    merged, seen, scopes, raw = [], set(), [], 0
    for dex in (dexes if dexes is not None else [""]):
        res = master_userfills(master_address, start_ms, dex, fetcher=fetcher, info_url=info_url, timeout=timeout)
        if not res.get("ok"):
            return {"ok": False, "status": TRUTH_UNAVAILABLE, "dex": dex, "detail": res.get("detail", "scope fill read failed")}
        for fill in res.get("fills", []):
            key = _fill_key(fill)
            if key in seen:
                continue
            seen.add(key)
            merged.append(fill)
        scopes.append({"dex": dex or "(default)", "count": len(res.get("fills", []))})
        raw += len(res.get("fills", []))
    merged.sort(key=_fill_key)
    return {"ok": True, "status": TRUTH_OK, "fills": merged, "scopes": scopes,
            "deduped": raw - len(merged), "count": len(merged)}


def terminal_reject_evidence(exchange_status, oid_accepted, no_fill_proved):
    """Evidence record for a terminal no-fill clear. A bare caller boolean can never satisfy this:
    it requires an exchange-derived terminal rejection AND an all-DEX post-attempt no-fill proof."""
    return {"terminal_reject": str(exchange_status or "").strip().upper() in
            {"ORDER_REJECTED", "REJECTED", "REFUSED", "CLIENT_ORDER_REJECT", "TERMINAL_REJECT"},
            "exchange_status": str(exchange_status or ""), "oid_accepted": bool(oid_accepted),
            "no_fill_proved": bool(no_fill_proved)}


def runtime_master_identity(env=None):
    """Production identity wiring: MASTER from HL_LIVE_HL_ACCOUNT_ADDRESS, signer derived from the
    configured private key. Signer and MASTER must both be valid and DISTINCT; else fail closed."""
    env = env if env is not None else __import__("os").environ
    master = str(env.get("HL_LIVE_HL_ACCOUNT_ADDRESS", "") or "").strip()
    signer = str(env.get("HL_LIVE_HL_SIGNER_ADDRESS", "") or "").strip()
    key = str(env.get("HL_LIVE_HL_PRIVATE_KEY", "") or "").strip()
    if not signer and key:
        try:  # derive the signing identity with the same plumbing the sender uses
            from eth_account import Account  # type: ignore
            signer = str(Account.from_key(key).address or "").strip()
        except Exception as exc:
            return {"ok": False, "status": IDENTITY_INVALID, "detail": f"signer derivation failed: {exc!r}"}
    if not valid_address(master) or not valid_address(signer) or signer.lower() == master.lower():
        return {"ok": False, "status": IDENTITY_INVALID, "detail": "invalid or non-distinct MASTER/signer identity"}
    return {"ok": True, "status": TRUTH_OK, "master": master, "signer": signer}

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

def resolve_settlement(intent, fills, master_net, reject_evidence=None):
    """Clear an in-flight reservation ONLY from independent MASTER evidence for this intent.

    A caller boolean is never sufficient: a no-fill terminal clear needs the evidence record from
    terminal_reject_evidence() (exchange-derived rejection + all-DEX no-fill proof) AND no matching
    fill AND no accepted oid whose absence is unproven.
    """
    size = abs(float(intent.get("size") or 0.0))
    coin, side, oid = intent.get("coin"), intent.get("side"), intent.get("oid")
    if reject_evidence:
        ev = reject_evidence if isinstance(reject_evidence, dict) else {}
        matched = [f for f in (fills or []) if _match(f, coin, side, oid)]
        if not (ev.get("terminal_reject") and ev.get("no_fill_proved")):
            return {"settled": False, "status": SETTLE_UNKNOWN, "detail": "insufficient terminal-reject evidence"}
        if oid and ev.get("oid_accepted"):
            return {"settled": False, "status": SETTLE_UNKNOWN, "detail": "accepted oid; absence not proven"}
        if fills is None:
            return {"settled": False, "status": SETTLE_UNKNOWN, "detail": "no post-attempt MASTER proof"}
        if matched:
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
