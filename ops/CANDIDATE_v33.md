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

---

## Re-cut: hermes/candidate-v34 (a307242)

Three pieces as their own merge commits, after the Codex findings on the first candidate:

| piece | branch tip | merge commit |
|---|---|---|
| exposure under-count | `hermes/exposure-pending` 899ed71 | first merge |
| pair-start seeding | `hermes/pair-seed` 918c2d3 | second merge |
| graceful stop | `hermes/graceful-stop` 51af97e | third merge `a307242` |

Provenance note, stated because it looks odd in the graph: `hermes/graceful-stop` was cut FROM the
previous candidate (3fa4afc), so its merge carries that ancestry. No content beyond the three pieces
is introduced by it; the earlier candidate commits in its history are the same pair-seed and
exposure-pending commits this branch already merges.

### Verification on this re-cut

| suite | result |
|---|---|
| Core compiles | yes |
| `test_core_exposure_pending.py` | 7/0 |
| `test_core_stop_sentinel.py` | 9/0 |
| `test_core_rw10_margin_symbol.py` | 18/0 |
| `test_core_observability_part1.py` | 21/0 |
| `test_core_send_lock_isolation.py` | 8/0 |
| `test_core_missed_entry_rule.py` | 95/0 |
| `ops/test_pair_launch.py` | 15/0 |
| `ops/test_stop_pair.py` | 6/0 |
| Core line endings | CRLF 12,678 / bare-LF 3,203 |

179 checks, zero failures.

### What changed since the first candidate

- exposure: the prefetch path no longer drops entries approved before its snapshot began; the TTL
  boundary is pinned with a frozen clock; the visible-fill over-count is documented and traced.
- graceful stop: a stale `STOP_REQUESTED` is quarantined at startup; a clean shutdown record counts
  only if it postdates the request; the UI is stopped only by a tracked, command-line-verified pid;
  `--force` writes `forced_stop_record.json`.
- `ops/stop_pair.py` is the only supported way to stop the pair.

### Still not covered

Unrecorded-fills reconciliation at start remains queued. The drain now protects the journal on a
clean stop; the reconciliation is what catches a journal that is incomplete for any other reason.

---

## Candidate after the stop-tool review: be6a52d

Adversarial review of `ops/stop_pair.py` returned **FAIL** with one BLOCKER: a timed-out intent
flush was recorded as `clean=True`, because `flush_intent_writer` reports a timeout by returning
False and the hook ignored the return value. That is the loss this tool exists to prevent, wearing a
green record. Fixed, with the reviewer's other findings:

- `clean=_flushed` from the sentinel hook, and `_atexit_marker` now flushes the intent writer too
  (it previously drained only the status workers) and records that outcome.
- the stale-sentinel quarantine moved AFTER the instance locks and refuses to start when the sentinel
  is younger than 120 s, so a second engine cannot steal a stop that is in flight.
- `--force` refuses to kill unless the forced-stop record is on disk, written per label and pid.
- UI identity is argv shape plus create_time, not a substring; a reused pid is refused.
- `verify()` requires the same pid and reason as well as a later timestamp.
- an already-stopped pair exits 0; each pid is verified; the kill is guarded; engines whose own
  `HL_LIVE_AUDIT_DIR` is not the dir being signalled are skipped.

### Verification on be6a52d

| suite | result |
|---|---|
| Core compiles | yes |
| `test_core_exposure_pending.py` | 7/0 |
| `test_core_stop_sentinel.py` | 11/0 |
| `test_core_rw10_margin_symbol.py` | 18/0 |
| `test_core_observability_part1.py` | 21/0 |
| `test_core_send_lock_isolation.py` | 8/0 |
| `test_core_missed_entry_rule.py` | 95/0 |
| `ops/test_pair_launch.py` | 15/0 |
| `ops/test_stop_pair.py` | 12/0 |
| Core line endings | CRLF 12,697 / bare-LF 3,203 |

187 checks, zero failures.
