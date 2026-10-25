# Worker brief — standing operating rules

Rules that hold for every change to this product, regardless of which worker makes it.

## The engine and the UI are ONE product (Boss, 25 Oct 2026)

A restart means BOTH, as one ordered operation with one proof. Nobody may be unsure what
serves the UI, or what the UI draws from.

Paired restart procedure:
1. stop the UI; stop the engine;
2. prove zero of each — engine by script-argument match, UI by port 8031 having no listener;
3. start the engine; prove exactly one engine (pid, cmdline, audit-dir instance.lock held);
4. start the UI from the SAME release — same SHA family as the engine;
5. prove exactly one UI on :8031 and that it reads the SAME audit dir as the engine;
6. post ONE identity block for the pair: engine pid/folder/SHA/audit dir/start time,
   UI pid/folder/SHA/port/audit dir/start time, and match yes/no.

A pair that is out of step is a defect in its own right, even when each half is healthy.
On 25 Oct the engine ran v33 while the UI still served v31 code; nothing on screen said so.

## Identity must be visible, not inferred

The UI must show a build-identity strip read from files only: engine pid, engine build SHA,
UI build SHA, audit-dir name, and both start times. It turns amber, in plain words, when the
UI and engine SHA families disagree or when the pid recorded in the state file is not running.
A reader should never have to ask which code is answering.

## Restart count is a cost

Once the product is running, prefer changes that a running process can take: config, roster,
caps and flags are read per cycle. Code needs a restart, and a restart is a paired operation
above. Keep restarts few and make each one count.

## Evidence rules that have already cost us time

- A zero-check must match the script argument, never a substring of the process command line: a
  shell whose text merely mentions the script will otherwise masquerade as a running engine.
- A predicate that decides whether a status is "unknown" must be derived from the statuses the
  code can actually emit, not hand-maintained: a stale exclusion list turns a classified block
  into a false "unclassified" row.
- One fill, one terminal row. Two writers journaling the same outcome produce rows that
  disagree about what happened.
- Never report a number you have not read from the source of truth in the current window, and
  never let `ok: true` hide a partial read.
