"""Refuse to let a controller post go unanswered. Exits NON-ZERO while a reply is outstanding.

Why this exists: "do not stand down after escalating" has been in memory, AGENTS.md and skills for days and has failed
repeatedly because PROSE IS SKIPPABLE. This makes the state one command with an exit code that cannot be talked past.

    python tools/cert/control_wait.py

    exit 0   every controller post has a reply        -> the turn may end
    exit 2   N post(s) still unanswered               -> DO NOT END THE TURN; keep working
    exit 3   state unknown (no token / check failed)  -> treat as unanswered; do not end the turn

Comparison is by TIMESTAMP, not id: pending entries record `posted_at` (epoch), and an entry counts as answered when a
foreign comment exists on that issue with created_at later than that epoch. Comment ids are not stored by
`pending_post.py --add`, so comparing ids silently reports posted=0 for every row and proves nothing.
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HOME = Path(r"C:/Users/wigmore/.hermes")
PENDING = HOME / "state" / "controller_posts_pending.json"
MINE = HOME / "state" / "my_comment_ids.json"
ENV = HOME / ".env"
REPO = "binancebotty-bot/hyperliquid-build3-repair"
REF_RE = re.compile(r"#(\d+)")


def token() -> str | None:
    for line in ENV.read_text(encoding="utf-8", errors="ignore").splitlines():
        for k in ("GITHUB_TOKEN", "GITHUB_API_TOKEN"):
            if line.startswith(k + "="):
                return line.split("=", 1)[1].strip().strip('"')
    return None


def get(url: str, tok: str):
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + tok,
                                               "Accept": "application/vnd.github+json",
                                               "User-Agent": "hermes-control-wait"})
    return json.load(urllib.request.urlopen(req, timeout=25))


def newest_foreign_ts(tok: str) -> dict[str, float]:
    mine = set(json.loads(MINE.read_text(encoding="utf-8"))) if MINE.is_file() else set()
    out = {}
    for num in (81, 3):
        base = f"https://api.github.com/repos/{REPO}/issues/{num}"
        meta = get(base, tok)
        pages = max(1, (int(meta.get("comments") or 0) + 99) // 100)
        data = get(f"{base}/comments?per_page=100&page={pages}", tok)
        newest = 0.0
        for c in data:
            if c["id"] in mine:
                continue
            try:
                ts = datetime.strptime(c["created_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()
            except Exception:
                continue
            newest = max(newest, ts)
        out[str(num)] = newest
    return out


def load() -> list[dict]:
    if not PENDING.is_file():
        return []
    d = json.loads(PENDING.read_text(encoding="utf-8"))
    if isinstance(d, dict):
        return d.get("posts", [])
    return d if isinstance(d, list) else []


def save(posts: list[dict]) -> None:
    PENDING.write_text(json.dumps(posts, indent=1), encoding="utf-8")


def main() -> int:
    posts = load()

    if "--close" in sys.argv:
        needle = sys.argv[sys.argv.index("--close") + 1]
        hit = 0
        for p in posts:
            if needle in str(p.get("ref", "")) and not p.get("answered"):
                p["answered"] = True
                p["answered_at"] = int(time.time())
                hit += 1
        save(posts)
        print("closed %d entr(ies) matching %s" % (hit, needle))
        return 0

    open_posts = [p for p in posts if not p.get("answered")]
    if not open_posts:
        print("CONTROL_WAIT  REPLY_CONSUMED - all %d controller posts answered" % len(posts))
        return 0

    tok = token()
    if not tok:
        print("CONTROL_WAIT  UNKNOWN - no GitHub token; treat as unanswered")
        return 3
    try:
        newest = newest_foreign_ts(tok)
    except Exception as exc:
        print("CONTROL_WAIT  UNKNOWN - reply check failed: %r; treat as unanswered" % (exc,))
        return 3

    now = time.time()
    outstanding = []
    for p in open_posts:
        m = REF_RE.search(str(p.get("ref", "")))
        issue = m.group(1) if m else "81"
        posted_at = float(p.get("posted_at") or 0)
        if newest.get(issue, 0.0) > posted_at:
            p["answered"] = True
            p["answered_at"] = int(now)
            continue
        outstanding.append({"ref": p.get("ref"), "issue": issue,
                            "age": "%dm" % int((now - posted_at) / 60) if posted_at else "?",
                            "note": p.get("note", "")})
    save(posts)

    if "--json" in sys.argv:
        print(json.dumps({"outstanding": outstanding}))
    elif not outstanding:
        print("CONTROL_WAIT  REPLY_CONSUMED - every open post now has a newer reply")
    else:
        print("CONTROL_WAIT  OUTSTANDING %d - DO NOT END THE TURN" % len(outstanding))
        for o in outstanding:
            print("   #%s age=%-5s %s" % (o["issue"], o["age"], str(o["ref"])[:46]))
            if o["note"]:
                print("      %s" % str(o["note"])[:110])
        print("")
        print("  Keep working: dispatch, verify an artifact, repair a card. Ending the turn here is the silent-drop")
        print("  failure the operator has flagged repeatedly.")
    return 0 if not outstanding else 2


if __name__ == "__main__":
    raise SystemExit(main())
