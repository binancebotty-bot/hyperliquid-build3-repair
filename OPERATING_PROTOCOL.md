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

## Hermes reporting convention — Richard instruction, October 2026

Richard is the CEO/human authority, not the normal worker reporting destination.

- Hermes sends routine progress, test results, ACKs, blocker details, and stand-down requests to `gpt:reviewer-controller` using the existing deterministic control mailbox. Do not address Richard with these routine updates.
- When Richard directly speaks to Hermes, Hermes may answer normally. No blocking, interception, recipient guards, filtering code, new watcher, new transport, or restrictions on Richard initiating communication are required or authorised.
- After publishing a RESULT, verify it was published/woke Controller and **read the correlated Controller reply from the actual remote `origin/control-mailbox` branch as the final control operation of every turn**. Consume it if available. If still pending, preserve the correlation and existing event-driven receiver; do not send the waiting/status explanation to Richard.
- Project/product semantics and blockers go to Controller and, where required, the Project Architect; company control/routing matters go to Controller and MD. Richard need not relay any of these.
- Only Controller can authorise Hermes stand-down after the correlated ruling; no stand-down is inferred from a sent report, armed loop, or ending chat turn.
- This is a simple **reporting convention**, not a software feature or a new implementation task. It supersedes the earlier request for an outbound recipient guard.

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
