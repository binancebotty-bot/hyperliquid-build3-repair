
## DECISIONS — escalate, never assume. (operator, repeated, zero tolerance)

**Assume the operator is not here.** His presence is not a resource the loop may depend on; he appears when something is
broken, so any design that needs him in the loop has already failed.

Therefore: **anything requiring a decision is escalated, at the moment it is identified** — via a persistent question card
(`clarify`), and persisted to `EVIDENCE/DECISIONS.md` so it survives the session. Not held, not inferred, not resolved by
my own judgement, and never surfaced as a line inside a longer report where it can be missed.

Three specific failures this rule exists to prevent:

1. **Acting on a forbidden option because it was the only one that worked.** If every permitted lane is exhausted, the
   answer is a decision card, not silently using the forbidden one. "It was the only way to keep throughput" is a
   justification, never a permission.
2. **Reporting a violation as a fact.** Seeing `default: 7` in a lane table and reporting it as an observation instead of
   recognising it as a breach of a standing prohibition is the same error as committing it.
3. **Burning time on a decision I could have raised in one line.** Card prep, lane choice, provider authorisation, scope
   questions: escalate at the point of doubt, not after the cost is incurred.

Routing of questions: technical questions go to the controller; only business/human-authority questions (credentials,
policy, spend, LIVE) go to the operator. **Spend is always his.** A provider that bills is a spend decision even when the
technical choice is obvious.

## DELIVERY — a HEAD-only bundle has no base (found the hard way)

`git bundle create work.bundle HEAD` carries ONE ref. A card told to resolve `origin/main` or an earlier tested commit
from that bundle will correctly report the commit as absent and block — which is what happened to `t_03123cb4`: it blocked
on "the provided bundle lacks origin/main and the required tested commit 43731b4f", while that commit was on `origin/main`
and 40+ branches the whole time.

Rules:

1. **Bundles are coordinator recovery artifacts, not a worker's route to the base.** Workers reach the base by cloning:
   `git clone https://github.com/binancebotty-bot/hyperliquid-build3-repair repo`, no `--depth`, no `--filter`.
2. **When a bundle is written, include both refs:** `git bundle create work.bundle HEAD origin/main`.
3. **A commit missing from a bundle is not a missing commit.** Before blocking on an unreachable revision, check the
   repository: `git merge-base --is-ancestor <sha> origin/main`.
4. **Reviewers read the subject from the branch, not a bundle:** `git fetch origin <branch>` then
   `git show FETCH_HEAD:<path>`.

The general form: when a card blocks on "the artifact/commit is absent", verify against the remote first. Three blocks
today were phantom absences caused by an inadequate local instrument — a shallow clone, a dirty checkout, a single-ref
bundle — not by anything missing from the repository.

## DELIVERY — paths must be ABSOLUTE (cost two runs)

A relative delivery path is resolved against the worker's clone, not the folder intended, so `git bundle create` fails
creating its `.lock` in a directory that does not exist:

    cd <clone> && git bundle create "trading_stack/.../work.bundle" HEAD
      -> fatal: Unable to create '<clone>/trading_stack/.../work.bundle.lock': No such file or directory
    cd <clone> && git bundle create "C:/Users/wigmore/trading_stack/.../work.bundle" HEAD
      -> created, 3,176,871 bytes

Every card must carry the absolute form:

    D=C:/Users/wigmore/trading_stack/hl-build3-testnet-cert-evidence/worker_patches/<CARD_ID>

`D` begins with `C:/`. Not `trading_stack/`, not a path relative to the repo. This is on top of the earlier rule that the
drop folder is a plain directory with no git in it.
