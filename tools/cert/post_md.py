"""Post a markdown file to both channels. Reads the file from disk - never inline in a shell string, because markdown
backticks are command substitution to bash and are silently eaten, producing a post with every identifier stripped.
"""
import json
import sys
import urllib.request
from pathlib import Path

ENV = Path(r"C:/Users/wigmore/.hermes/.env")
REPO = "binancebotty-bot/hyperliquid-build3-repair"
CHANNELS = (81, 3)


def token():
    for line in ENV.read_text(encoding="utf-8", errors="ignore").splitlines():
        for key in ("GITHUB_TOKEN", "GITHUB_API_TOKEN"):
            if line.startswith(key + "="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("no token")


def main():
    if len(sys.argv) < 2:
        raise SystemExit("usage: post_md.py <file.md>")
    body = Path(sys.argv[1]).read_text(encoding="utf-8")
    if "`" in body:
        print("  (backticks present - safe, reading from disk)")
    tok = token()
    for num in CHANNELS:
        url = "https://api.github.com/repos/%s/issues/%d/comments" % (REPO, num)
        req = urllib.request.Request(
            url,
            data=json.dumps({"body": body}).encode(),
            headers={"Authorization": "Bearer " + tok,
                     "Accept": "application/vnd.github+json",
                     "Content-Type": "application/json",
                     "User-Agent": "hermes"},
            method="POST")
        r = json.load(urllib.request.urlopen(req, timeout=40))
        print("  posted #%d %s" % (num, r["id"]))


if __name__ == "__main__":
    main()
