# AGENTS_CONTEXT — standing rules for every agent in this lane

**Read this first. It is short on purpose.** It carries the rules that never change; the current facts live in
`STATE.md`; things we believed and then disproved live in `RETRACTIONS.md`.

Applies to: Hermes, Claude, GPT/controller, Codex, and any agent drafted in later.

---

## 1. Where the truth lives

| question | file | who writes it | how it changes |
|---|---|---|---|
| What are the rules? | `AGENTS_CONTEXT.md` (this) | nobody without agreement | rarely |
| What is true *right now*? | `STATE.md` | the coordinator | **rewritten** in place |
| What did we stop believing? | `RETRACTIONS.md` | whoever retracts | append-only |
| What happened, in order? | GitHub issue #3 | the coordinator | append-only |
| What is the work? | the kanban board | the coordinator | live |

**`STATE.md` is the high-water mark done correctly.** It is not a log and not a summary — it is *the current answer*,
overwritten each time the answer changes. If you want to know what's true, read `STATE.md`. If it disagrees with
anything in the issue thread, **`STATE.md` wins** and the thread is history.

**Never treat a long comment thread as current state.** A thread is ordered by *when something was said*, not by
*whether it is still true*. That is exactly how the 579 figure outlived its own refutation.

---

## 2. Rules for claims (the expensive lessons)

1. **A claim is retired by writing it down, not by saying something else later.** Every withdrawn claim goes in
   `RETRACTIONS.md` with what replaced it. Silence is not a retraction.
2. **Quote a number with its scope or don't quote it.** "579 PASS" is meaningless without "on cert/local-main,
   of which 74 are audit-verified." A number without its scope is a false claim waiting to happen.
3. **Evidence is a committed object, not a summary.** Read the artifact. A worker's completion message is a
   *claim*; the committed JSON is the evidence. Never accept the first as the second.
4. **"Green" needs a negative control.** A check that passes everywhere proves nothing. A test that passes both
   before and after a fix is not a test.
5. **Run the two-run control before reporting a finding.** Scrubbed environment vs inherited, or the finding may
   be the instrument, not the product.
6. **State the ref you read.** `git show <ref>:<path>`, not the working tree. The checkout is not the truth; the
   committed object is.

---

## 3. Rules for communication

1. **One durable file per fact.** If it matters tomorrow, it goes in a file or an issue — never only in chat.
2. **Batch, don't stream.** Deposit findings when a batch is complete, not per-item. Issue #3 has 1,192 comments
   because of streaming.
3. **Say which ref, which commit, which file.** "I verified it" is not verification; "verified at `origin/main`
   `2a2c241`, sha256 `5a555bd8…`" is.
4. **Correct in place.** When you were wrong, edit `STATE.md` and add to `RETRACTIONS.md` — don't post a
   correction deep in a thread where only a tail-reader will ever see it.
5. **No acknowledgements, no routine status.** Only decisions, blocks, corrections and completed evidence.
6. **Never synthesise another agent's position.** Quote them or don't represent them.

---

## 4. Rules for the register

1. **`certification/certification_matrix.json` at a named ref is the register of record.** Never the working-tree
   copy; the checkout sits on a divergent branch.
2. **`origin/main` may be a stub.** Verify before quoting: check row count, verdict distribution and
   `evidence_ref` presence. A register with zero evidence refs is not a register.
3. **`RUN_STATUS.md` / `run_status.csv` are derived and stale.** Never quote them as the position.
4. **A demotion is not a failure** — it's the audit working. Report it as a finding.
5. **NOT_TESTED is a valid, honest verdict.** Never inflate it to PASS, never record a tool failure as NOT_TESTED
   (that's an environment bug, fix it).

---

## 5. Rules for work

1. **Card bodies must be self-contained** — paths, refs, clone location, the standard, and where evidence lives.
   "Read the artifact" is not an instruction.
2. **A reviewer must not be the author.** A card approving its own work is not a review.
3. **On FAIL, raise a REDO card** on a different lane, parented to the original, plus a reviewer for it. Rejection
   does not self-requeue.
4. **Block → escalate immediately.** A block you cannot resolve is escalated the moment you know, not carried
   until the card dies.
5. **Fix the class, not the instance.** The tell that you're patching a symptom: you are fixing the same thing a
   second time. (Schema on one branch. Three cards rejected. Each fixed per-card.)
6. **Shared artifacts must exist on a shared ref.** A file that only exists on one task branch is not shared —
   every other branch will fail to cite it.

---

## 6. Lane economics

| lane | limit | kind |
|---|---|---|
| custom-deepseek-free | 3 | 3 logins × 1 in-flight — hard |
| openai-codex (luna) | 4 | operator cap, subscription |
| gemini | ~4 | rate-limits at 5–6 |
| openrouter | 2 | **free tier, 1000 requests/DAY** — a budget, not a concurrency cap |
| nous | ~3 | 50 req/min account-wide |

**A concurrency cap tells you how many workers to start. A daily allowance tells you what work to send.** Sending
long agentic cards to a daily-allowance lane burns the day for one card.
