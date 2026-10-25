# Candidate: v33 base + exposure-pending + pair-seed

Assembled 2026-10-25 after the 25 October testnet incident. Nothing here is deployed; the engine is
stopped with sends off.

## What it is

| piece | branch | tip | what it changes |
|---|---|---|---|
| base | `6c69310` | `6c69310` | the engine the pair restart already ran |
| exposure under-count | `hermes/exposure-pending` | `9017929` | Core:4921 no longer discards approved-but-invisible entries; keeps them until proven or 30 s old; writes `exposure_cap_trace.jsonl` |
| pair-start seeding | `hermes/pair-seed` | `918c2d3` | seeds an empty audit dir with a T0-anchored leader cursor, sends OFF by default, one identity block |

Merge commits: `c39ae9d` (exposure-pending), `a067d50` (pair-seed). 7 files, +960/-5, no conflicts.

## Verification on this candidate (not on the pieces)

| suite | result |
|---|---|
| `test_core_exposure_pending.py` | 5/5 |
| `ops/test_pair_launch.py` | 15/15 |
| `test_core_rw10_margin_symbol.py` | 18/0 |
| `test_core_observability_part1.py` | 21/0 |
| `test_core_send_lock_isolation.py` | 8/0 |
| `test_core_missed_entry_rule.py` | 95/0 |
| Core compiles | yes |
| Core line endings | CRLF 12,643 / bare-LF 3,203 (baseline unchanged) |

## Review status at assembly

| piece | internal adversarial review | Codex static review |
|---|---|---|
| pair-seed `918c2d3` | **FAIL** on `d998a74` - the overlap omitted the poll-interval term, so the engine would still have read one interval before T0 while the tool printed "pre-start fills: 0". Fixed in `d3ed8e8`; the three missing assertions now exist and pass. | PENDING |
| exposure-pending `9017929` | failing-first test drives the real `IntentBuilder.follower_exposure` and the real `_exposure_cap_block`; `PENDING_SURVIVES_A_REFRESH_THAT_HIDES_ITS_FILL` fails on the pre-fix code and passes now | PENDING |

The two PENDING cells are the reason this is a candidate and not a deploy.

## Known gaps this candidate does NOT close

1. **No drain on stop.** Terminating the engine discards its write-behind audit queue: a measured 8
   of 133 engine-era fills on 25 October have exchange fills and no journal row. A graceful stop
   must stop intake, flush the queues, then exit.
2. **No unrecorded-fills reconciliation at start.** Nothing compares the follower's exchange fills
   against the journal on the first cycle, so a restart after a violent stop begins with an
   understated book.
3. **`live_config.json` is not backed up by the seeder beyond the change log hash** - rollback is
   the `--force` re-seed or the archived `run8` copy.

## To use it

    python ops/seed_pair_state.py --state-dir <runN> --seed ops/live_config_seed.json --start-ms <now_ms>
    # then start the engine on Python 3.11 from this candidate's checkout, UI from the same release
    python ops/pair_identity.py        # must print UP and consistent

Sends stay off unless the seed is run with `--send-mode on`, which is a separate decision.
