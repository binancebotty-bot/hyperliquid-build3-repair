"""Record a post to the controller/Codex and whether a reply is still owed.

Rule this enforces: *a post with no one listening is not communication.* Every time something is posted to Claude or
Codex, the pending entry is written here. board_health.py reports any pending post whose watcher is not armed, so the
gap is visible instead of being discovered days later.

    python tools/cert/pending_post.py --add --ref "#81 6264733249" --note "register breakdown"
    python tools/cert/pending_post.py --reply "#81 6264733249"
    python tools/cert/pending_post.py --list
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

STATE = Path(r"C:/Users/wigmore/.hermes/state/controller_posts_pending.json")


def load() -> list[dict]:
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:
        return []


def save(items: list[dict]) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(items, indent=2), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--add", action="store_true")
    ap.add_argument("--ref", help="surface + id, e.g. '#81 6264733249'")
    ap.add_argument("--note", default="")
    ap.add_argument("--reply", help="mark this ref as answered")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()

    items = load()

    if a.add:
        if not a.ref:
            raise SystemExit("--add needs --ref")
        items.append({"ref": a.ref, "note": a.note, "posted_at": int(time.time()), "answered": False})
        save(items)
        print("  recorded pending post:", a.ref)

    if a.reply:
        hit = 0
        for it in items:
            if it["ref"] == a.reply:
                it["answered"] = True
                it["answered_at"] = int(time.time())
                hit += 1
        save(items)
        print("  marked answered:", a.reply, "(%d)" % hit)

    if a.list or (not a.add and not a.reply):
        open_items = [i for i in items if not i.get("answered")]
        print("  pending posts awaiting a reply: %d" % len(open_items))
        for i in open_items:
            age = int(time.time()) - i["posted_at"]
            print("    %-24s %4dm  %s" % (i["ref"], age // 60, i.get("note", "")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
