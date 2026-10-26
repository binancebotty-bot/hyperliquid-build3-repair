# HANDOFF — read this first

You are taking over the **Build-3 Hyperliquid testnet copy-engine lane** from Hermes. This file is the whole
context: what we are doing, the rules that exist because something went wrong without them, how to work with the
controller, and exactly where things stand at the moment of handoff.

Read this top to bottom once. It is written so that you do **not** need the previous conversation.

---

## 0. IF YOU ONLY READ ONE THING

**The pair is STOPPED on purpose. Do not start it.** An unattributed batch flatten hit the account at
14:37:02Z and is not yet explained. The controller (Claude, via GitHub issue #92) has not given a start
instruction since. Your first action is always: **read the newest comments on issue #92**, then act on what it says.

Repo: `C:/Users/wigmore/hyperliquid-build3-repair`
Control channel: **GitHub issue #92** of `binancebotty-bot/hyperliquid-build3-repair` (PR #81 is full — GitHub
refuses more than 2,500 comments; #3 is an older lane).
You post results there. You do **not** post to the operator (Richard) unless he speaks to you first.

---

## 1. WHAT WE ARE TRYING TO ACHIEVE

A copy-trading engine on Hyperliquid **testnet** that mirrors real **mainnet** leaders:

- Leaders are **read-only**; the follower is the only thing that writes.
- The long-term goal is a certified, safe follower: it copies entries and exits, never opens a position it cannot
  close, never exceeds its exposure caps, and can prove every action against the exchange.
- Tonight's specific goal was a **zeroed restart**: flat the book, archive the old state dir, start fresh on a
  reviewed build with sending OFF, then turn each new safety unit on one at a time while watching.

Current blockers to that goal are listed in §6.

---

## 2. THE CAST

| Who | Role | How you talk to them |
|---|---|---|
| **Richard** (operator) | Human authority. Business decisions, credentials, anything irreversible, MAINNET. | Only if he messages you. Plain English, no jargon, one or two lines. |
| **Claude** (controller) | Your boss. Gives bounded orders, reads your diffs, gives GO/NO-GO. | GitHub issue #92 comments. Never skip him. |
| **Codex** (reviewer) | Read-only adversarial reviewer. Finds the bugs you miss. | It reviews a **sha** you post; you fix, push, post the new sha. |
| **You** | Implement, verify, report. | — |

**Never** claim another agent's work as your own, or infer their reply. If Claude has not posted, there is no
instruction.

---

## 3. THE WORKFLOW (this is the loop; everything else is detail)

```
1. WAKE        a GitHub comment arrives on #92 → read the NEWEST comments, oldest-unread first
2. UNDERSTAND  quote the order back in one line before you start
3. BUILD       in a git worktree under C:/tmp/<name> — never in the live checkout
4. TEST        run the real tests; a change with no test is not finished
5. REVIEW      for anything touching orders, money or state: get an adversarial review BEFORE posting
6. POST        short, deterministic, proven: the sha, the numbers, what failed, what you did not do
7. AWAIT       the next order. Do not invent work.
```

**Post format that works** (Claude reads dozens of these):

```
HERMES: <one-line verdict>. <sha>, <test count>.
what changed — a table or bullets, each tied to the reviewer's item number
what I measured — real numbers, real command output
what I did NOT do — stopped/untouched/not-run, explicitly
what I need — the decision, if any
```

Never post a claim you have not measured. "The suite passed" needs the numbers. "Fixed" needs a sha.

---

## 4. THE RULES — each one exists because something went wrong

### 4.1 Safety, absolute

1. **Never print, log, echo or transmit a private key, seed or secret.** Report derived addresses and paths only.
   The key lives in `~/.hermes/state/core_launch_env.json` — read it into a process, never into a chat.
2. **Never start, stop or restart the engine without an explicit order.** It is stopped right now on purpose.
3. **Never `git add -A`.** Concurrent edits share the tree; stage explicit paths, then check `git diff --cached --stat`.
4. **Never merge, never force-push over reviewed work.** Rebase, don't force.
5. **One writer per worktree.** Two agents in one checkout will corrupt each other's work.
6. **The live checkout is read-only** (`C:/tmp/v41_2e44573/...` is where the running build lives). Do all work in
   `C:/tmp/<something>`.

### 4.2 Money-path rules (these came from real incidents)

7. **Never write a file the running engine watches while sending is ON.** `live_config.json` is re-read on mtime
   change: a mid-run edit is a live control action. Stage it, back it up, apply it as part of a restart.
8. **A reduce-only order must never exceed `abs(net)`**, and its side must oppose the net. Round sizes DOWN to the
   coin's `szDecimals` and prices with the engine's own formatter — never hand the SDK a raw float (that caused
   `float_to_wire causes rounding`).
9. **An order that fills can still raise.** After any exception during a send, re-read the position: if it moved
   toward flat the row is **`FILLED_DESPITE_EXCEPTION`**, not an abort. A fill recorded as a failure is how an
   unaccounted fill gets archived over.
10. **Every order needs a cloid.** Without one, the reconcile gate cannot match it and your own fill looks
    UNACCOUNTED.
11. **Never trust a position's ownership from a name alone.** Decide ENGINE / USER / AMBIGUOUS from the ledger's
    **non-zero signed size** AND the send journal, case-blind. AMBIGUOUS means **refuse and name it**, never
    auto-close. Hand-placed coins (`XYZ:CRCL`, `XYZ:ORCL`, `XYZ:LLY`) are never touched.
12. **Unknown is never zero, and unknown is never permission.** An unreadable ledger, an unreadable endpoint, an
    unclassifiable reply → stop. Never guess.
13. **Only a clean "IOC no match" may retry.** Rejected or unclassified → abort the whole run.
14. **Evidence before exit.** Every abort writes a report and fsyncs it, with a final position re-read. A report
    write failure prints the rows to stdout and returns a distinct code.

### 4.3 Evidence rules

15. **Quote the exchange, not your own bookkeeping.** `position`, `fill oid`, `cloid`, `closedPnl` — from
    `/info`, by time window. Local journals are for reconciliation, not for truth.
16. **A perp `accountValue` is not the account.** Check **spot** before you call a number a loss. (I raised a
    false alarm at 14:41Z saying $232→$3.35 was a wipe; it was $972.86 sitting in spot, and the realised loss was
    $2.03. Check both sides before alarming.)
17. **Withdraw or correct a claim the moment you find it is wrong**, in the same channel, with the measurement. Do
    not quietly move on.

### 4.4 Windows/tooling traps (they cost hours)

18. **Do not pass `/c/...` MSYS paths to native programs** (git, python, node) — they create `C:\c\Users\...`.
    Use `C:/Users/...`.
19. **`wmic` does not exist on this Windows build.** For pids use `ops/stop_pair.pids()` (psutil-based) — the
    wmic version silently returns `[]` and your guard never fires.
20. **`write_file` can report success and leave no file** under `.hermes/cache/scratch`. For anything that must
    persist, write into the repo and verify with `ls`/`wc -c`.
21. **Backticks inside a `python -c "..."` shell string are command substitution.** Post bodies with backticks by
    writing the body to a file first, then reading it in the Python call.
22. **The engine file has MIXED line endings.** Never rewrite it wholesale; patch with exact-string replacement and
    assert the match count.
23. **A `delegate_task` child that reports success may be wrong.** Verify the artifact yourself (file exists, test
    count, sha).

---

## 5. HOW TO HELP CLAUDE OPTIMALLY

- **He reads diffs, not prose.** Post the sha, the diff stat, and the numbers. He will say "I read it" if it is
  small — keep it small.
- **Tie every fix to his item number.** "His P1.3" beats "I fixed some rounding".
- **When he is wrong, say so with evidence, once, then do what he decides.** He reversed himself twice tonight
  after being shown a measurement, and was right to.
- **Do not ask him to make an engineering decision you can measure.** Measure first, present the number, then ask
  only what genuinely needs a human (money, policy, MAINNET).
- **Never send him a message that costs him a round trip to learn something you could have checked.** He has said
  this repeatedly.
- **When a review blocks you, fix all items in ONE push** and post the new sha. Do not drip.
- **When you have made a mistake, lead with it.** He has accepted every honest correction tonight and distrusted
  every dressed-up one.

---

## 6. WHERE THINGS STAND AT HANDOFF (2026-10-26 ~14:50Z)

### The account
```
perp positions   HYPE 0.14 only           (was 19 earlier today)
perp orders      1 × HYPE sell 0.14 @ 60.836   (not placed by us)
perp equity      $3.35
SPOT             USDC 972.86              <-- the real money, always check this
```

### The incident that is NOT explained
At **14:37:02Z** something closed **22 positions in one second** (sequential oids `63737993675`–`63737993699`,
**every one `cloid: None`**), including **`xyz:COPPER`**, which is the category we treat as hand-placed.
Realised PnL −$2.03. **Neither the engine (stopped 14:31:03Z) nor Hermes' driver did it.** Attribution is open.
**Do not archive the state dir over an unattributed batch.**

### The pair
```
engine    stopped 14:31:03Z (pid 21596 exited clean; shutdown record clean=True)
UI        stopped (pid 26952)
port      8031 free; zero engine pids (verified)
state dir C:/Users/wigmore/trading_stack/hl-build3-testnet-cert-evidence/run13/state_20261026
          intact, send_mode ON, snapshot PRE_ZERO_SNAPSHOT_20261026T143046Z.json inside it
```
A monitor process (`trading_stack/_tools/hl_monitor.py`) posts an ALERT every ~15 minutes saying "engine restart
condition detected". **That is expected while the pair is down. It never acts. Do not silence it and do not start
the engine to quiet it.**

### The builds
```
start sha       C:/tmp/bundle_v2 @ be42c74         suite 84 failed / 2,155 checks (base 85)  <- restart target
flatten driver  C:/tmp/w_flatten @ 35345be         units 68/0 + behavioural send-path 6/0
                branch hermes/flatten
rollback target 2e44573  (checkout C:/tmp/v41_2e44573/_archive/hl_stage2)
```

### The remaining sequence (each step needs the controller's GO)
```
1. attribute the 14:37:02Z batch (ask Claude; do not guess)
2. decide xyz:COPPER (was it Boss's?)
3. finish HYPE 0.14 if instructed (one coin, --only HYPE)
4. --reconcile  -> must print ARCHIVE_GATE PASS
5. archive old state dir (mv, never delete)
6. fresh dir run15/state_20261026 + staged config (sha256 2677427c...) + seed:
      ops/seed_pair_state.py --state-dir <new> --seed ops/live_config_seed.json \
          --start-ms <now> --interval-sec 10 --send-mode off
      then the same command with --verify-only   (expect VERIFIED)
7. ops/start_pair.py --checkout C:/tmp/bundle_v2 --state <new> --expect-sha be42c74 --ui-port 8031
      (launch with the launcher env: ~/.hermes/state/core_launch_env.json)
8. zero proof, then a table every 10 minutes for the first hour
```

### Commands that work (copy/paste)

```bash
# newest comments on the control channel
cd /c/Users/wigmore/.hermes/control && <py311> -c "
import sys; sys.path.insert(0,'.')
import gh_issue as g; g.REPO='binancebotty-bot/hyperliquid-build3-repair'
for c in g.comments(92)[-3:]: print(c['id'], c['created_at']); print((c['body'] or '')[:800])"

# post a comment (write the body to a file first — backticks are shell substitution)
<py311> -c "import sys; sys.path.insert(0,'.'); import gh_issue as g;
g.REPO='binancebotty-bot/hyperliquid-build3-repair';
print(g._post('%s/repos/%s/issues/92/comments'%(g.API,g.REPO), {'body': open(r'C:/tmp/msg.md',encoding='utf-8').read()})['id'])"

# is an engine running?
<py311> -c "import sys; sys.path.insert(0,'C:/tmp/bundle_v2/ops'); import stop_pair; print(stop_pair.pids(None))"

# the flatten driver (dry run is the default; --live needs --cancel-resting, a testnet endpoint, no engine)
cd C:/tmp/w_flatten && <py311> ops/flatten_testnet.py --state <state dir> --reconcile
```
`<py311>` = `C:/Users/wigmore/AppData/Local/Programs/Python/Python311/python.exe` (the 3.11 install has the
hyperliquid SDK; the default python is 3.14 and does not).

---

## 7. THE FAILURE PATTERNS TO AVOID (learned the hard way tonight)

1. **Do not fix the instance in front of you and assume it is the only one.** Twice tonight a defect had a sibling
   one `grep` away (two `terminal_state` writers; two oid normalisers). **Always grep every caller and every
   sibling before you claim a class of bug is fixed.**
2. **Do not test by reading.** A test that asserts a string exists in the source proves nothing. Drive the
   behaviour with a stub (see `ops/test_flatten_send_path.py`).
3. **Do not change a thing the controller did not ask for**, especially not "one round trip instead of two" on the
   engine's most important read — that one returned **HTTP 422** on the live endpoint and would have stopped the
   engine copying.
4. **Do not announce a result before the measurement lands.** Posting "green" then correcting it costs more trust
   than posting late.
5. **Do not conclude from a stale file.** Check mtimes. A six-day-old health file produced a false "engine dead"
   alert that was believed for an hour.
6. **Do not assume a tidy number is the whole story.** $3.35 perp ≠ a wiped account.

---

## 8. FIRST TEN MINUTES OF YOUR SHIFT

1. Read the last ~5 comments on issue #92 (command above). Identify any order you have not actioned.
2. `stop_pair.pids(None)` — confirm zero engines. Never start one without an order.
3. Query `/info` `clearinghouseState` + `spotClearinghouseState` and write down positions, orders, perp equity,
   spot balance. That is your baseline.
4. Post a one-line "HERMES online — state as of <time>" with those four numbers, and the sha of the build you are
   working from.
5. Then, and only then, do what the controller asked.
