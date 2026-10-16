# AUTHORITY INDEX — where the truth lives

**You are not expected to hold project context in your head. If you are uncertain about ANY fact,
read it from the repo. Do not guess, and do not ask the coordinator for something the repo states.**

Every card should begin from this index. This repo is the single source of truth; the coordinator's
messages, card bodies, and your own assumptions all rank BELOW it.

## Read in this order when uncertain

| # | Question you have | Authoritative source |
|---|---|---|
| 1 | What must be true / what am I certifying? | `certification/MASTER_PRODUCT_INVARIANTS_AND_CERTIFICATION.md` |
| 2 | What is the exact requirement + its proof? | `certification/certification_matrix.json` **AT `main`** — read via `git show main:certification/certification_matrix.json`. **NEVER the working-tree copy** (see §Register of record) |
| 3 | How is evidence judged? What counts as PASS? | `OPERATING_PROTOCOL.md` + invariants §Evidence discipline |
| 4 | Which architecture is allowed / forbidden? | `ARCHITECTURE.md` (+ invariants §4 authority ranking) |
| 5 | What does a term/product concept mean? | `PRODUCT_SEMANTICS.md` |
| 6 | Where is the live surface / port / endpoint? | `EVIDENCE/CERT_ENVIRONMENT.md` |
| 7 | What are open human decisions? | `certification/open_decisions.json` |
| 8 | Current run status / what's already earned | `certification/RUN_STATUS.md`, `certification/run_results.json` |
| 9 | Testnet operation rules | `TESTNET_RUN_HANDOVER.md`, `CONTROL_STATE.json` |
| 10 | This project's binding rules for agents | `AGENTS.md` |

## The four non-negotiables (from OPERATING_PROTOCOL + invariants)

1. **PASS requires executed evidence on the exact commit under test.** Prose, a commit, a sent report,
   or a passing unit test is NOT a PASS. Unit/in-process tests go in `prior_evidence` and never set `result`.
2. **The oracle must be independent** — it reads the exchange or the OS and does NOT import engine or UI code.
3. **No substitution.** Do not evaluate a pinned source file and call it a runtime proof. If the real
   surface is genuinely absent, BLOCK with the exact probe — do not fabricate or approximate.
4. **Read the artifact, never the summary.** Verify claims against the committed object.

## Rules of uncertainty

- **A stable fact belongs in the repo, not in a card and not in anyone's memory.** If you find yourself
  needing a fact that is not written down anywhere, that is a defect: block or flag it so it gets
  recorded ONCE, in the right file above — then every future card inherits it.
- **Never invent a surface, port, commit, or path.** Take it from the index above, or block with the
  probe output that shows it missing.
- **When two sources disagree**, the ranking in invariant §4 wins — a later document supersedes an
  earlier one ONLY where it says so explicitly.
- **Do not ask the coordinator for anything this index already answers.** Ask only for genuine
  human-authority decisions (credentials, policy, LIVE/mainnet).

## Register of record — READ THIS BEFORE QUOTING ANY ROW STATUS

**The register of record is `certification/certification_matrix.json` AT `main`.** Read it as a
committed blob, never from a working tree:

```bash
git show main:certification/certification_matrix.json    # authoritative
```

**Why this rule exists.** On 2026-10-16 the working checkout sat on branch `oc/ledger-fix-v2`, whose
matrix disagrees with main:

| register | FAIL total | UI FAIL rows |
|---|---|---|
| `main` (`b142cf8`) — **of record** | **76** | **60** |
| `oc/ledger-fix-v2` (`4649d47`) — the checkout's branch | **0** | **0** |

A worker that read the local file saw "NOT_TESTED" for rows that are FAIL on main, and correctly
refused to proceed on a register that contradicted its card. The card premise (FAIL) was right; the
*local file* was the wrong source. Reading the working tree is how a certified row silently becomes
"unproven" or vice versa.

**Rules:**
- Quote row status ONLY from `git show main:<path>` (or another explicitly named ref), and STATE the
  ref you read in your evidence.
- A working-tree copy is never evidence of a row's status.
- If `main` and your checkout disagree, `main` wins — and say so in your report; do not silently
  reconcile.
- `RUN_STATUS.md` / `run_status.csv` are DERIVED summaries. When they disagree with `main`'s matrix,
  the matrix wins and the summary is stale.

## Change log

| date | change |
|---|---|
| 2026-10-16 | created — single entry point so workers resolve uncertainty from the repo, not from card-local detail or memory |
