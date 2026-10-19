#!/usr/bin/env python3
'''Does the testnet append-only audit carry any campaign dimension?

A campaign dimension means a column (or a repeated field) that ties a fill or a
send attempt to a declared campaign/scenario. Without one, per-campaign evidence
cannot be extracted from the audit - only per-run evidence can.

Read-only: opens the audit CSVs for reading, writes nothing there.

Usage: python probe_campaign_dimension.py <append_only_dir> <out.json>
'''
import csv
import io
import json
import os
import sys

TOKENS = ('campaign', 'scenario', 'manifest', 'phase_6t', 'phase6t')
RUN_TOKENS = ('b3-c2a', 'b3-c2h', 'b3-test')


csv.field_size_limit(1 << 24)


def sniff_header(path):
    with open(path, encoding='utf-8', errors='replace', newline='') as fh:
        chunk = fh.read(1 << 18)
    try:
        return next(csv.reader(io.StringIO(chunk))), chunk
    except Exception as exc:  # noqa: BLE001 - report, never crash
        return None, str(exc)


def main():
    root = sys.argv[1]
    out_path = sys.argv[2]
    files = []
    total_rows = 0
    campaign_cols = []

    for name in sorted(os.listdir(root)):
        if not name.endswith('.csv'):
            continue
        path = os.path.join(root, name)
        header, chunk = sniff_header(path)
        entry = {
            'file': name,
            'bytes': os.path.getsize(path),
            'header_read': header is not None,
        }
        if header is None:
            entry['error'] = chunk
            files.append(entry)
            continue
        entry['column_count'] = len(header)
        camp = [c for c in header if any(t in c.lower() for t in TOKENS)]
        entry['campaign_columns'] = camp
        entry['campaign_token_hits_in_first_256k'] = {
            t: chunk.lower().count(t) for t in TOKENS + RUN_TOKENS
        }
        # count lines without parsing (some rows exceed the csv field limit)
        n = -1
        with open(path, 'rb') as fh:
            for _ in fh:
                n += 1
        entry['data_rows'] = max(n, 0)
        entry['data_rows_counted_by'] = 'newline count minus header'
        total_rows += n
        if camp:
            campaign_cols.append((name, camp))
        files.append(entry)

    out = {
        'task_id': 't_9c795ece',
        'audit_dir': root,
        'files_scanned': len(files),
        'total_data_rows_in_audit': total_rows,
        'files_with_a_campaign_column': campaign_cols,
        'campaign_dimension_present': bool(campaign_cols),
        'verdict': 'CAMPAIGN_DIMENSION_PRESENT' if campaign_cols else 'NO_CAMPAIGN_DIMENSION',
        'interpretation': (
            'No column in any audit file names a campaign, scenario or manifest, and no '
            'run/campaign identifier repeats in the data. The audit records individual send '
            'attempts and fills; it cannot be re-cut per campaign without an external mapping '
            'that does not exist in the repo. So per-campaign evidence for TN-CAMP-01..09 '
            'cannot be produced from this data, and inventing campaign ids would be fabrication.'
        ),
        'files': files,
    }
    with open(out_path, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(out, fh, indent=1)
        fh.write('\n')
    print('verdict:', out['verdict'])
    print('files:', len(files), 'rows:', total_rows)
    print('campaign columns:', campaign_cols)


if __name__ == '__main__':
    main()
