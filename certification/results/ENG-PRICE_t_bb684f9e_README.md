# ENG/PRICING evidence package - kanban t_bb684f9e

Rows: ENG-INV-07, ENG-INV-08, ENG-INV-09, ENG-003, PRICE-001, PRICE-002

Register of record: `git show b142cf88:certification/certification_matrix.json`
(matrix sha256 `86b2237fe95f88ca9eb758fb42ddbdf3efdaef71e56f79a10e2d2635f44f341a`).
The working-tree matrix was NOT used and was NOT edited.

## Verdict

All 6 rows remain NOT_TESTED. 10 executed checks pass; no row is fully covered at the
register commit. Each row in the JSON names exactly what is missing and why.

## Files

| file | what |
|---|---|
| `ENG-PRICE_t_bb684f9e_b142cf88.json` | evidence package (per-row verdicts, executed checks, oracles, missing-for-pass) |
| `ENG-PRICE_harness_t_bb684f9e_b142cf88.py` | executed probe (pricing/freshness + DEX scope + ledger reconciliation) |
| `ENG-PRICE_wire_trace_harness_t_bb684f9e_b142cf88.py` | wire-level trace (engine limit price -> exchange fill) |
| `ENG-PRICE_oracle_b142cf88/` | read-only oracle snapshots + sha256 (`ORACLE_SHA256.txt`, `SNAPSHOT_SHA256.txt`) |

## Method / honesty notes

- Two-run control run for every executed probe (scrubbed env dropping PYTHONPATH vs inherited).
  Only delta was the live HYPE mid (54.0262 vs 54.0597) - a real-time instrument artefact.
- No credentials loaded (HL_LIVE_ENV_FILE=/nonexistent; no .env in repo). No key value printed,
  logged or committed.
- No orders placed, cancelled or modified. Testnet exchange used read-only (info API).
- Oracle independence: every exchange read made by a standalone script that does not import engine
  or UI code.

## Headline finding - engine-lineage divergence

THREE DISTINCT ENGINE BINARIES are in play, and the register commit is NOT the engine that ran
the copy session:

| role | commit | Core sha256 | lines |
|---|---|---|---|
| register commit | `b142cf88` | `b171ec8fef01ead5...` | 8042 |
| engine prior evidence cited | `43731b4f` | `2dfbd571012af674...` | 8030 |
| engine that ran the live copy session | `d8a49d3e...` (`origin/engine/gate-snapshot-cache`) | `0cc9720c2932c09c...` | 13129 |

`d8a49d3` is NOT a descendant of `main` (merge-base `43731b4f`; 23 commits on main's side,
222 on the live side). The live copy engine therefore holds 222 commits of engine work that are
not in the certification register.

`follower_mid()` and `list_perp_dexes()` are byte-identical between `b142cf88` and `d8a49d3`
(extracted-function diff = IDENTICAL), so the pricing/TTL/DEX-scope semantics proven here hold on
both; the remainder of the engine differs by 5477 insertions / 390 deletions.

### Rows that name symbols existing only in the LEGACY module

At `b142cf88`, in the ENGINE module `_archive/hl_stage2/HL_Live_Copy_Service_Core.py`:

- `apply_fixed_sleeve_event` - core 0 / legacy 2 -> named by PRICE-001
- `FIXED_MODE_AUTHORITY_HOLD` - core 0 / legacy 4 -> named by ENG-003
- `HL_LIVE_QUOTE_CACHE_TTL_MS`, `EXECUTABLE_QUOTE_UNAVAILABLE` - core 0 -> named by PRICE-002

The Core instead implements `HL_LIVE_MIDS_CACHE_TTL_SEC` (2 s) + `HL_LIVE_MIDS_MAX_AGE_SEC` (5 s)
via `follower_mid()`. PRICE-002's rule was executed against those Core names and passes; the row
as written names legacy symbols and must be re-derived before it can be certified.

## Executed checks (all pass)

- ENG-INV-08: oracle enumerates 273 testnet perpDexs; engine `list_perp_dexes()` returns 273.
- PRICE-002: live mid via real network path; cached-within-max-age; stale-beyond-max-age -> 0.0
  (fail closed); beyond-TTL -> refetch.
- PRICE-001: `follower_mid` live; 3 real testnet orders traced `send_attempts.limit_price` ->
  exchange `userFillsByTime` fill (marketable side consistent, sizes match, cloid match 3/3).
- ENG-INV-09: 7/7 audit-referenced order ids independently read from the exchange and present in
  the engine ledger.
- ENG-INV-07: `sleeve_id` is `wallet::coin` - 880 distinct keys, 0 malformed, all resolve.

## Explicitly NOT covered (what a PASS would still need)

- ENG-INV-07/08/09: their `execution_proof` is a leader event driven through the engine at THIS
  commit; and each row's negative case (missing required scope fails closed; stale manual file does
  not override exchange) was not exercised - both need controlled live-engine runs.
- ENG-003: OD-02 is unruled and the required behaviour is a ZERO-order hold, which no order chain
  can prove.
- PRICE-001: the named defect site is not in the engine under test.
- PRICE-002: row names legacy symbols; needs re-derivation against the Core names.
