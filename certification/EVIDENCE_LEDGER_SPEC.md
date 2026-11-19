# Evidence Ledger Specification

Status: proposed single authority; this document changes no verdict or matrix row.

## Authority and row contract

The evidence ledger is the sole authority for current certification verdicts. It contains exactly one row per stable requirement ID and exactly one current verdict per row. A verdict is one of `PASS`, `FAIL`, `BLOCKED`, or `NOT_TESTED`; applicability and proof-network constraints remain metadata and do not create parallel verdicts. Rows are keyed by the requirement ID from the certification matrix; IDs must be unique, with no missing or extra requirements relative to the matrix at the ledger snapshot.

Every verdict carries an artefact reference that produced that verdict: repository-relative `path`, the artefact blob `sha256`, and the exact `check_id` or `field` inside that artefact supporting the verdict. Also record `as_of_sha` (full commit SHA of the tree assessed) and `as_of_date` (UTC ISO-8601 date/time). The artefact must be resolvable at the named SHA and its hash must match. A verdict with no artefact reference is invalid. A verdict whose artefact does not exist at the named SHA is invalid. `NOT_TESTED` must reference the evidence record establishing the assessment boundary and identify the exact check/field showing no executed proof; it is not an unbound default. Evidence may be external only when an immutable content-addressed artefact is available and its path/identity, SHA-256, and check/field are recorded.

A row has one verdict, not an implicit merge of evidence sources. New assessments append/revise evidence with provenance and explicitly supersede the prior row verdict; retain history rather than silently overwrite. Derive aggregate counts exclusively from ledger rows, with a documented snapshot SHA/date.

## How this retires `run_status.csv`

Migration is additive: derive the ledger from existing sources first, then diff it against `run_status.csv`. Keep the CSV unchanged during reconciliation. No count is declared correct until the diff is empty or every differing requirement is explained row by row with source evidence. The ledger becomes authoritative only after this reconciliation is reviewed; generated CSV/status views may then be projections, never independent verdict authorities.

## Five-count defect record

These are competing counts, not reconciled truth. Snapshot figures below are recorded in `certification/snapshots/G0_SNAPSHOT.json`; base/head meanings follow that snapshot.

| Count | Source and ref | Why it differs |
|---:|---|---|
| 6 | `run_status.csv` / generated `RUN_STATUS.md`; snapshot `declared_authority_pass` | Latest `run_results.json` projection; six PASS are run results and the declared authority had not been reconciled with the matrix. |
| 54 | `certification_matrix.json` at pinned base `c63d2299` (`result_counts_at_base.PASS`) | Matrix carries prior evidence results at base; differs from generated run-status results. |
| 0 | `run_status.csv` verdict-bearing rows (`csv_verdicts` in snapshot) | Snapshot's CSV verdict audit counted zero CSV verdict records under its audit definition, despite six declared/generated PASS; schema/representation does not yield a unified verdict authority. |
| 513 | Certification-claimed result fields in `certification_matrix.json` (snapshot `cert_claimed_counts`) | Claimed counts include stale/contradictory claims: snapshot records 511 base and 513 head contradictions against matrix results. |
| 582 | Retired `certification/results/apply_verified_results.py` overlay map (`overlay_map_pass`) | Historical literal mapping has no evidence-file input; applying it would produce a different count and mismatches, so it is not an authority. |

The snapshot also records 50 matrix PASS at head; this sixth competing figure reinforces that the listed totals describe different inputs and must not be conflated. No value in this table is endorsed as the correct certification count.

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
