# Certification (Build 3 Repair)

This folder is the single reconciled list of what must be proven before the Hyperliquid copy engine is called done. It grants no authority, closes no gate and authorises no code change.

## Read order for an agent starting here
1. `MASTER_PRODUCT_INVARIANTS_AND_CERTIFICATION.md`: §3 (how to record a result), §4 (precedence), §5 (settled decisions: do not reopen), §6 (open decisions: do not pick a side).
2. `open_decisions.json`: the same §6 register, with the matrix records each decision blocks.
3. `certification_matrix.json` (or `.csv`): one record per requirement. Every record has a source, an execution proof path, an independent oracle and negative tests.
4. `RUN_STATUS.md` (and `run_status.csv`): the current NOT_TESTED / PASS / FAIL status of every requirement, run by run, with evidence.

## Rules
- Pick work by matrix ID. A record with `applicability = OPEN_DECISION` cannot be certified until its OD-xx is ruled; escalate it, never decide it.
- A result is `PASS` only with evidence from an executed run on one commit. Nothing passes by inference (a code read is not a result). A `FAIL` is kept in the history even after a later PASS.
- Certification runs follow real, active mainnet leader wallets and send only to the testnet follower account (§5).
- Pre-existing orders and positions on the follower account (including Build 4 leftovers) are never touched (ENG-016).

## Recording a run
Results live in `run_results.json`, not in the matrix. After each testnet run, append one entry to `runs` (`run`, `date`, `commit`, `network`, `report`, `summary`, and `results`: a list of `{id, result, evidence}` with `result` PASS or FAIL), then run:

    python3 certification/gen_status.py

It checks every ID exists in the matrix and rewrites `RUN_STATUS.md` and `run_status.csv`. A requirement's status is its result in the latest run that tested it.

## Regenerating the matrix
The matrix is generated from copies of the cited source documents, which are not in this repository (Build 4 and Mission Control are private, and the local evidence is large). With those copies available:

    HL_CERT_SOURCE_DOCS=/path/to/source-docs python3 certification/gen_matrix.py

`certification_matrix.json → source_sha256` lists every source file and its hash, so a regenerated matrix can be checked against the same inputs. Requirement IDs are stable; withdrawn requirements become `SUPERSEDED`, never deleted.
