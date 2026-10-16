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
| 7 | What are open human decisions? | **`EVIDENCE/OPEN_DECISIONS.md`** — the parked list of **23 OPEN decisions** (OD-02…OD-25) with owner + affected records, one line each. Source of truth: `certification/open_decisions.json`. **No card can clear one.** |
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

### MEASURED DISCREPANCY (2026-10-16) — the register and the summary disagree hugely

**CONTROLLER RULING (option 3, reconcile first): the 579-PASS matrix is UNPUSHED and UNVERIFIED.** `b142cf88`
does **not** exist on `origin/main` (`3ea99f4d`); the 579-PASS matrix has never left this PC.

**CONTROLLER CORRECTION (later): the provenance check must ALSO run against the published branch.**
My first sweep tested hashes with `git cat-file -t` against the **local** repo. The 4 dead hashes
(`2dfbd57`, `2dfbd571`, `5bda57be`, `5de53fa`, cited by 170 of 579 PASS rows) may be commits that exist
**only in the PC's local history** — the same cause as the missing matrix. So:

- re-run the resolve check against **`origin/cert/local-main-b142cf8` AFTER J15 publishes it**;
- hashes that resolve there **stay PASS**; hashes still unresolvable are **demoted** with reason
  "pinned hash unresolvable", listed;
- therefore **409 PASS is the FLOOR and 579 PASS is the CEILING — quote NEITHER until J15 lands.**

**Open decisions:** the controller will split them (engine-behaviour vs Boss-needed) after the speed
re-measure. **No action from me before that** — list parked at `EVIDENCE/OPEN_DECISIONS.md`.

**Quote that figure ONLY as:**

> **"579 / 790 PASS on PC-local main @ b142cf88, unpushed, not yet verified against shared origin."**

Do NOT publish it as the project position and do NOT call it the register of record until it is pushed and
reviewed. `t_70c69d13` (status regen) stays HELD.

**Row-by-row comparison (coordinator, read-only):**

| ref | rows | verdicts |
|---|---|---|
| PC-local `main` @ `b142cf88` (unpushed) | 790 | 579 PASS / 76 FAIL / 122 NT / 13 BLOCKED |
| `origin/main` @ `3ea99f4d` (shared) | 832 | **832 NOT_TESTED — no verdicts at all** |

- ids ONLY on PC-local: **0** · ids ONLY on origin: **42** · on both: **790** · verdict differs on **668**
- origin is a strict SUPERSET by id (+42 rows: `ENG-017/018/019`, `ORD-009/010`, `SET-009`, `UI-DIFF-01`, `UI-ROUTE-01..05`, …)
- so origin = requirements list extended to 832 with verdicts absent; PC-local = 790 rows WITH the work applied

**Do NOT quote `RUN_STATUS.md` either** — it is a DERIVED summary and stale (claims 6 PASS).

## Change log

| date | change |
|---|---|
| 2026-10-16 | created — single entry point so workers resolve uncertainty from the repo, not from card-local detail or memory |
