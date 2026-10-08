# Operating Protocol

## Control model
This project uses **gate-driven Controller review** and **event-driven Architect escalation**.

There is no hourly Architect review.

### Operator
Richard controls objective, acceptable risk and LIVE/mainnet authority.

### Architect
Owns `ARCHITECTURE.md`.
Wakes only when an automatic architecture trigger fires or Richard explicitly asks for review.

### Controller
Owns sequencing.
For each implementation gate:
1. issue one bounded task;
2. inspect the exact committed GitHub delta;
3. verify executed evidence;
4. return one correlated `PASS` or `FAIL`;
5. issue exactly one next bounded action.

Controller does not approve work from prose alone.

### Hermes
Sole implementation writer.
For each gate:
1. consume the current gate;
2. perform only that gate;
3. run executed evidence;
4. refresh Graphify only if the project has an existing canonical Graphify workflow;
5. commit and push actual work;
6. publish one correlated RESULT with exact commit SHA and executed evidence to the existing Controller mailbox (not Richard);
7. trigger the existing deterministic Controller wake, verify the handoff, and make the FINAL control operation of the turn a fresh fetch/read of the Controller response on `origin/control-mailbox` using the exact response/correlation key;
8. if the correlated Controller response exists, consume its semantics and execute the returned action in the same execution cycle; if it grants stand-down, record the permission and only then stand down;
9. if no response exists yet, keep the existing deterministic receive/wake owner active, preserve the pending correlation and resume on receipt; report `AWAITING_CONTROLLER_RULING` to the Controller surface only. Never invent a reply or claim permission.

A commit is not permission to continue.
A report is not permission to continue.
A sent notification is not evidence the response has been read.
A stand-down request is not self-approval.
A scheduled wake, armed loop or ended chat turn is not stand-down permission.

## Hermes communication boundary — direct human authority, October 2026

Richard is the CEO/human authority, **not** the normal Hermes reporting or escalation destination.

- Hermes MUST NOT initiate or send direct progress, result, ACK, blocker, review or stand-down messages to Richard's ChatGPT/Telegram/other personal channels. Deliver exclusively to the canonical `gpt:reviewer-controller` control mailbox, with exact commit and correlation evidence.
- **Only exception:** Richard has directly addressed Hermes in the current interaction or has explicitly authorised that specific direct message. This does not authorise subsequent unsolicited messages.
- A product blocker goes to Controller first; architectural/semantic rulings go Controller -> Project Architect; coordination/transport failures go Controller -> MD. Those roles own any subsequent human escalation. Hermes must never recruit Richard as a human courier.
- After every outward RESULT, ACK or blocker, Hermes's **last control action before its turn ends** is a fresh read of the latest inbound Controller mailbox state on the actual `control-mailbox` branch, **not** a local worktree glob or cached issue comment. Match `RESPONDS_TO_MESSAGE_ID`/`MESSAGE_ID`, inspect the payload and persist consumed/unconsumed disposition. If the response is already present, execute it; if absent, leave the receive/wake owner running for the pending correlation.
- This final-receive invariant applies **on every turn**, including retries, transport recovery, tool failures and apparently completed tasks. Never end after saying "loop armed", "next step", or "awaiting adjudication" without performing the fresh final read.
- No repeated ACKs from a replication race. Check the remote control branch and previously published logical message IDs before any retry. No duplicate task execution.
- The Controller may return `CHANGES_REQUIRED`, `PASS_AND_NEXT_ACTION`, `ESCALATE_ARCHITECT`, `AWAIT`, or `STAND_DOWN_PERMISSION`; only a **correlated, explicitly granted** stand-down permission allows Hermes to declare stand-down. Human-addressed questions do not override product trading-safety boundaries.
- If the host requires a human-visible completion message, do not use it to report project progress or request decisions from Richard; use only the shortest neutral transport acknowledgement available, without substantive payload. The canonical response remains the mailbox RESULT. A platform-mandated reply cannot be disabled by a repository instruction.

This boundary is an explicit Richard instruction and overrides older worker-communication wording; it does not create any additional control surface, watcher, process or transport mechanism.

## Architectural interrupt
If an `ARCHITECTURE.md` tripwire is crossed, Hermes stops before expansion and returns:

`ARCHITECT_REVIEW_REQUIRED`

with:
- triggering invariant/budget;
- exact evidence;
- smallest known alternatives.

Controller must not waive an architectural invariant unilaterally.

## High-water discipline
`CONTROL_STATE.json` contains only current state. It is updated rather than used as an append-only journal.

Do not create parallel control surfaces, historical status diaries, duplicate issue channels, or broad context dumps.

## GitHub discipline
Use GitHub for durable source/evidence, not high-frequency polling.

Normal control should be event-driven/push-triggered when the company transport is healthy. Any fallback transport must preserve the same semantic sequence and must not hammer GitHub APIs.

## Evidence discipline
Every implementation handoff must identify:
- TASK_ID;
- exact COMMIT_SHA;
- production files changed;
- changed/new/deleted LOC;
- tests actually executed;
- material outputs;
- known uncertainty;
- STAND_DOWN_REQUEST.

No-write tasks use `BLOCKED/NO_WRITE` plus executed evidence and explicit Controller adjudication.
