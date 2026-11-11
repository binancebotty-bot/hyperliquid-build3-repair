# Seeding a fresh audit dir (pair start)

`ops/seed_pair_state.py` prepares an EMPTY state dir so a pair start cannot replay leader history.
Read this before any state reset. It exists because of an incident, not as a nicety.

## Why it exists

With no state, the per-wallet leader cursor is absent. The engine then takes its
`_cursor == 0` branch and starts the leader poll at `now - POLL_WINDOW_MS` (24 h), clamped to the
retention floor (`LEADER_POLL_RETENTION_MS`, 100 minutes). On 2026-10-25 that replayed roughly one
hundred minutes of ten active leaders as if it were live: 38,555 merged fills, 221 real send
attempts, 58 positions in 173 seconds on the testnet account, before the engine was stopped by hand.

## What it writes

Exactly two files into the empty dir, nothing else:

| file | content |
|---|---|
| `live_config.json` | the non-secret seed: wallets, modes, `global_controls` (every cap), `send_mode` |
| `clean_core_runtime_state.json` | `last_leader_poll_cursor_ms` for every wallet |

No keys, no addresses beyond the public leader wallets, no history.

## The cursor arithmetic, and why it looks odd

The engine's own formula is:

    _overlap_ms = poll_interval_sec * 1000 + LEADER_POLL_OVERLAP_MS      # Core:13519
    _start      = max(_cursor - _overlap_ms, retention_floor)            # Core:13525

`poll_interval_sec` is not a constant: it is 0 with the feed off, 120 s with a healthy websocket,
and a few seconds while the feed is unacked (Core:12729-12741). So the seed writes

    cursor = T0 + interval_max + LEADER_POLL_OVERLAP_MS

with `interval_max` the largest interval the engine may resolve. For any smaller actual interval,
`_start` lands at or after `T0`. Counting only the overlap constant leaves the engine reading one
whole poll interval before `T0` — which is what revision 1 of this tool did, while printing
"pre-start fills: 0". That was caught by adversarial review, not by the suite that existed.

## The second line of defence: PRE_CUTOVER_NOT_SENT

The engine stamps `live_start_ms` when the dedupe store is constructed (Core:11233-11234) and marks
any leader fill older than it `PRE_CUTOVER_NOT_SENT` instead of sending (Core:12497, 12514).

**Do not remove or pre-seed that key.** It is what stopped the 25 October replay from sending after
the first instance, and it is why a mistimed cursor costs audit noise rather than orders. The seed
deliberately never writes `live_start_ms`, so the engine always stamps a fresh one.

## Sending is OFF by default

`--send-mode` defaults to `off`, and the shipped seed also carries `send_mode: OFF`. A seeded pair
start therefore comes up observing only. `send_mode` wins over any `auto_send_enabled` key
(Core:3885), so that is the single place to look.

Turning sending on is a separate, logged step, ordered deliberately:

    python ops/seed_pair_state.py --state-dir <dir> --seed ops/live_config_seed.json \
        --start-ms <T0> --send-mode on        # and that is a decision, not a default

## Refusals (each a distinct exit code)

| code | refusal |
|---|---|
| 2 | the seed is missing a cap key |
| 3 | a cursor file already exists (not a fresh dir) |
| 4 | `instance.lock` exists (an engine is running) |
| 5 | the seed file lives INSIDE the state dir |
| 8 | the written config does not parse back equal to the seed |
| 9 | `--start-ms` more than 120 s in the past (a stale anchor reopens the window) |

`--verify-only` inspects a seeded dir and writes nothing: it rejects non-positive or stale cursors
and a config that no longer equals the seed, then prints `VERIFIED`.

Every successful seed appends one line to `~/.hermes/state/pair_launch.log` (override with
`PAIR_LAUNCH_LOG`) recording the seed hash, the config hash before and after, the cursor count, the
start time, the interval, the overlap and the send mode.


## Stopping the pair: only one supported way

Never stop the engine with a terminate/kill. On Windows that runs no cleanup and discards the
write-behind audit queue (measured: 8 of 133 engine-era fills lost on 2026-10-25).

    python ops/stop_pair.py --track-ui     # at launch, record the UI pid it may later stop
    python ops/stop_pair.py --all          # graceful: sentinel -> flush -> clean shutdown record

`--force` exists as a last resort, writes `forced_stop_record.json`, and says that queued rows may
be lost. A clean shutdown record only counts if it is newer than the stop request.

## Sequence for a pair start

1. seed the empty dir immediately before the start (within 120 s), default send mode off
2. start the engine from its own checkout, on Python 3.11 (the SDK lives only there)
3. start the UI from the same release against the same dir, with `PYTHON*` scrubbed from its env
4. prove the pair with `ops/pair_identity.py` and post the block
