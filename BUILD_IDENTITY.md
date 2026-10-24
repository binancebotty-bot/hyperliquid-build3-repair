# BUILD_IDENTITY

Identity is a commit SHA. Not a directory name, not "the newest folder", not a snapshot of
this machine.

**This file deliberately holds NO live identity.** It records only the pinned build and where
the live identity is maintained. Copying current heads, branch counts or run paths here creates
a second, stale identity record - reviewers then read a run that no longer exists.

## Pinned build

| Role | Value |
|---|---|
| Pinned build SHA | `bf40a9d8bbb91348ebebf1b7d8d53ec15cbc7847` |
| Pinned by | `ops/testnet_launch_spec.json` -> `source_sha` (in the launcher checkout) |
| Pinned checkout branch | `claude/rw15-builder-empty` (holds that commit) |

A different SHA means a different build. Do not substitute a directory.

## Where the live identity is maintained

The live run identity - which checkout is running, which run-state folder, which SHA the engine
advertises - is maintained on the **controller's live page** for this lane:
GitHub issue #3 and PR #81 in `binancebotty-bot/hyperliquid-build3-repair`. Read it there; do
not mirror it into this repo.

## How to verify

```bash
git fetch origin
git ls-remote origin refs/heads/main      # authoritative tip, straight from GitHub
git rev-parse HEAD                        # what this tree actually is
```

Never report a SHA you have not seen in `git ls-remote` output.

## Not the product

The repository contains no live identity and no run state. In particular it does not contain,
and must not be extended with: current local/remote heads, branch counts, the running Core
directory, the run-state folder, process IDs, wallet addresses, or engine environment values.
