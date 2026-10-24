# BUILD_IDENTITY

Identity is a commit SHA, never a directory name and never "the newest folder".

## Measured 2026-10-24 (raw, from git)

```
local HEAD .............. 572517fb60acbd64e45fa2510ea6417177016bd0  (2026-10-20 09:00:12 +0100)
remote refs/heads/main .. 5b975f0f258a996a8525d881283a52e8525aa38b
remote branch heads ..... 474
local branches .......... 38
```

Read that as: **the main checkout on this PC is 4 days behind origin/main.** Anything verified
in it describes `572517f`, not `5b975f0`. Do not cite a result from this tree as current.

Refresh before claiming identity:

```bash
git fetch origin
git ls-remote origin refs/heads/main      # the authoritative tip, straight from GitHub
git rev-parse HEAD                        # what this tree actually is
```

## What is running

The CORE is not built from this tree. Its identity is:

```
build sha ....... bf40a9d8bbb91348ebebf1b7d8d53ec15cbc7847
directory ....... C:/tmp/v31_bf40a9d-clean-20261024
env ............. HL_BUILD_SHA in the Core's own process environment
```

`HL_BUILD_SHA` is written into the Core at launch and reported in `live_service_state.json`.
If the env SHA and the directory's `git rev-parse HEAD` disagree, the running engine is not the
build it claims to be.

## Rules

- A release directory that is dirty against its commit is `IMMUTABILITY_BREACHED` — rebuild, do
  not patch in place.
- Never report a SHA you have not seen in `git ls-remote` output.
- 474 remote heads: a branch name is not identity either. Quote the SHA.
