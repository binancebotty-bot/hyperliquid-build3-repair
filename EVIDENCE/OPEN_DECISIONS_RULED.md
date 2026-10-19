# Open decisions — rulings on record

Recorded 2026-10-19. These convert rows from "blocked on a decision" to "testable", but the evidence for them still has
to be produced; a ruling is not a verdict.

Sources: controller rulings `6264913600` (OD-12, OD-18) and `6264924895` (confirmation); OD-08's product half was already
recorded in `certification/open_decisions.json` as settled by Boss on 2026-10-09 §5.

---

## OD-08 — 43 rows — CLOSED by recorded Boss decision

**Decision text:** network configuration contract; each side's network is switchable and mainnet and testnet can run in
parallel (Boss, 2026-10-09 §5). The residual stated in the register is *"the per-side split in code and its testnet
proof."*

**Ruling:** the product question is closed and not re-opened. The residual is **not** a decision — it is a code change
(a per-side URL split so leader reads can stay on mainnet while follower reads point at testnet) plus testnet proof.

**Status:** rows move from the decision bucket to the **runtime/implementation** bucket. Not testable until that change
exists and has testnet evidence.

---

## OD-12 — 32 rows — RULED BY CONTROLLER (`6264913600`)

**Decision text:** Build 3 lifecycle mechanism. ARCHITECTURE requires proof of launch, start, stop, restart, version
identification, cutover, rollback and config migration. Build 4's mechanism cannot be imported (inv 5/6) and no Build 3
document names the canonical start command, lock or version source.

**Ruling:** **one documented start command, a PID/lock file, and a version string written at launch — certified on those
three properties only.** Not the full Build 4 lifecycle set.

**Status:** the question is answered. The 32 rows (`LIFE-001..009`, `F25-P01..P10`, `F25-X01..X06`, `NET-006`, …) are now
testable **in principle**, but each still needs evidence that those three properties hold. That is runtime evidence, so
they sit in the runtime bucket until it exists.

**Note:** the register still carries OD-12 as an open decision on 32 rows. It should be closed there, but `source_sha256`
and decision state are register data — changing it is a reviewed edit, not a coordinator write. Flagged for the next
reviewed register change.

---

## OD-18 — 45 rows — RULED BY CONTROLLER (`6264913600`)

**Decision text:** two UIs in one app; the analytics dashboard shows an app-derived model while the Command Centre shows
real-account truth; FAILURES UI-001 / PRODUCT-002 require every value to carry its truth tier, so a model value cannot be
read as live truth. Needed: how the model view is labelled while Build 3 is preserved.

**Ruling:** **a visible `MODEL` tier badge on every model value.**

**Status:** the labelling question is answered. The 45 rows (`UI-SSOT-TOP-01..09`, `UI-SSOT-CARD-01..07`, …) are testable
against a live surface — but the badge may not exist in the served build yet. If it does not, the rows are FAIL or
NOT_TESTED with that reason, not PASS.

---

## What this changes, arithmetically

| | rows |
|---|---:|
| decision-blocked before these rulings | 221 |
| now ruled (product question closed) | **120** (OD-08 43 + OD-12 32 + OD-18 45) |
| still awaiting a ruling | 101 across 20 smaller decisions |

The 120 do **not** become certified. They move from "waiting on a person" to "waiting on evidence" — which is progress,
but it is not verdicts.

---

## Standing constraint

Controller ruling `6264924895`: **stop raising generic cards until free slots are real.** Every Hermes lane returns
`exit_code 75` (rate-limited). Only the pacing tests and their reviewer stay queued. Row work resumes when lanes free.
