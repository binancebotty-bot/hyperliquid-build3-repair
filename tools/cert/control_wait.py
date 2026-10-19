"""Have I READ everything the controller has said? Exit non-zero if not.

The previous version asked the wrong question: "does any of my posts lack a newer reply?" That missed the case that
actually keeps happening - the controller replies, I keep working, and I never READ the reply. Nothing looked outstanding
because no post of mine was newer than it.

The right question is a **read watermark**: the highest comment id I have actually consumed and acted on. Anything newer on
either issue is unread, full stop.

    python tools/cert/control_wait.py

    exit 0   nothing unread      -> the turn may end
    exit 2   unread replies      -> DO NOT END THE TURN; read them and act
    exit 3   state unknown       -> treat as unread

    python tools/cert/control_wait.py --consume 6271553509   mark one comment read
    python tools/cert/control_wait.py --consume-all          mark everything current as read
    python tools/cert/control_wait.py --list                 show the unread ones with their text

Watermark lives at ~/.hermes/state/controller_read_watermark.json -> {"issue_81": <id>, "issue_3": <id>}.
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

HOME = Path(r"C:/Users/wigmore/.hermes")
STATE = HOME / "state"
MARK = STATE / "controller_read_watermark.json"
MINE = STATE / "my_comment_ids.json"
ENV = HOME / ".env"
REPO = "binancebotty-bot/hyperliquid-build3-repair"
ISSUES = (81, 3)


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


def load_marks() -> dict:
    if MARK.is_file():
        try:
            return json.loads(MARK.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_marks(m: dict) -> None:
    MARK.parent.mkdir(parents=True, exist_ok=True)
    MARK.write_text(json.dumps(m, indent=1), encoding="utf-8")


def foreign_comments(tok: str) -> dict[int, list[dict]]:
    mine = set(json.loads(MINE.read_text(encoding="utf-8"))) if MINE.is_file() else set()
    out: dict[int, list[dict]] = {}
    for num in ISSUES:
        base = f"https://api.github.com/repos/{REPO}/issues/{num}"
        meta = get(base, tok)
        pages = max(1, (int(meta.get("comments") or 0) + 99) // 100)
        data = get(f"{base}/comments?per_page=100&page={pages}", tok)
        f = [c for c in data if c["id"] not in mine]
        f.sort(key=lambda c: c["id"])
        out[num] = f
    return out


def main() -> int:
    args = sys.argv[1:]
    marks = load_marks()
    tok = token()

    if "--consume" in args:
        cid = int(args[args.index("--consume") + 1])
        for num in ISSUES:
            cur = int(marks.get("issue_%d" % num, 0))
            if cid > cur and (not tok or True):
                # only advance the issue the id belongs to; safest is to advance both up to cid
                marks["issue_%d" % num] = max(cur, cid)
        save_marks(marks)
        print("consumed up to %d" % cid)
        return 0

    if not tok:
        print("CONTROL_WAIT  UNKNOWN - no token; treat as unread")
        return 3
    try:
        comments = foreign_comments(tok)
    except Exception as exc:
        print("CONTROL_WAIT  UNKNOWN - check failed: %r" % (exc,))
        return 3

    latest = {num: (max([c["id"] for c in comments[num]], default=0)) for num in ISSUES}

    if "--consume-all" in args:
        for num in ISSUES:
            marks["issue_%d" % num] = latest[num]
        save_marks(marks)
        print("consumed all: %s" % marks)
        return 0

    unread = []
    for num in ISSUES:
        wm = int(marks.get("issue_%d" % num, 0))
        unread.extend([c for c in comments[num] if c["id"] > wm])

    if "--list" in args:
        for c in sorted(unread, key=lambda x: x["id"]):
            print("=== %s  %s" % (c["id"], c["created_at"]))
            print(c["body"][:1200])
            print()
        return 0 if not unread else 2

    if not unread:
        print("CONTROL_WAIT  ALL_READ - watermark %s, newest %s" % (marks, latest))
        return 0

    print("CONTROL_WAIT  UNREAD %d - DO NOT END THE TURN" % len(unread))
    for c in sorted(unread, key=lambda x: x["id"]):
        body = " ".join(str(c["body"]).split())
        print("   %s  %s" % (c["id"], body[:120]))
    print("")
    print("  Read them:   python tools/cert/control_wait.py --list")
    print("  Then act, and mark read:  --consume <id>")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
