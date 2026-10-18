# Authority preamble — paste at the top of every worker card

Short by design. The full rules live in `AGENTS_CONTEXT.md` at the repo root; this is the part every worker must
have in front of it.

---

**WHERE THE TRUTH IS**
- Register of record: `git show origin/cert/local-main-b142cf8:certification/certification_matrix.json` — **never**
  the working-tree copy.
- Current position: `STATE.md` at the repo root (regenerated, not hand-written).
- Do not quote `RUN_STATUS.md` or `run_status.csv`; they are derived and stale.
- If a number has no scope, it is not a fact.

**THE STANDARD — this is what demoted 301 of 579 rows**
PASS requires **both**:
1. **SPECIFICITY** — the check asserts something true of *this row* that would FAIL for a different row. Shared
   sweeps, carried boilerplate, substring searches and predicates that cannot fail are **not** evidence.
2. **NON-VACUITY** — a mutation control showing that row's check flips to FAIL when what it asserts is perturbed.

Row-keyed text alone is not enough. Six rows were rejected three times for exactly that.

**VERDICTS**
- `PASS` — both tests met, with the artifact cited by commit.
- `FAIL` — the code/product is wrong. Name the defect.
- `NOT_TESTED` — honest and frequently correct. Name precisely what is missing. **Never inflate.**
- A tool or environment failure is **not** a NOT_TESTED — fix the environment.

**EVIDENCE**
- Commit the artifact and PUSH it. Report `git ls-remote --heads origin <branch>` in your result.
- The artifact must exist in the branch you cite. A citation to a file your branch does not carry is a FAIL.
- Quote file:line for any claim about code.

**WHEN BLOCKED**
Escalate immediately — do not carry a block until the card dies. State the exact first failed edge and what you
need.

**WHEN YOU CANNOT DO SOMETHING**
Say so plainly with the attempt you made. Do not fabricate, do not approximate a number, do not pass a check you
could not run.

**CONTEXT PROTOCOL**
- Read `STATE.md` for current truth; read `RETRACTIONS.md` for withdrawn claims. The thread is history, not state.
- Recompute any count you are given from the file. If a stated count disagrees with the file, the file wins.
- `EVIDENCE/CONTEXT_PROTOCOL.md` has the details.
