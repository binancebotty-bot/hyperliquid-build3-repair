
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
