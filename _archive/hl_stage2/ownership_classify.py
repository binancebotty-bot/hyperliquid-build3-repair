"""Ownership labelling for the Live Copy screen (rulings 6388333568 / 6388338865).

Four names only: ENGINE, USER_OWNED, KNOWN_UNMANAGED, UNKNOWN. Nothing here decides ownership
positively: proven_ownership() is the seam Codex's authoritative rule fills in, and until it does
every item is UNKNOWN rather than a guessed ENGINE.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable, Dict, Optional

OWNERSHIP_CLASSES = ("ENGINE", "USER_OWNED", "KNOWN_UNMANAGED", "UNKNOWN")
KNOWN_UNMANAGED_FILE = Path(os.getenv("HL_KNOWN_UNMANAGED_FILE") or
                            "C:/Users/wigmore/trading_stack/hl-build3-testnet-cert-evidence/run8/state_20261024/known_unmanaged.json")


def fetch_builder_dex_positions(account: str, post: Callable[[Dict[str, Any]], Any], max_dexes: int = 64) -> Dict[str, Any]:
    """Open positions on HIP-3 / builder DEXes (xyz:ORCL and friends). The exchange returns them only
    per scope: {'type':'perpDexs'} lists the dex names, then {'type':'clearinghouseState','user':acct,
    'dex':name} reads each - the main-dex read the caller already does never contains them, which is
    how four leftovers sat unseen. `post` is the caller's /info POST, injected so tests need no
    network. Never raises: an unreadable scope is reported. An empty book still yields the position
    with no bids behind it (a reduce-only sell cannot match); such an item belongs on the
    known-unmanaged list with that reason. Nothing here closes, adopts or resizes."""
    if not account:
        return {"ok": False, "status": "ACCOUNT_ADDRESS_UNAVAILABLE", "positions": [], "scopes": []}
    try:
        enum = post({"type": "perpDexs"})
    except Exception as exc:
        return {"ok": False, "status": "DEX_ENUM_UNAVAILABLE", "detail": f"{type(exc).__name__}: {exc}",
                "positions": [], "scopes": []}
    names = [str((r or {}).get("name") or "").strip() for r in (enum if isinstance(enum, list) else [])
             if isinstance(r, dict)]
    positions: List[Dict[str, Any]] = []
    scopes: List[Dict[str, Any]] = []
    for dex in [n for n in names if n][:max(1, max_dexes)]:
        try:
            state = post({"type": "clearinghouseState", "user": account, "dex": dex})
        except Exception as exc:
            scopes.append({"dex": dex, "status": "SCOPE_UNAVAILABLE", "detail": f"{type(exc).__name__}: {exc}"})
            continue
        if not isinstance(state, dict) or not isinstance(state.get("assetPositions"), list):
            scopes.append({"dex": dex, "status": "SCOPE_UNAVAILABLE", "detail": "no assetPositions"})
            continue
        for item in state["assetPositions"]:
            pos = item.get("position") if isinstance(item, dict) else None
            if not isinstance(pos, dict):
                continue
            try:
                size = float(pos.get("szi") or 0)
            except (TypeError, ValueError):
                continue
            if abs(size) <= 1e-12:
                continue
            value = _num(pos.get("positionValue"))
            positions.append({
                "coin": str(pos.get("coin") or "").upper(),
                "dex": dex,
                "signed_size": size,
                "side": "LONG" if size > 0 else "SHORT",
                "entry_px": _num(pos.get("entryPx")),
                "mark_px": value / abs(size) if abs(size) > 1e-12 else 0.0,
                "position_value": value,
                "unrealized_pnl": _num(pos.get("unrealizedPnl")),
                "leverage": pos.get("leverage"),
                "row_type": "BUILDER_DEX",
            })
        scopes.append({"dex": dex, "status": "OK", "position_count": sum(1 for p in positions if p["dex"] == dex)})
    bad = [s for s in scopes if s.get("status") != "OK"]
    return {"ok": True, "status": "SCOPE_UNAVAILABLE" if bad else "OK",
            "detail": "some scopes unreadable" if bad else "", "positions": positions, "scopes": scopes}


def _num(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def load_known_unmanaged(path: Optional[Path] = None) -> Dict[str, str]:
    """coin -> reason. A missing or unreadable file means nothing is known unmanaged, never an
error: the item then classifies UNKNOWN. Accepts {'positions': [{coin, reason}]}, a bare list, or a
flat {coin: reason} map."""
    try:
        data = json.loads(Path(path or KNOWN_UNMANAGED_FILE).read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    rows = data.get("positions") if isinstance(data, dict) and isinstance(data.get("positions"), list) else data
    if isinstance(rows, dict):
        rows = [{"coin": k, "reason": v} for k, v in rows.items()]
    out: Dict[str, str] = {}
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        coin = str(row.get("coin") or "").upper().strip()
        if coin:
            out[coin] = str(row.get("reason") or "no reason recorded")
    return out


def proven_ownership(item: Dict[str, Any]) -> Optional[str]:
    """SEAM - the one place ownership is proven, and where Codex's authoritative rule plugs in.

Codex's rule returns 'ENGINE' for an item provably carrying the engine's own cloid or a ledger
sleeve, 'USER_OWNED' for one provably placed by hand, None when it proves neither. It stays None
here on purpose: the exact data field is Codex's to define, so the screen must not guess."""
    return None


def classify_ownership(item: Dict[str, Any], known_unmanaged: Optional[Dict[str, str]] = None,
                       proven: Callable[[Dict[str, Any]], Optional[str]] = proven_ownership) -> str:
    """Exactly one of OWNERSHIP_CLASSES for an open position or a resting order. `proven` is the
seam (tests inject a fake, so no network and no live state are needed)."""
    if not isinstance(item, dict):
        return "UNKNOWN"
    verdict = proven(item)
    if verdict in ("ENGINE", "USER_OWNED"):
        return verdict
    known = known_unmanaged if known_unmanaged is not None else load_known_unmanaged()
    coin = str(item.get("coin") or "").upper().strip()
    if coin and coin in known:
        return "KNOWN_UNMANAGED"
    return "UNKNOWN"


def label_rows(rows: Any, known_unmanaged: Optional[Dict[str, str]] = None,
               proven: Callable[[Dict[str, Any]], Optional[str]] = proven_ownership) -> Dict[str, Any]:
    """Writes ownership (and ownership_reason for KNOWN_UNMANAGED) onto every row in place and
returns {'counts': {...}, 'known_unmanaged': {...}}."""
    known = known_unmanaged if known_unmanaged is not None else load_known_unmanaged()
    counts = {k: 0 for k in OWNERSHIP_CLASSES}
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        verdict = classify_ownership(row, known, proven)
        coin = str(row.get("coin") or "").upper().strip()
        row["ownership"] = verdict
        row["ownership_reason"] = known.get(coin, "") if verdict == "KNOWN_UNMANAGED" else ""
        counts[verdict] += 1
    return {"counts": counts, "known_unmanaged": known}
