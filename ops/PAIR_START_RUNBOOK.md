# Pair-start runbook — sends OFF

The ordered procedure for bringing the engine and the UI up together from one reviewed build, with
sending disabled, and proving it. Nothing here turns sending on: that is a separate, logged step the
controller orders (see the last section).

Applies to candidate `hermes/candidate-v34` (`720438a`). Do not improvise around it — each gate below
exists because something was lost by skipping it on 2026-10-25.

## 0. Preconditions, checked not assumed

    # exactly one engine, or none; never two
    ops/stop_pair.py --engine            # idempotent: prints "no engine running - already stopped"

    # the build you are about to run
    git -C <candidate checkout> rev-parse --short HEAD        # must equal the reviewed SHA
    git -C <candidate checkout> status --porcelain             # must be empty

    # both interpreters exist: the engine SDK lives ONLY under 3.11
    C:/Users/wigmore/AppData/Local/Programs/Python/Python311/pythonw.exe -c "import hyperliquid"   # engine
    C:/Users/wigmore/AppData/Local/Python/pythoncore-3.14-64/python.exe -c "import uvicorn"        # UI

If any precondition fails, stop here and report it. Do not work around a missing interpreter: under
3.14 the engine fails as `SDK_UNAVAILABLE`, which reads like a credential problem.

## 1. Stop anything that is running (graceful)

    ops/stop_pair.py --all

Expect: engine exits within a second or two of the sentinel, the shutdown record says
`clean=True reason=stop_sentinel` with the pid that was stopped, and no `send_attempts` row is left
`PENDING_SEND`. If the record is missing or unclean, do NOT proceed to a start — a stop that lost rows
means the journal is short and the next run's book starts wrong.

## 2. Fresh state dir

    STATE=C:/Users/wigmore/trading_stack/hl-build3-testnet-cert-evidence/run10/state_20261026
    mkdir -p "$STATE"            # must be empty; the seeder refuses a dir that has a cursor file

Never reuse a previous run's dir and never delete one: previous dirs are the evidence.

## 3. Seed it, sends OFF, immediately before the start

    ops/seed_pair_state.py --state-dir "$STATE" --seed ops/live_config_seed.json \
        --start-ms "$(date +%s%3N)"

Expect, and check every line:
  - `send_mode OFF`
  - `engine starts at <T0> (matches T0: True)`
  - `PRE-START FILLS REACHABLE AT ANY INTERVAL <= ASSUMED: 0`
  - a change-log line in `~/.hermes/state/pair_launch.log` with config hashes before and after

The seed must run within 120 s of the engine start; the tool refuses a stale anchor, and if it is
stale the honest move is to re-seed rather than to force.

## 4. Point the launcher at that dir

    # ~/.hermes/state/core_launch_env.json -> env.HL_LIVE_AUDIT_DIR = $STATE
    # keep a copy of the previous file beside it; that is the rollback

The identity tool and stop_pair both read this file, so if it is wrong they act on the wrong run.

## 5. Start the engine (Python 3.11, headless)

    HL_LIVE_AUDIT_DIR=$STATE <3.11>/pythonw.exe HL_Live_Copy_Service_Core.py \
        --ws --loop --interval 10 --poll-live --poll-copy
    # cwd = the candidate's _archive/hl_stage2

Prove, before starting the UI:
  - exactly one engine, by script-argument match (not by a substring of a command line)
  - `$STATE/instance.lock` exists
  - `$STATE/live_service_state.json` is being written
  - the first `fill_trace.jsonl` cycle is stamped at or after T0 — no catch-up

## 6. Start the UI from the SAME build, console-less

    # PYTHON* must be scrubbed from the child env or the 3.14 UI exits instantly and silently
    HL_LIVE_AUDIT_DIR=$STATE HL_APP_PORT=8031 <3.14>/python.exe -m uvicorn \
        HL_Copy_App_SSOT:app --host 127.0.0.1 --port 8031 --no-access-log
    # cwd = the candidate's _archive/hl_stage2; CREATE_NO_WINDOW; stderr to a log file

Then record it, so a later stop does not have to guess:

    ops/stop_pair.py --track-ui

## 7. Prove the pair, then post the identity block

    ops/pair_identity.py

Expect `pair UP and consistent`. It must show engine build and UI build from the candidate, the same
audit dir on both, one engine, one listener on 8031, and the page serving the new-build markers. If it
says DEGRADED, stop with `ops/stop_pair.py --all` and report - never leave a half-pair running.

## 8. Sending stays OFF until ordered

The engine comes up observing. Sending is turned on only as a separate, logged step:

    # write global_controls.send_mode = "ON" into live_config.json, log the before/after hashes,
    # then restart the engine gracefully (stop_pair --all, then section 5 again)
    # the change log line is the record of who armed sending and when

Nothing in this runbook arms sending by accident, and no flag outside `live_config.json` can.

## Rollback

    ops/stop_pair.py --all
    # repoint core_launch_env.json at the previous run's dir, restart section 5 from the previous
    # build's checkout, then section 6-7 to prove it

Rollback is a restart, never an edit of a running state dir.
