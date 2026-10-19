#!/usr/bin/env python3
"""Apply the TN campaign-evidence verdicts to certification/certification_matrix.{json,csv}.

Touches ONLY the 15 TN rows named in card t_9c795ece. Every other row is preserved
byte-for-byte at the value level; JSON and CSV are rewritten with the exact serialisation
that was proven byte-identical to the committed blob before editing.

Sets, for each TN row:
  result        = NOT_TESTED
  evidence_ref  = EVIDENCE/TN_CAMPAIGN_EVIDENCE/TN_CAMPAIGN_EVIDENCE.json
  tested_commit = ""
  tested_at_utc = ""
  notes         = <existing notes> + " | TN-CAMPAIGN-EVIDENCE: <row reason>"

The per-row reason text is read from TN_CAMPAIGN_EVIDENCE.json so the two artifacts
cannot drift. Refuses to run if any named row is missing or duplicated.

Usage: python apply_tn_campaign_verdicts.py <repo_root>
"""
import csv
import io
import json
import sys
from pathlib import Path

EVIDENCE_REL = 'EVIDENCE/TN_CAMPAIGN_EVIDENCE/TN_CAMPAIGN_EVIDENCE.json'
PREFIX = 'TN-CAMPAIGN-EVIDENCE:'

SHORT_REASON = {
    'TN-CAMP-01': 'no campaign manifest committed before the first order; cited check is a product-logic no-change assertion',
    'TN-CAMP-02': 'no follower account observed at a campaign start; cited check states engine start-up semantics only',
    'TN-CAMP-03': 'no universe snapshot artifact cited and no refused symbol named',
    'TN-CAMP-04': 'cited check is a control-mailbox transport hold, not a testnet order event',
    'TN-CAMP-05': 'cloid/oid named as a cleanup rule only; no observed identifier',
    'TN-CAMP-06': 'cited check is a test-count summary; no abort condition exercised, no halt timestamp',
    'TN-CAMP-07': 'identity record names engine hash and commit only; interpreter, SDK version and config hash absent',
    'TN-CAMP-08': 'no scenario class named and no exchange response quoted; row passes by the inference it forbids',
    'TN-CAMP-09': 'gaps documented only; no mainnet verification cited',
    'TN-F24': 'OD-24 unresolved; audit shows 67 RATE_LIMIT_OR_TIMEOUT attempts but carries no weight accounting',
    'TN-F25': 'no launcher/release-pointer identity surface reachable from the register; OD-12 unresolved',
    'TN-F26': 'OD-22 unresolved; the reading the row asserts is not yet ruled',
    'TN-F27': 'OD-23 unresolved and no margin-event capture exists; audit records orders and fills only',
    'TN-PS1': 'invariant stated in a document but no post-trade projection probe executed; OD-23 unresolved',
    'TN-T1': 'nearest candidate B3-TESTNET-ACCEPT.json is a read-only account probe whose commit is not an ancestor of the register',
}


SHARED = 'no campaign-specific evidence; existing citation is a shared semantics report'


def row_reason(row_id):
    """Only the nine TN-CAMP rows had a citation at all.

    Those nine cited one shared semantics report, so the shared-report wording is
    accurate for them. The other six rows cited nothing; claiming they had a shared
    citation would be false, so they get the bare missing-component reason.
    """
    if row_id.startswith('TN-CAMP-'):
        return f'{SHARED}. {SHORT_REASON[row_id]}'
    return SHORT_REASON[row_id]


def apply_to_records(records, wanted):
    seen = {}
    for r in records:
        if r['id'] in wanted:
            seen[r['id']] = seen.get(r['id'], 0) + 1
    missing = sorted(set(wanted) - set(seen))
    dupes = sorted(k for k, v in seen.items() if v != 1)
    if missing or dupes:
        raise SystemExit(f'ABORT: missing={missing} duplicated={dupes}')
    for r in records:
        if r['id'] not in wanted:
            continue
        r['result'] = 'NOT_TESTED'
        r['evidence_ref'] = EVIDENCE_REL
        r['tested_commit'] = ''
        r['tested_at_utc'] = ''
        base = r.get('notes') or ''
        marker = f'{PREFIX} {row_reason(r["id"])}'
        r['notes'] = f'{base} | {marker}' if base else marker
    return records


def main():
    repo = Path(sys.argv[1] if len(sys.argv) > 1 else '.').resolve()
    ev = json.loads((repo / EVIDENCE_REL).read_text(encoding='utf-8'))
    wanted = [r['row_id'] for r in ev['rows']]
    assert len(wanted) == 15, wanted

    jpath = repo / 'certification' / 'certification_matrix.json'
    raw = jpath.read_bytes()
    doc = json.loads(raw.decode('utf-8'))
    # prove the serialisation before touching anything
    probe = (json.dumps(doc, indent=1, ensure_ascii=False) + '\n').encode('utf-8')
    if probe != raw:
        raise SystemExit('ABORT: JSON serialisation is not byte-stable; refusing to rewrite')
    doc['records'] = apply_to_records(doc['records'], wanted)
    out = (json.dumps(doc, indent=1, ensure_ascii=False) + '\n').encode('utf-8')
    jpath.write_bytes(out)
    print(f'wrote {jpath} {len(raw)} -> {len(out)} bytes')

    cpath = repo / 'certification' / 'certification_matrix.csv'
    craw = cpath.read_bytes()
    rows = list(csv.reader(io.StringIO(craw.decode('utf-8'), newline='')))
    header = rows[0]
    idx = {name: i for i, name in enumerate(header)}
    touched = 0
    for row in rows[1:]:
        rid = row[idx['id']]
        if rid not in wanted:
            continue
        row[idx['result']] = 'NOT_TESTED'
        row[idx['evidence_ref']] = EVIDENCE_REL
        row[idx['tested_commit']] = ''
        row[idx['tested_at_utc']] = ''
        base = row[idx['notes']]
        marker = f'{PREFIX} {row_reason(rid)}'
        row[idx['notes']] = f'{base} | {marker}' if base else marker
        touched += 1
    if touched != 15:
        raise SystemExit(f'ABORT: CSV touched {touched} rows, expected 15')
    buf = io.StringIO(newline='')
    csv.writer(buf, lineterminator='\r\n').writerows(rows)
    cpath.write_bytes(buf.getvalue().encode('utf-8'))
    print(f'wrote {cpath} {len(craw)} -> {len(buf.getvalue())} bytes, rows touched {touched}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
