# Build-3 reporting destinations (operator directive 2026-10-16)

Durable, in-repo record so it survives a restart.

## Rule

**Every JOB result and every ACTION RESULT is posted as a comment on BOTH:**

1. `PR #81` of `binancebotty-bot/hyperliquid-build3-repair`
   — "Batch tracking: post Codex/Hermes results here (do not merge)"
2. `issue #3` of `binancebotty-bot/hyperliquid-build3-repair`

One body, two targets. PR #81 is a tracking surface only — **do not merge it**.

## Why

The operator reads the batch surface (PR #81) to see Codex + Hermes results side by side,
and issue #3 is the control surface where the controller correlates the cycle.
Posting to only one drops the loop for the other reader.

## Mechanics (no `gh` CLI on this machine)

Use the credential-manager client at
`C:/Users/wigmore/.hermes/scripts/control_loop/gh_issue.py` with `REPO` overridden:

```python
import gh_issue as g
g.REPO = 'binancebotty-bot/hyperliquid-build3-repair'
body = open(path, encoding='utf-8').read()
g._post(g.API + '/repos/' + g.REPO + '/issues/3/comments',  {'body': body})   # issue 3
g._post(g.API + '/repos/' + g.REPO + '/issues/81/comments', {'body': body})  # PR 81
```

PR comments use the same issues-comments endpoint.

## Standing exceptions

- Routine AWAITING_CONTROLLER_RULING progress is not a JOB result — it does not need the
  double post; it goes to the control mailbox per the normal convention.
- Never print or commit credentials; `gh_issue.py` reads them from the Windows credential manager.
