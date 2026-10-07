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
5. commit actual work;
6. report exact commit SHA + evidence + `STAND_DOWN_REQUEST=YES`;
7. stop until the Controller ruling is consumed.

A commit is not permission to continue.
A report is not permission to continue.
A stand-down request is not self-approval.

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
