#!/usr/bin/env python3
"""PreToolUse credit guard: keep Claude for project awareness, push the heavy lifting to Hermes.

Boss, 2026-11-08: delegate wherever possible, and enforce industry-standard credit savers in code.
This hook only blocks (exit 2) with a one-line reason that says what to do instead. It never
blocks polling (no_polling_guard.py owns that) and it never wedges a session: unreadable input
or an internal error allows the call.

Rules, each a pure check in decide():
  * Read: no whole-file read of a big file, slices capped, and at most 2 reads of an unchanged file.
  * Grep: content output needs head_limit.
  * Bash/PowerShell: gh api listings need since= or per_page= (high-watermark), recursive grep/rg
    needs head, and an identical read-only command is not re-run inside DEDUPE_WINDOW_S.
  * Write/Edit: large code edits are delegated to a Hermes seat; notes, memory and .md files are exempt.
The operator lifts every rule for a while by creating ~/.claude/delegation_override.json with
{"expires_epoch": <unix seconds>}. Claude must never create or edit that file.
"""
import json
import os
import re
import sys
import time

OVERRIDE_FILE = os.path.expanduser("~/.claude/delegation_override.json")
STATE_DIR = os.path.expanduser("~/.claude/state/credit_guard")

BIG_FILE_LINES = 800
MAX_READ_SLICE = 800
MAX_UNCHANGED_READS = 2
MAX_CLAUDE_EDIT_LINES = 120
DEDUPE_WINDOW_S = 300

_LIST_ENDPOINT = re.compile(r"/(comments|issues|pulls|commits|events|runs)(\?|\s|'|\"|$)")
_RECURSIVE_SEARCH = re.compile(r"(?<![\w-])(grep\s+-\w*r\w*|rg)\s")
_BOUNDED = re.compile(r"\|\s*head\b|\s-m\s*\d+|--max-count|\s-l\b|\s-c\b|Select-Object\s+-First")
_READ_ONLY_CMD = re.compile(r"^\s*(git\s+(log|show|diff|ls-remote|branch)|gh\s+api|rg|grep|ls|cat)\b")
_EXEMPT_PATH = re.compile(r"(?i)(/memory/|\.claude[/\\]projects|\.md$|\.txt$|[/\\]scratchpad[/\\])")


def _lines(path):
    try:
        if os.path.getsize(path) > 5_000_000:
            return 10**9
        with open(path, "rb") as f:
            return f.read().count(b"\n")
    except OSError:
        return 0


def _mtime(path):
    try:
        return os.path.getmtime(path)
    except OSError:
        return None


def _check_read(inp, state):
    path = inp.get("file_path")
    if not path:
        return None
    limit = inp.get("limit")
    if limit is not None and int(limit) > MAX_READ_SLICE:
        return "slice too large (limit %s): read a targeted slice of at most %d lines, or query graphify first" % (limit, MAX_READ_SLICE)
    if limit is None and _lines(path) > BIG_FILE_LINES:
        return "whole-file read of a big file: read a slice (offset and limit) or query graphify first"
    rec = state.setdefault("reads", {}).get(path)
    mtime = _mtime(path)
    if rec and rec.get("mtime") == mtime and rec.get("n", 0) >= MAX_UNCHANGED_READS:
        return "file already read %d times unchanged: use what you have, or read a different slice" % rec["n"]
    state["reads"][path] = {"mtime": mtime, "n": (rec["n"] + 1) if rec and rec.get("mtime") == mtime else 1}
    return None


def _check_command(cmd, state, now):
    if _GIT_COMMIT.search(cmd):
        return _evidence_gap(state, now, "commit")
    if (re.search(r"\bgh\s+api\b", cmd) and not _GH_WRITE.search(cmd) and _LIST_ENDPOINT.search(cmd)
            and "since=" not in cmd and "per_page=" not in cmd):
        return "unbounded gh api listing: use a high-watermark (since=<last seen> and per_page=<small>) or fetch one item by id"
    if _RECURSIVE_SEARCH.search(cmd) and not _BOUNDED.search(cmd):
        return "recursive search without a bound: pipe to head, add -m, or query graphify"
    if _READ_ONLY_CMD.match(cmd):
        seen = state.setdefault("cmds", {})
        last = seen.get(cmd)
        if last is not None and now - last < DEDUPE_WINDOW_S:
            return "repeated read-only command within %ds: reuse the earlier result" % DEDUPE_WINDOW_S
        seen[cmd] = now
    return None


