#!/usr/bin/env python3
"""Catch-up plan for a leader's late fills in one coin: one NET order per (wallet, coin).

Pure function, NOT wired into the engine. Prototype for the controller to compare against the engine's
current per-fill merge (HL_Live_Copy_Service_Core._plan_batch / mergeable_fills / already_closed_late_entries).

Rules (Boss, 2026-10-10): after a gap, rebuild what the leader actually did over the window, as ONE net order
per (wallet, coin), never turning a late entry into a position the leader no longer holds.

  plan_catchup(fills, held_before) -> dict with:
    fills       : the batch, in time order (each a dict: side, size, price, ts, startPosition, id)
    held_before : the position the account held BEFORE these fills (leader, and the engine's sleeve copy)
    returns     : {"steps": [...], "net": float, "leader_after": float, "netting": bool, "notes": [...]}
      steps: one of
        {"action": "FILL",  ...}   per-fill fallback (startPosition unknown somewhere: no netting, no skipping)
        {"action": "SKIP",  "reason": ...}                 a late entry whose leader went back to flat
        {"action": "CLOSE", "side", "size", "price"}       full close of the engine's sleeve, always FIRST
        {"action": "ENTRY", "side", "size", "price",
         "oldest_entry_price", "newest_price"}             the single net order for the window
"""
from __future__ import annotations

POS_EPS = 1e-9


def _g(f, k, default=None):
    if isinstance(f, dict):
        return f.get(k, default)
    return getattr(f, k, default)


def _num(x, default=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def _signed(side: str, size: float) -> float:
    return abs(size) if str(side).upper() == "BUY" else -abs(size)


def _side_of(delta: float) -> str:
    return "BUY" if delta > 0 else "SELL"


def _start(f):
    s = _g(f, "startPosition")
    if s is None or (isinstance(s, str) and s.strip() == ""):
        return None
    return _num(s)


def plan_catchup(fills, held_before: float) -> dict:
    fills = list(fills or [])
    held = _num(held_before, 0.0)
    notes = []
    if not fills:
        return {"steps": [], "net": 0.0, "leader_after": held, "netting": False, "notes": ["no fills"]}

    # --- startPosition must be known on EVERY fill of the batch, or we cannot net or skip anything ---
    starts = [_start(f) for f in fills]
    if any(s is None for s in starts):
        steps = [{"action": "FILL", "side": str(_g(f, "side", "")).upper(), "size": abs(_num(_g(f, "size"), 0.0)),
                  "price": _num(_g(f, "price"), 0.0), "fill_ids": [str(_g(f, "id", ""))]} for f in fills]
        return {"steps": steps, "net": sum(_signed(_g(f, "side"), _num(_g(f, "size"))) for f in fills),
                "leader_after": held + sum(_signed(_g(f, "side"), _num(_g(f, "size"))) for f in fills),
                "netting": False,
                "notes": ["startPosition unknown on some fill: per-fill fallback, nothing skipped and nothing netted"]}

    # running position per fill: start -> end
    rows = []
    for f, s in zip(fills, starts):
        rows.append((f, s, s + _signed(_g(f, "side"), _num(_g(f, "size")))))

    # --- (a) the lowest index at which the leader is flat again; late ENTRIES up to there are skipped ---
    flat_at = -1
    for i, (_f, _s, e) in enumerate(rows):
        if abs(e) <= POS_EPS:
            flat_at = i
    skipped = set()
    if flat_at >= 0:
        for f, s, e in rows[:flat_at + 1]:
            opens = abs(e) > abs(s) + POS_EPS and s * e >= 0        # opened or added, same side
            if opens and _num(_g(f, "ts"), 0) < _num(_g(rows[flat_at][0], "ts"), 0):
                skipped.add(str(_g(f, "id", "")))
        if skipped:
            notes.append(f"leader returned to flat at fill {flat_at}: {len(skipped)} late entr(y/ies) skipped")

    net = sum(_signed(_g(f, "side"), _num(_g(f, "size"))) for f in fills)
    leader_after = held + net
    live = [f for f in fills if str(_g(f, "id", "")) not in skipped]
    steps = [{"action": "SKIP", "side": str(_g(f, "side", "")).upper(),
              "size": abs(_num(_g(f, "size"), 0.0)), "price": _num(_g(f, "price"), 0.0),
              "reason": "late entry; the leader was flat again later in this batch (engine never holds it)",
              "fill_ids": [str(_g(f, "id", ""))]} for f in fills if str(_g(f, "id", "")) in skipped]

    if not live:
        return {"steps": steps, "net": 0.0, "leader_after": 0.0, "netting": True,
                "notes": notes + ["net change over the window is flat: no order"]}

    oldest = _num(_g(live[0], "price"), 0.0)          # oldest entry price of the surviving window
    newest = _num(_g(live[-1], "price"), 0.0)         # newest price

    # the window nets to flat AND the engine held nothing: nothing to open, and the closing fill has nothing to
    # close (the engine never held it) -> skip the whole window
    if abs(held) <= POS_EPS and abs(leader_after) <= POS_EPS and abs(net) <= POS_EPS:
        for f in live:
            steps.append({"action": "SKIP", "side": str(_g(f, "side", "")).upper(),
                          "size": abs(_num(_g(f, "size"), 0.0)), "price": _num(_g(f, "price"), 0.0),
                          "reason": "engine held nothing and the leader is flat again: this fill has nothing to do",
                          "fill_ids": [str(_g(f, "id", ""))]})
        return {"steps": steps, "net": 0.0, "leader_after": 0.0, "netting": True,
                "notes": notes + ["leader flat at the end and the engine held nothing: whole window skipped"]}

    # --- (c) a net change that fully closes (or flips) the engine's sleeve: CLOSE first, then any remainder ---
    if abs(held) > POS_EPS and (held + net) * held <= 0:      # closes or crosses zero
        close_side = _side_of(-held)
        steps.append({"action": "CLOSE", "side": close_side, "size": abs(held), "price": newest,
                      "oldest_entry_price": oldest, "newest_price": newest, "fill_ids": [str(_g(f, "id", "")) for f in live]})
        remainder = held + net
        if abs(remainder) > POS_EPS:
            steps.append({"action": "ENTRY", "side": _side_of(remainder), "size": abs(remainder), "price": newest,
                          "oldest_entry_price": oldest, "newest_price": newest,
                          "fill_ids": [str(_g(f, "id", "")) for f in live]})
            notes.append("flip: sleeve closed first, then the remainder opened")
        else:
            notes.append("net change closed the sleeve exactly")
        return {"steps": steps, "net": net, "leader_after": leader_after, "netting": True, "notes": notes}

    # --- (b) one net order for the window ---
    if abs(net) > POS_EPS:
        steps.append({"action": "ENTRY", "side": _side_of(net), "size": abs(net), "price": newest,
                      "oldest_entry_price": oldest, "newest_price": newest,
                      "fill_ids": [str(_g(f, "id", "")) for f in live]})
    else:
        notes.append("net change over the window is flat: no order")
    return {"steps": steps, "net": net, "leader_after": leader_after, "netting": True, "notes": notes}
