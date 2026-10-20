# Decisions awaiting the operator

Durable record of blockers that need a decision ONLY the operator can make. A blocker here is (a)
surfaced to Richard as one clear question and (b) written down so it survives a restart. Obsolete /
duplicate / abandoned blockers are closed with a reason, not re-presented.

## OPEN

### D-001 — Testnet credentials for physical-fill certification
- **Question for Richard:** Do you authorise supplying real Hyperliquid TESTNET credentials
  (`HL_LIVE_HL_PRIVATE_KEY` plus `.env` / `.env.testnet`) so the physical-order/fill certification
  rows can be executed? Yes / No / defer.
- **Why it blocks:** With the key unset and no `.env`/`.env.testnet` present, the engine's real sender
  path returns `REAL_SENDER_NOT_CONFIGURED`; `HL_LIVE_MOCK_SEND=1` runs are dry-run self-tests, not
  real orders. No genuine order id / fill id / tx hash can be produced without credentials.
- **Scope of impact:** every row that requires a PHYSICAL exchange fill. Those rows are `BLOCKED` /
  `NOT_ESTABLISHED` and must never be marked PASS. Non-physical (static + runtime, no send) rows are
  unaffected and continue.
- **Opened:** 2026-10-14.
- **Status: AUTHORISED by Richard 2026-10-14.** Credentials are cleared for TESTNET use. They are
  ALREADY ON THE SYSTEM - no operator placement needed: `trading_stack/Hyperliquid scanner/_archive/hl_stage2.env`
  (names `HL_LIVE_HL_PRIVATE_KEY` [SET], `HL_LIVE_HL_ACCOUNT_ADDRESS`, `HL_USER_WALLET`,
  `HL_LIVE_MAX_MANUAL_ORDER_NOTIONAL_USD`, `HL_LIVE_MAX_CLOSE_ADVERSE_DIFF_PCT`, `HL_LIVE_WS_ENABLED`;
  values never read). The repair-repo engine's `DEFAULT_ENV_FILE` resolves relative to the engine at
  `_archive/hl_stage2.env`, which does NOT exist in this repo - point it at the existing file with
  `HL_LIVE_ENV_FILE=<absolute path>` (a PATH, never a secret) or run from the source tree. Do NOT copy
  the credential file into this repo. `HL_ENABLE_LIVE_SEND` is currently 0. This authorisation covers
  TESTNET only - MAINNET remains a separate human-authority gate (and the pre-existing mainnet leftovers
  are still an open human decision, `TESTNET_RUN_HANDOVER.md` §3). A key present is NOT authority to
  place a live MAINNET order.

### D-002 — Physical-fill signer does not exist on testnet (credential/account mismatch)
- **Question for Richard:** The key in the env file signs as `0x1110Dd09c451F3a5258F83309a65F470E6cFe86a`,
  which does NOT exist on Hyperliquid testnet, while the env's own account/user wallet is the funded
  master `0x7AE3B08bb4E7B085C6db5D635b96Bec9715e9205` (which DOES exist, 51 positions on testnet).
  Which is intended: (a) supply a private key/API agent that is actually authorised on testnet for the
  master `0x7AE3...`, (b) use a different existing testnet account, or (c) defer? Yes-a / Yes-b / defer.
- **Why it blocks:** the engine's real `_send_real` path was driven end-to-end and verified (symbol
  resolution, testnet mid-price fetch, SDK client creation, risk-limit check, exchange call all OK); the
  exchange then rejected the order `"User or API Wallet 0x1110... does not exist."` No genuine fill id
  can be produced until a signer that exists on testnet is supplied, so rows ENG-INV-07/08/09 stay
  BLOCKED/NOT_ESTABLISHED and MUST NOT be marked PASS.
- **Scope of impact:** every row requiring a PHYSICAL testnet fill. Non-physical rows are unaffected.
- **Opened:** 2026-10-14.
- **Status: OPEN — awaiting operator decision.** TESTNET only; MAINNET remains a separate gate.

### D-003 — DONE-10: LIVE/MAINNET authorisation (human-only gate)
- **Matrix row:** `DONE-10` (CONTROL / "Measurable DONE 10"). Source: `PRODUCT_SEMANTICS.md` §4.10
  (DONE item 10) and `ARCHITECTURE.md` "Completion definition" (DONE item 11).
