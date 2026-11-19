# Purge limitation and deployment order (backup/r4-purge-narrowed)

Status: DESIGN REQUIREMENT, not deployed. The new fail-closed reader and writer below exist only on
`backup/r4-purge-narrowed`. The code the host runs today is plaintext-only and would silently ignore a
hashed tombstone, so this branch must not be deployed on its own.

## (i) Unparseable entry = PURGED, and alerted

`load_purged_wallets()` must never skip a line it cannot parse. As of this branch:

- a line that is a 64-hex tombstone is used as-is;
- a plaintext wallet address is hashed once, so it still matches its wallet, and is rewritten hashed
  on the next save;
- anything else that carries no control character (e.g. `zz-not-a-wallet`, a truncated 60-hex
  tombstone, a corrupted line) is kept **verbatim** in the returned set, so the exact key that wrote it
  stays blocked, and the load emits a
  named event `PURGE_UNPARSEABLE_ENTRY count=… file=… entries=… treated=PURGED` and fills
  `PURGE_UNPARSEABLE_ENTRIES`, so the drop is visible instead of silent;
- `save_purged_wallets()` carries unparseable lines over from disk verbatim. Its read, merge, and replace
  are serialized under `_FILE_WRITE_LOCK`, so saves using this lock cannot erase entries added by another
  cooperating writer using the same lock; a writer in another process that does not take this lock is not
  covered by this guarantee. `test_purge_save_race.py` pins the covered half: 50 iterations plus 20 burst
  rounds of a cooperating writer racing the save, 0 entries lost;
- an unparseable entry that also carries a control character (newline, tab, NUL, DEL) is **rejected**, not
  carried over: written back verbatim it splits into several lines, so ONE supplied value would become
  several persisted records - and the extra line could be a wallet address the next load hashes into the
  valid set. A rejected entry is named by
  `PURGE_UNPARSEABLE_CONTROL_REJECTED count=… file=… entries=… treated=REJECTED` and fills
  `PURGE_UNPARSEABLE_REJECTED`;
- both alerts print **outside** `_FILE_WRITE_LOCK`, so a blocked stdout cannot stall every
  `atomic_write_json`/`atomic_write_csv` behind it.

Blank padding is not an entry and is still skipped: it names no wallet.

Proof in this branch, all run with `PAID_GUARD_ALLOW=1` and every exit code recorded. The lock check is
bound to the disk READ (an observed `Path.read_text`), not to a helper called after it: a hook on
`_split_tombstones` accepts a save whose `read_text` was hoisted above `_FILE_WRITE_LOCK`, and that save
loses 50 of 50 cooperating appends in `test_purge_save_race.py` while the hooked check still passes.

| command | result |
|---|---|
| `test_purge_unparseable_fails_closed.py` against the module at `eba8581` | 10 checks run, 7 `_FAIL`, then `ValueError: BAD_WALLET` from the old writer, exit 1 (RED) |
| `test_purge_unparseable_fails_closed.py` against this branch | `TOTAL=15 FAILED=0`, exit 0 |
| same test with the silent `continue` restored in an isolated copy | `TOTAL=15 FAILED=9`, exit 1 |
| same test with only the disk read hoisted above `_FILE_WRITE_LOCK`, merge left inside | `TOTAL=15 FAILED=1`, exit 1 |
| same test against the whole module at `ffb41fe` (pre-fix) | `TOTAL=15 FAILED=5`, exit 1 |
| `test_purge_save_race.py` (50 iterations + 20 burst rounds, cooperating writer) | `TOTAL=5 FAILED=0`, exit 0 |
| `test_purge_keeps_engine_history.py` | `TOTAL=16 FAILED=0`, exit 0 |
| `test_ui_routes_post_batch01.py` | `TOTAL=6 FAILED=0`, exit 0 |

## (ii) Known limitation: plaintext residue on the live host

Two plaintext residues exist and this branch does not remove them:

1. `hl_copy_output/purge_backups/<timestamp>_<first 8 hex>/` - the rollback copies the purge writes
   before it edits anything, and the directory name itself carries the wallet's address prefix by
   design.
2. `purged_wallets.txt` on the live host - the currently deployed writer stores plaintext addresses, so
   the live file (ruling figure: 61 lines) holds addresses, not hashes.

Neither is erasure of records: a retired wallet can still hold a position that must be closed, so the
purge intentionally keeps and backs up state. Anyone treating a purge as an erasure must be told that
the address prefix survives in `purge_backups/` and in the tombstone file until a human cleans it up.

Also unremovable in code: a truncated or corrupted tombstone cannot be matched to a wallet, so the wallet
it was written for stays unblocked (the entry itself blocks its own literal key and keeps alerting).
Recovering that wallet is a manual repair of the file.

## (iii) Deployment is atomic or not at all

The live file, the reader and the writer must change in the same window. Deploying any part alone makes
the block list lie:

| deployed alone | result |
|---|---|
| hashed writer + old plaintext reader | the old reader ignores hashed lines: every purged wallet silently unblocks |
| hashed reader + old plaintext writer | the old writer keeps writing plaintext, and the next save rewrites the file hashed: mixed states |
| migration before code | the still-deployed plaintext reader reads hashes it cannot parse |

Required single step, on Boss's explicit go:

1. stop the app/UI writers (engine and UI restart only on Boss's go);
2. back up `purged_wallets.txt`;
3. deploy the reader + writer from this branch;
4. migrate the 61 plaintext lines to sha256 tombstones in one atomic rewrite (tmp + replace);
5. verify: every wallet that was blocked before the migration still answers `is_purged() == True`, and
   `PURGE_UNPARSEABLE_ENTRIES` is empty;
6. restart engine and UI, then dashboard-check that the previously purged wallets stay hidden.

Nothing in this branch performs steps 1-6, and no step may be split across a deploy.

## (iv) Provenance of `eba8581` — contents verified, not unknown

An earlier report described commit `eba8581` as *absent*. That report was wrong. It **is** present in
this worktree and its contents were read here, not inferred:

```
$ git -C C:/Users/wigmore/oc-runs/w70-purgehash cat-file -t eba8581
commit
$ git -C C:/Users/wigmore/oc-runs/w70-purgehash log -1 --format='%H %s' eba8581
eba8581b0b3faaebff6547e796179abbbab425d2 Hash the purge tombstone; keep membership, migration and UI honest
$ git -C C:/Users/wigmore/oc-runs/w70-purgehash branch --contains eba8581
backup/r4-purge-narrowed
```

What `eba8581` actually contains, verified by reading its blobs:

- `_archive/hl_stage2/HL_Copy_App_SSOT.py` (blob `2a77ef4c`): `purge_tombstone()` returning
  64-hex-or-sha256, `load_purged_wallets()` hashing plaintext lines, and **the defect under repair** —
  the `except ValueError: continue` that silently dropped an entry it could not parse;
  `is_purged()` matching by hash only.
- `_archive/hl_stage2/test_purge_keeps_engine_history.py` (16 checks at `eba8581` and at HEAD):
  membership, migration rewrite and honest UI wording.
- `_archive/hl_stage2/test_ui_routes_post_batch01.py` (6 checks): including the purge route.

So `eba8581` is the parent of this branch's fail-closed commit, is reachable from
`backup/r4-purge-narrowed`, and is the exact revision the RED run above was taken against. No part of
this branch rests on an unverified revision.

