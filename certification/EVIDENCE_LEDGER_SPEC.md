# Evidence Ledger Specification

Status: proposed single authority; this document changes no verdict or matrix row.

## Authority and row contract

The evidence ledger is the sole authority for current certification verdicts. It contains exactly one row per stable requirement ID and exactly one current verdict per row. A verdict is one of `PASS`, `FAIL`, `BLOCKED`, or `NOT_TESTED`; applicability and proof-network constraints remain metadata and do not create parallel verdicts. Rows are keyed by the requirement ID from the certification matrix; IDs must be unique, with no missing or extra requirements relative to the matrix at the ledger snapshot.

Every verdict carries an artefact reference that produced that verdict: repository-relative `path`, the artefact blob `sha256`, and the exact `check_id` or `field` inside that artefact supporting the verdict. Also record `as_of_sha` (full commit SHA of the tree assessed) and `as_of_date` (UTC ISO-8601 date/time). The artefact must be resolvable at the named SHA and its hash must match. A verdict with no artefact reference is invalid. A verdict whose artefact does not exist at the named SHA is invalid. `NOT_TESTED` must reference the evidence record establishing the assessment boundary and identify the exact check/field showing no executed proof; it is not an unbound default. Evidence may be external only when an immutable content-addressed artefact is available and its path/identity, SHA-256, and check/field are recorded.

A row has one verdict, not an implicit merge of evidence sources. New assessments append/revise evidence with provenance and explicitly supersede the prior row verdict; retain history rather than silently overwrite. Derive aggregate counts exclusively from ledger rows, with a documented snapshot SHA/date.

## How this retires `run_status.csv`

`run_status.csv` remains the declared authority until a named approver records the transition in `certification/EVIDENCE_LEDGER_MIGRATION.md`. During reconciliation, any disagreement is a defect in the ledger to resolve; it is not a reason to quote the CSV as correct. Keep the CSV unchanged. The ledger becomes authoritative only after reconciliation is reviewed and the named approver records the transition; generated CSV/status views may then be projections, never independent verdict authorities.

## Five-count defect record

These are competing counts, not reconciled truth. Snapshot figures below are recorded in `certification/snapshots/G0_SNAPSHOT.json`. Ref labels identify the exact snapshot basis; the `0` is only the CSV verdict-audit count at the base ref, not a general verdict count.

| Count | Source and ref | Why it differs |
|---:|---|---|
| 6 | `run_status.csv` / generated `RUN_STATUS.md`; snapshot `declared_authority_pass` at snapshot `branch_head` `819b6bf9` | Latest `run_results.json` projection; six PASS are run results and the declared authority had not been reconciled with the matrix. |
| 54 | `certification_matrix.json` at pinned base `c63d2299` (`result_counts_at_base.PASS`) | Matrix carries prior evidence results at base; differs from generated run-status results. |
| 0 | `run_status.csv` verdict-bearing rows (`csv_verdicts` in snapshot), base audit for pinned base `c63d2299` | Snapshot's CSV verdict audit counted zero CSV verdict records under its audit definition, despite six declared/generated PASS; schema/representation does not yield a unified verdict authority. |
| 513 | Certification-claimed result fields in `certification_matrix.json` at snapshot refs: base `c63d2299` and head `819b6bf9` (`cert_claimed_counts`) | Claimed counts include stale/contradictory claims: snapshot records 511 base and 513 head contradictions against matrix results. |
| 582 | Retired `certification/results/apply_verified_results.py` overlay map; no named ref is recorded in the snapshot, so this is **not verified at a named ref** (`overlay_map_pass`) | Historical literal mapping has no evidence-file input; applying it would produce a different count and mismatches, so it is not an authority. |

The snapshot also records 50 matrix PASS at head `819b6bf9`; this sixth competing figure reinforces that the listed totals describe different inputs and must not be conflated. No value in this table is endorsed as the correct certification count.

## Fail-closed validator contract

The validator refuses the ledger on any failed condition; codes are stable machine-readable refusal codes. Resolve `matrix_ids` from the named matrix snapshot and `rows` from the complete ledger.

| Checkable condition | Refusal code |
|---|---|
| `set(current_row.requirement_id for current_row in rows) == matrix_ids` (missing or extra current IDs fail). | `E_REQUIREMENT_SET` |
| Each matrix ID has exactly one current row; a second current verdict fails. | `E_DUPLICATE_CURRENT` |
| `artefact.path` resolves to a blob at `as_of_sha`. | `E_ARTEFACT_MISSING` |
| SHA-256 of the blob bytes equals `artefact.sha256`. | `E_ARTEFACT_HASH` |
| Exact `check_id_or_field` is present in the artefact content. | `E_CHECK_NOT_FOUND` |
| The check record names the exact `as_of_sha` it ran against, and `as_of_date` is at or after that revision's recorded check time. | `E_CHECK_REVISION_MISMATCH` / `E_DATE_BEFORE_CHECK` |
| Resolved `artefact.path` is not a ledger file, including this ledger or another ledger. | `E_VERDICT_ARTEFACT` |
| JSON Schema violations, including `format: date-time`, are refused with format assertions enabled. | `E_SCHEMA` |

A check is considered to have run only when its artefact contains the identified check record explicitly naming the exact `as_of_sha`; a claimed result, nearby log, or unbound reference is insufficient. A schema parser without enforced assertions is decoration and does not satisfy validation.

## Untestable clause rule

Detect an untestable clause by examining the requirement text and linked acceptance criteria: if no executable check or objectively inspectable field can be identified, the clause is untestable. Record its verdict as `BLOCKED`, with a non-empty reason and named owner. It must never be `PASS` or left undefined; missing reason/owner is refused as `E_UNTESTABLE_METADATA`.

## Duplicate resolution

The validator refuses a second verdict for an ID as `E_DUPLICATE_CURRENT`; duplicates are not reconciled by judgement. A corrected verdict supersedes only through an explicit `supersedes` field naming the prior row's unique row ID. The prior row remains present. The validator verifies that the reference resolves to an earlier row for the same requirement; otherwise it refuses as `E_SUPERSEDES_INVALID`.

## JSON Schema: one ledger row

Draft 2020-12 schema. A complete ledger is an array of these rows; uniqueness of `requirement_id` is enforced across that array by the ledger validator.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://example.invalid/certification/evidence-ledger-row.schema.json",
  "title": "Certification evidence ledger row",
  "type": "object",
  "additionalProperties": false,
  "required": ["requirement_id", "verdict", "artefact", "as_of_sha", "as_of_date"],
  "properties": {
    "requirement_id": {"type": "string", "minLength": 1},
    "verdict": {"type": "string", "enum": ["PASS", "FAIL", "BLOCKED", "NOT_TESTED"]},
    "artefact": {
      "type": "object", "additionalProperties": false,
      "required": ["path", "sha256", "check_id_or_field"],
      "properties": {
        "path": {"type": "string", "minLength": 1},
        "sha256": {"type": "string", "pattern": "^[a-fA-F0-9]{64}$"},
        "check_id_or_field": {"type": "string", "minLength": 1}
      }
    },
    "as_of_sha": {"type": "string", "pattern": "^[a-fA-F0-9]{40}$"},
    "as_of_date": {"type": "string", "format": "date-time"}
  }
}
```

Schema validation does not establish artefact existence, SHA correctness, check semantics, requirement coverage, or row uniqueness across the ledger; those are mandatory semantic validation gates.
