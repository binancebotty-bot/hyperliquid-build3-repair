# CONTEXT PROTOCOL — read this before consuming anything else

**For: Claude, GPT/controller, Codex, and any agent drafted into this project.**

## The rule

**Consume the high-watermark file, not the thread.** The thread is ordered by *when something was said*. The
high-watermark is ordered by *whether it is still true*. They are different documents and only one of them is
current.

| you want | read | do NOT read |
|---|---|---|
| what is true right now | **`STATE.md`** at the repo root | the comment tail |
| the rules | `AGENTS_CONTEXT.md` | — |
| claims we withdrew | `RETRACTIONS.md` | — |
| what happened, in order | issue #3 (history only) | — |

Read `STATE.md` first, every time. Go deeper **only when you need a specific fact** that `STATE.md` doesn't carry,
and then go to the named ref/commit, not to the gossip.

## Regenerate rather than trust

`STATE.md` is **generated** from the board and the committed register:

    python tools/cert/gen_state.py --write

If you suspect it is stale, run that. It cannot drift, because nobody types facts into it.

## Why this exists

The register's PASS count was quoted as **579** for hours after it had been disproven. It was corrected five times
in comments — each correction deeper in the thread than the original claim, so anyone tail-reading saw the wrong
number and the right one was invisible. The current true figure is **74 audit-verified**.

**A number without its scope is a false claim.** "579 PASS" is meaningless without "on `cert/local-main-b142cf8`,
of which 74 are audit-verified." Quote the scope or don't quote the number.

## The three things most likely to be wrong in a message you receive

1. **A count.** Recompute it from the file. If a stated count disagrees with the file, the file wins.
2. **A citation.** Check the artifact exists *on the ref being cited*. Three cards were rejected for citing files
   their branch did not carry.
3. **A "verified".** Ask for the ref, the commit and the sha. "Verified" without those is an assertion.

## One durable file per fact

If it matters tomorrow, it goes in a file or an issue comment — not only in chat. Chat is transport, not storage.
When something you previously stated is now false, **write the retraction** into `RETRACTIONS.md`; do not merely
say something different later. Silence is not a retraction, and a reader has no way to tell a dead claim from a
live one.

## Current high-watermark, so you are not blind until you fetch it

- Register of record: `origin/cert/local-main-b142cf8` — **790 rows**: 579 PASS claimed / 76 FAIL / 13 BLOCKED /
  122 NOT_TESTED; 668 rows carry an `evidence_ref`.
- **74 rows are audit-verified. That is the number to quote.** 505 demoted or unaudited.
- `origin/main` is a **stub**: 832 rows, all NOT_TESTED, **zero** evidence refs. Claude has ruled the register be
  merged to main with ENG-INV-02 recorded as **FAIL**.
- **Zero UI rows are certified.** UI evidence needs rebuilding, not auditing.
- `eb91d9a`: OFF-to-ON TOCTOU can silently consume a fill. Fix card requires a dynamic two-thread test that fails
  on `eb91d9a` and passes after.
