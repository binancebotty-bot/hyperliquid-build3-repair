# REPORTING CONVENTION — Build-3 repair lane (coordinator ↔ controller)

Operator-set rules. These govern WHEN I post to Claude, not what the work is.

## Surfaces

- **PR #81** and **issue #3** of `binancebotty-bot/hyperliquid-build3-repair` — both, every substantive post.
  PR #81 is a tracking surface and is **never merged**.
- The session/desktop chat is for the OPERATOR, not the controller.

## CHATTER RULE — absolute minimum (operator, 2026-10-16)

Post **only** when the message is substantive. Concretely, post when:

1. a **ruling is needed** (a decision only the controller can make);
2. a **blocker** exists that he or his GPT can act on;
3. he **asked a question** and an answer is owed;
4. a **correction** is owed on something previously posted (accuracy beats silence);
5. a **finding changes the project position** (e.g. a register/matrix discrepancy).

Do **NOT** post: acknowledgements, routine progress, "still working" notes, restatements of what he just said,
or the same update twice. **Batch findings and post once.**

## …BUT the chatter rule is NOT a licence to under-escalate (operator, 2026-10-16)

> "however don't fail to escalate when relevant he has GPT who can directly drive the engine"

So silence is never the safe choice when something is genuinely actionable. In particular, **escalate promptly**:

- **engine / mission / runtime blockers** — Claude has GPT that can **directly drive the engine**, so a blocked
  engine row is HIS to unblock, not something to sit on;
- **anything an agent on his side can execute** but I cannot from this repo (no kanban route, no local access);
- **testnet transport / captured-oracle gaps** — the owner is Codex, routed by him;
- **registers or matrices disagreeing** — a position-affecting discrepancy is never "routine".

Rule of thumb: **no chatter, yes escalation.** The test is "can he or his side act on this?" — if yes, post it,
however short. If no, batch it or leave it.

## Format

- Lead with the ask or the finding; keep it short.
- Cite the exact refs (register ref + commit), never bare "main".
- State what I did NOT do as well as what I did, when a boundary was respected.
- Never report a number I have not computed from the source of record — show the arithmetic where it matters.

## Escalation log discipline

Corrections to previously published figures are posted **even when embarrassing** — three wrong numbers were
caught this session (a stale derived summary, an unqualified ref, a double-count) and each was published as a
correction. Accuracy over appearance.
