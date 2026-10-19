"""Refuse to let a controller post go unanswered. Exits NON-ZERO while a reply is outstanding.

Why this exists: "do not stand down after escalating" has been written in memory, in AGENTS.md and in skills for days and
has failed repeatedly because PROSE IS SKIPPABLE. This makes the state one command with an exit code I cannot talk past.

    python tools/cert/control_wait.py

    exit 0   every controller post has a reply        -> the turn may end
    exit 2   N post(s) still unanswered               -> DO NOT END THE TURN; keep working
    exit 3   state unknown (no token / check failed)  -> treat as unanswered; do not end the turn

Storage is ~/.hermes/state/controller_posts_pending.json, a LIST of entries:

    {"ref": "#81 6270956704", "note": "...", "posted_at": <epoch>, "answered": false}

`ref` carries the issue number and the comment id that was posted. An entry counts as answered when `answered` is true OR a
foreign comment newer than that id now exists on the issue.
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.request
from pathlib import Path

HOME = Path(r"C:/Users/wigmore/.hermes")
PENDING = HOME / "state" / "controller_posts_pending.json"
MINE = HOME / "state" / "my_comment_ids.json"
ENV = HOME / ".env"
REPO = "binancebotty-bot/hyperliquid-build3-repair"
REF_RE = re.compile(r"#(\d+)\s+(\d{6,})")


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


def newest_foreign(tok: str) -> dict[str, int]:
    mine = set(json.loads(MINE.read_text(encoding="utf-8"))) if MINE.is_file() else set()
    out = {}
    for num in (81, 3):
        base = f"https://api.github.com/repos/{REPO}/issues/{num}"
        meta = get(base, tok)
        pages = max(1, (int(meta.get("comments") or 0) + 99) // 100)
        data = get(f"{base}/comments?per_page=100&page={pages}", tok)
        foreign = [c for c in data if c["id"] not in mine]
        out[str(num)] = max([c["id"] for c in foreign], default=0)
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
        print("CONTROL_WAIT  REPLY_CONSUMED - no outstanding controller posts (%d total, all answered)" % len(posts))
        return 0

    tok = token()
    if not tok:
        print("CONTROL_WAIT  UNKNOWN - no GitHub token; cannot verify. Treat as unanswered.")
        return 3
    try:
        newest = newest_foreign(tok)
    except Exception as exc:
        print("CONTROL_WAIT  UNKNOWN - reply check failed: %r. Treat as unanswered." % (exc,))
        return 3

    outstanding = []
    now = time.time()
    for p in open_posts:
        m = REF_RE.search(str(p.get("ref", "")))
        issue, posted_id = (m.group(1), int(m.group(2))) if m else ("81", 0)
        nid = newest.get(issue, 0)
        if posted_id and nid > posted_id:
            p["answered"] = True
            p["answered_at"] = int(now)
            continue
        age = ""
        if p.get("posted_at"):
            age = "%dm" % int((now - float(p["posted_at"])) / 60)
        outstanding.append({"ref": p.get("ref"), "issue": issue, "posted": posted_id,
                            "newest": nid, "age": age, "note": p.get("note", "")})
    save(posts)

    if "--json" in sys.argv:
        print(json.dumps({"outstanding": outstanding}))
    elif not outstanding:
        print("CONTROL_WAIT  REPLY_CONSUMED - every open post now has a newer reply")
    else:
        print("CONTROL_WAIT  OUTSTANDING %d - DO NOT END THE TURN" % len(outstanding))
        for o in outstanding:
            print("   #%s %-30s posted=%s newest=%s age=%s" %
                  (o["issue"], str(o["ref"])[-11:], o["posted"], o["newest"], o["age"]))
            if o["note"]:
                print("      %s" % str(o["note"])[:110])
        print("")
        print("  Keep working: dispatch, verify an artifact, or repair a card body. A turn that ends here is the")
        print("  silent-drop failure the operator has flagged repeatedly.")
    return 0 if not outstanding else 2


if __name__ == "__main__":
    raise SystemExit(main())