GRAPHIFY_TTL_S = 7200
PONYTAIL_TTL_S = 1200
PONYTAIL_RULES = "~/.hermes/plugins/ponytail/AGENTS.md"  # the plugin Hermes loads; docs/ponytail/ holds a pinned copy
_CODE_EXT = re.compile(r"(?i)\.(py|js|ts|tsx|jsx|ps1|sh|bat|go|rs|java|c|cpp|h|cs|rb|php|sql|ipynb)$")
_GRAPHIFY_CMD = re.compile(r"(?<![\w-])graphify\s+(query|explain|path|update)\b")
_PONYTAIL_NOTE = re.compile(r"PONYTAIL:\s*(\S.{9,})")
_PONYTAIL_RULES_PATH = re.compile(r"(?i)ponytail.*(AGENTS|SKILL)[^/\\]*\.md$")


def _record_evidence(tool, inp, state, now):
    """Remember what this session has consulted: graphify, the ponytail rules, and a ponytail plan note."""
    cmd = str(inp.get("command", "")) if tool in ("Bash", "PowerShell") else ""
    paths = " ".join(str(inp.get(k, "")) for k in ("file_path", "path"))
    if _GRAPHIFY_CMD.search(cmd) or (tool in ("Read", "Grep", "Glob") and "graphify-out" in paths):
        state["graphify_at"] = now
    if tool == "Read" and _PONYTAIL_RULES_PATH.search(str(inp.get("file_path", ""))):
        state["ponytail_rules_at"] = now
    if _PONYTAIL_NOTE.search(cmd):
        state["ponytail_at"] = now


_GH_WRITE = re.compile(r"\s(-X|--method)\s+(POST|PATCH|PUT|DELETE)\b|\s-[fF]\s|\s--(field|raw-field|input)\b", re.I)
_GIT_COMMIT = re.compile(r"(?:^|[;&|]\s*)git\s+(?:-C\s+\S+\s+)?commit\b")


def _evidence_gap(state, now, what):
    """The three things every coding action needs: a graphify lookup, the ponytail rules, a ponytail plan."""
    if now - state.get("graphify_at", -10**9) >= GRAPHIFY_TTL_S:
        return "%s without a graphify lookup: run graphify query/explain (or read graphify-out) first" % what
    if now - state.get("ponytail_rules_at", -10**9) >= PONYTAIL_TTL_S:
        return "%s without the ponytail rules: read %s first (smallest complete change)" % (what, PONYTAIL_RULES)
    if now - state.get("ponytail_at", -10**9) >= PONYTAIL_TTL_S:
        return ("%s without a ponytail plan: record the smallest complete change with "
                "echo \"PONYTAIL: <callers and tests touched, what is skipped>\"" % what)
    return None


