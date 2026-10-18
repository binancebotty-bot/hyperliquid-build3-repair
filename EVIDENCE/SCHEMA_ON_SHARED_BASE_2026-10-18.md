# UI_CERT_ARTIFACT_SCHEMA placed on the shared base

**Date:** 2026-10-18
**Cards:** `t_45c1e992` (place), `t_bd28ad9b` (review)

## Defect
`EVIDENCE/UI_CERT_ARTIFACT_SCHEMA.md` is cited by UI certification evidence across many cards, but existed
on only two origin refs — a single task branch and one cert branch. It was absent from `origin/main` and from
`origin/cert/local-main-b142cf8`.

Any card branched from anywhere else cited a file its tree did not contain. Reviewers correctly failed it.
Three cards were already rejected for this (`t_baa15aad`, `t_0f4bab8e`, the merge-ready branch) and each was
"fixed" by re-pointing that single card's citation — which did not stop the next one.

## Fix
Placed byte-identical on all three refs:
- `origin/main` — commit `2a2c241`
- `origin/cert/local-main-b142cf8` — commit `f4ee2bb`
- `origin/hermes/re-earn-ui-lcc-hdr-btn-card-graph-t_b11aec53` — source

## Verification
Two independent checks, same result:

    sha256 5a555bd82e9b3be580ca0bf74715afdec75cfcb3e2c426f0b9155752027cd93f
    present and identical on all three refs

Coordinator verified via `git show <ref>:<path> | sha256sum`; review card `t_bd28ad9b` verified the same
independently and returned PASS.

## Lesson
A missing shared file is a **class** defect, not a per-card one. The tell is that you are fixing the same thing
a second time. Fix at the base so every future branch inherits it.
