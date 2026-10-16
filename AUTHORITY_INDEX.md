# AUTHORITY INDEX — where the truth lives

**You are not expected to hold project context in your head. If you are uncertain about ANY fact,
read it from the repo. Do not guess, and do not ask the coordinator for something the repo states.**

Every card should begin from this index. This repo is the single source of truth; the coordinator's
messages, card bodies, and your own assumptions all rank BELOW it.

## Read in this order when uncertain

| # | Question you have | Authoritative source |
|---|---|---|
| 1 | What must be true / what am I certifying? | `certification/MASTER_PRODUCT_INVARIANTS_AND_CERTIFICATION.md` |
| 2 | What is the exact requirement + its proof? | `certification/certification_matrix.json` (the 832-record register) — read the ACTUAL record for your row id |
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

## Change log

| date | change |
|---|---|
| 2026-10-16 | created — single entry point so workers resolve uncertainty from the repo, not from card-local detail or memory |