def _repo_root(path):
    cur = os.path.dirname(os.path.abspath(path))
    while True:
        if os.path.exists(os.path.join(cur, ".git")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            return None
        cur = parent


def _check_code_discipline(path, state, now):
    if not _CODE_EXT.search(path) or _EXEMPT_PATH.search(path):
        return None
    root = _repo_root(path)
    if root is None:
        return None  # not inside a repo: nothing to map
    fresh_graph = now - state.get("graphify_at", -10**9) < GRAPHIFY_TTL_S
    if not os.path.isdir(os.path.join(root, "graphify-out")) and not fresh_graph:
        return ("no graphify map for this repo: generate it first (delegate to the Runner), then run "
                "graphify query before editing code")
    return _evidence_gap(state, now, "code edit")


_PROTECTED = re.compile(r"(?i)(credit_guard\.py|hook_selfcheck\.py|[\\/]\.claude[\\/]settings(\.local)?\.json|"
                        r"managed-settings\.json|delegation_override\.json)")
_SHELL_WRITE = re.compile(r"(?i)(\bsed\s+-i|>\s*\S|\btee\b|\bset-content\b|\bout-file\b|\badd-content\b|\bcp\b|\bmv\b|"
                          r"\bcopy\b|\bmove\b|\brm\b|\bdel\b|\bremove-item\b|\bopen\([^)]*['\"][wa]|write_text|\bunlink\b)")


def _check_protected(tool, inp):
    """The agent must not edit the hook, its self-check, the settings that register it, or the override."""
    why = "protected hook or settings file: only the operator changes it (delegation_override.json lifts this)"
    if tool in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        return why if _PROTECTED.search(str(inp.get("file_path") or inp.get("notebook_path") or "")) else None
    if tool in ("Bash", "PowerShell"):
        cmd = str(inp.get("command", ""))
        return why if _PROTECTED.search(cmd) and _SHELL_WRITE.search(cmd) else None
    return None


def _check_edit(tool, inp, state, now):
    path = str(inp.get("file_path") or inp.get("notebook_path") or "")
    if _EXEMPT_PATH.search(path):
        return None
    text = inp.get("content") if tool == "Write" else (inp.get("new_source") if tool == "NotebookEdit" else inp.get("new_string"))
    if text and str(text).count("\n") + 1 > MAX_CLAUDE_EDIT_LINES:
        return ("large code edit (over %d lines): delegate it to a Hermes seat or free runner and review the result; "
                "do it directly only if they are unavailable and the task would stall" % MAX_CLAUDE_EDIT_LINES)
    return _check_code_discipline(path, state, now)


def decide(event, state, now=None, override=None):
    """Return a block reason, or None to allow. Mutates `state` (the per-session counters)."""
    if override is None:
        override = _override_active()
    if override:
        return None
    now = time.time() if now is None else now
    tool = event.get("tool_name", "") or ""
    inp = event.get("tool_input") or {}
    try:
        _record_evidence(tool, inp, state, now)
        protected = _check_protected(tool, inp)
        if protected:
            return protected
        if tool == "Read":
            return _check_read(inp, state)
        if tool == "Grep" and inp.get("output_mode") == "content" and not inp.get("head_limit"):
            return "content search without head_limit: add head_limit (20 to 50) or use files_with_matches"
        if tool in ("Bash", "PowerShell"):
            return _check_command(str(inp.get("command", "")), state, now)
        if tool in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
            return _check_edit(tool, inp, state, now)
    except (TypeError, ValueError):
        return None
    return None


def _override_active():
    try:
        with open(OVERRIDE_FILE, encoding="utf-8") as f:
            return float(json.load(f).get("expires_epoch", 0)) > time.time()
    except (OSError, ValueError, TypeError):
        return False


def _state_path(session_id):
    safe = re.sub(r"[^\w.-]", "_", session_id or "nosession")
    return os.path.join(STATE_DIR, safe + ".json")


USAGE_LOG = os.path.join(STATE_DIR, "usage.jsonl")


def log_usage(event, reason, path=None, now=None):
    """Append one line per guarded call: when, session, tool, allow/block and the rule that fired.
    Content is never logged, only the tool name and a short reason, so the log is safe to share."""
    entry = {"ts": round(time.time() if now is None else now, 1), "session": (event.get("session_id") or "")[:12],
             "tool": event.get("tool_name", ""), "decision": "block" if reason else "allow",
             "rule": (reason or "").split(":")[0][:60]}
    try:
        target = path or USAGE_LOG
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except (OSError, ValueError):
        pass


def main():
    try:
        event = json.load(sys.stdin)
    except ValueError:
        sys.exit(0)
    path = _state_path(event.get("session_id", ""))
    try:
        with open(path, encoding="utf-8") as f:
            state = json.load(f)
    except (OSError, ValueError):
        state = {}
    reason = decide(event, state)
    log_usage(event, reason)
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f)
    except OSError:
        pass
    if reason:
        sys.stderr.write("BLOCKED by credit_guard: %s. (Boss, 2026-11-08: delegate to Hermes, save credits. "
                         "Only the operator lifts this, via ~/.claude/delegation_override.json.)\n" % reason)
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
