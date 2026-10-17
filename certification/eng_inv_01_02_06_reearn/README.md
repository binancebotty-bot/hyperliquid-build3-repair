# ENG-INV-01 / -02 / -06 - re-earn, defect repair (card t_43fbb222)

Branch off `89b3bc7`. **Not merged.** No edit to `apply_verified_results.py` or
`certification_matrix.json`. Repairs the two defects the reviewer found in
`t_20e1cb6d`.

| row | verdict |
|---|---|
| ENG-INV-01 | PASS (unchanged - reviewer accepted) |
| ENG-INV-02 | **PASS**, on a narrowed predicate |
| ENG-INV-06 | PASS (unchanged - reviewer accepted) |

Files: `verdicts.json` (deliverable), `probe.py` -> `result.json`,
`verify_citations.py` -> `CITATION_RESOLUTION.json`, `gen_final.py`, `cited/`.

## Defect 1 - citation resolution (fixed)

The reviewer found two `evidence_ref` paths did not exist on the branch:

    certification/results/ENG-INV-01-02_ENG-010-014_SEM-B1-B4_corrected_43731b4f.json   MISSING
    certification/results/ENG-INV-06-09_43731b4.json                                    MISSING

`certification/results/` does not exist at `89b3bc7` nor on the source branch;
those files only ever lived under the branch's `cited/`. Every citation now names
a path that exists on this branch.

Proof: `verify_citations.py` splits each `evidence_ref` on ` + ` and `#` and tests
each path with `git cat-file -e <head>:<path>` - against the commit object, not
the working tree.

    total_refs=18 missing_count=0 ACCEPTANCE_ZERO_MISSING=True   (exit 0)

It is a real check: run before the first commit it reported 18/18 `EXISTS=NO`,
which is what a branch-object resolver must say about uncommitted files.

## Defect 2 - ENG-INV-02 predicate was over-scoped (narrowed, justified)

Row: "Exactly one physical production `.order()` call site."

Before, the predicate counted `*.order(...)` across every `.py` under
`_archive/hl_stage2` and found 2 - a file set, not the certified engine.
Narrowed to the certified engine scope:

| | before | after |
|---|---|---|
| predicate | `order_nodes(ALL_PRODUCTION_FILES) == 1` | `order_nodes(CERTIFIED_ENGINE_SCOPE) == 1` |
| count | 2 | 1 |
| row | FAIL | PASS |

Both counts are published (`count_certified_scope: 1`, `count_all: 2`).

### Scope authority, not convenience

* `MASTER_PRODUCT_INVARIANTS_AND_CERTIFICATION.md` OD-26 / section 5 (Boss,
  2026-10-09T12:30Z): certification targets the real Core engine
  `HL_Live_Copy_Service_Core.py`, NOT the legacy `HL_Live_Copy_Service.py`.
* Core's own header: "intentionally independent of the legacy HL_Live_Copy_Service.py flow."
* `ARCHITECTURE.md` scope budget: `production files: <=2`, `physical production
  order sites: 1`.
* `CONTROL_STATE.json`: `single_order_site` = "exactly one physical
  exchange.order() call site".

### What was excluded, and what it actually is

Excluded: `HL_Live_Copy_Service.py:1036`, inside `send_hyperliquid_order()`
(defined L936). Not dead code, not a test shim - a real, complete sender:
reads `HL_LIVE_HL_PRIVATE_KEY` (L971), `Account.from_key` (L1030),
`Exchange(...)` (L1035), `exchange.order(...)` (L1036), parses the ack (L1041).

Reachability traced end to end:

1. `manual_send_one_intent` (L1124) -> `send_hyperliquid_order` (L1387).
   Reached by `--send-one-intent <id> --confirm-send`.
2. `maybe_auto_send_would_send` (L2825) -> `manual_send_one_intent(..., True)`
   (L2860), called from `append_order_intent` (L2781), reached from
   `run_once -> process_fill`. Gated by `HL_LIVE_AUTO_SEND_ENABLED` (L141, default `0`).

With auto-send on, the legacy module can place a real order with no per-order
human confirm. Recorded as `residual_finding` in `verdicts.json` for the
Controller/Architect to rule on; out of scope here and deliberately not
repaired - this card fixes packaging and scoping, not product behaviour.

### The narrowing is falsifiable and the check can fail

All ten controls non-vacuous. Key ones:

| control | expected | got |
|---|---|---|
| `inv02_add_site_core_far` (send appended to Core) | FAIL | FAIL OK |
| `inv02_add_site_core_in_place_order` (send inside `_place_order`) | FAIL | FAIL OK |
| `inv02_add_site_legacy_only` (send added to legacy only) | PASS, scope-bounded | PASS OK |
| original cited predicate vs legacy-only send | PASS (blind) | PASS OK |
| original cited predicate vs site in its own window | FAIL | FAIL OK |

Two independent mutations inside the certified engine both trip the narrowed
check, so it is not vacuous. The scope-demonstration control shows the boundary
explicitly: a synthetic legacy send is invisible to the narrowed predicate and
visible to the unnarrowed one.

## Reproduce

    python certification/eng_inv_01_02_06_reearn/probe.py --repo . \
      --out certification/eng_inv_01_02_06_reearn/result.json
    python certification/eng_inv_01_02_06_reearn/gen_final.py
    python certification/eng_inv_01_02_06_reearn/verify_citations.py    # exit 0 = zero missing

`probe.py` reads engine sources out of git objects at `43731b4f`, so the result
is commit-bound and cannot drift with a dirty tree.