- **Question for Richard (EXACT, verbatim from source):** "Richard explicitly decides LIVE/mainnet."
  Concretely: do you authorise the engine to go LIVE on Hyperliquid MAINNET (real funds, real orders)?
  Yes / No / defer.
- **Why it blocks:** DONE-10 is the human LIVE/mainnet gate — an operator decision ONLY Richard can
  make. It cannot be satisfied by any agent, harness, test, or certification run; no amount of executed
  evidence substitutes for the operator's explicit ruling. The row is BLOCKED on a human authority
  action, not on missing engineering work.
- **Scope of impact:** the single `DONE-10` completion row, and transitively the project "complete"
  verdict (DONE item 10 of 10). All non-LIVE certification rows are unaffected and continue. The
  TESTNET credential authorisation (D-001) and TESTNET signer question (D-002) are SEPARATE and do not
  constitute MAINNET authority; a testnet key present is NOT authority to place a live MAINNET order.
- **Control-mailbox check (Rule 8a):** no operator ruling already exists. `git fetch origin control-mailbox`
  performed; newest inbound envelope is `2026-10-09T16-14-33Z-B3-C2H-REALIGN-CFF93B-ACK-1.json`
  (realignment ACK only, no DONE-10 ruling); newest outbox is `2026-10-14T11-40-00Z-B3-H2C-PHYSICAL-FILL-RESULT-1.json`
  (testnet physical-fill result, not a MAINNET ruling). No DONE-10 decision present anywhere in the
  mailbox or in this file before this entry.
- **Row state:** kept `BLOCKED` on human decision — NOT `PASS`, NOT treated as unblocked. Do NOT invent
  or infer a ruling. `certification_matrix.json` is NOT edited by this task (matrix is owner-applied
  via the overlay); this durable entry is the authoritative blocked-reason record until the matrix
  owner applies it. Summary artifact: `certification/results/DONE10_GATE_d829fce8ff.md`.
- **Opened:** 2026-10-14.
- **Status: OPEN — awaiting operator decision (BLOCKED, human-only gate).**

### D-004 — STANDING FREEZE on certification work (operator-ordered; supersedes the completion gate)
- **Matrix rows affected:** ENG-INV-01, 03, 07, 08, 09, 10 and all 654 `NOT_TESTED` rows.
- **The order:** Boss, relayed by the controller in ruling `6285500040` at 07:12Z on 2026-10-20, verbatim:
  *"Boss's instruction: find the engine that ran for two months and fix only the sleeve/exit error. The
  certification register work has become a sprawl, and it ends now. **Hermes: stop all of this
  immediately.** No new register, evidence, mutation-control, decision-table or review cards, and no new
  engine branches beyond the two below. Finish only the two cards already in review. Park every other
  card."*
- **What remains authorised:** (1) the sleeve/exit fault — `t_65bc408d` / `e0a8017`, delivered and
  verified; (2) a Codex read-only comparison of the two-month engine (`5bda57be…`, 7,705 lines) against
  the current `_close_wire_plan` — dispatched as `t_7f672e87`; (3) the push route, which needs the
  operator's one-time GitHub sign-in.
- **Why this is a legitimate stop under the completion gate:** the gate's own criterion is *"a stop here
  is only legitimate if the user asked to stop."* The user asked to stop. The gate reads the matrix and
  cannot see a ruling in a comment thread, so it will keep reporting six outstanding requirements while
  the freeze forbids working on them. **The gate is not overridden — it is superseded by an explicit
  operator order, and this entry is the record that says so.**
- **Explicitly NOT a blocker:** the dispatch mechanism exists and works; `t_7f672e87` is a dispatched,
  running card. This is not a missing-mechanism report.
- **Do not:** refill the board with certification cards, raise register/evidence/review cards, or treat
  the idle board as starvation. The board being idle is the order working.
- **Opened:** 2026-10-20. **Status: ACTIVE — operator order in force.** Lifts when the operator or the
  controller says so, and not before.

## CLOSED

(none yet)
