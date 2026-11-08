#!/usr/bin/env python3
"""Fail loudly when the credit_guard hook is not active in a Claude session.

Run it at session start (SessionStart hook) or by hand. It checks that the user-level settings.json
registers credit_guard.py under hooks.PreToolUse for the tools that matter (Edit, Write, Bash), that the
script exists, and that it still blocks a known-bad call (exit 2). Exit 0 and one OK line, or exit 1 and
a CREDIT_GUARD BROKEN banner that names every problem.
"""
import json
import os
import subprocess
import sys

DEFAULT_SETTINGS = os.path.expanduser("~/.claude/settings.json")
DEFAULT_HOOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "credit_guard.py")
NEEDED_TOOLS = ("Edit", "Write", "Bash")
_BAD_CALL = {"session_id": "selfcheck", "tool_name": "Grep",
             "tool_input": {"pattern": "x", "output_mode": "content"}}


def problems(settings_path=DEFAULT_SETTINGS, hook_path=DEFAULT_HOOK):
    try:
        with open(settings_path, encoding="utf-8") as f:
            cfg = json.load(f)
    except (OSError, ValueError) as exc:
        return ["cannot read %s: %s" % (settings_path, exc)]
    out = []
    entries = [e for e in (cfg.get("hooks", {}).get("PreToolUse") or [])
               if any("credit_guard.py" in str(h.get("command", "")) for h in e.get("hooks", []))]
    if not entries:
        out.append("credit_guard.py is not registered under hooks.PreToolUse in %s" % settings_path)
    for e in entries:
        matcher = e.get("matcher", "")
        tools = matcher.split("|")
        gaps = [t for t in NEEDED_TOOLS if t not in tools and matcher not in (".*", ".+")]
        if gaps:
            out.append("matcher '%s' does not cover %s" % (matcher, ", ".join(gaps)))
    if not os.path.isfile(hook_path):
        out.append("hook script missing: %s" % hook_path)
    else:
        try:
            run = subprocess.run([sys.executable, "-I", hook_path], input=json.dumps(_BAD_CALL),
                                 capture_output=True, text=True, timeout=20)
            if run.returncode != 2:
                out.append("hook does not block a known-bad call (exit %s)" % run.returncode)
        except (OSError, subprocess.SubprocessError) as exc:
            out.append("hook failed to run: %s" % exc)
    return out


def main():
    found = problems()
    if found:
        sys.stdout.write("CREDIT_GUARD BROKEN: every coding action in this session is UNGUARDED.\n  - "
                         + "\n  - ".join(found) + "\n")
        sys.exit(1)
    sys.stdout.write("CREDIT_GUARD OK: graphify and ponytail are enforced on edits and commits.\n")


if __name__ == "__main__":
    main()
